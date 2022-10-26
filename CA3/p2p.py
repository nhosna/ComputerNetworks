import errno
import fcntl
import json
import multiprocessing
import os
import random
import socket
import sys

from datetime import datetime, timedelta
from time import sleep

from  util import str_to_packet, packet_id, id_to_addr, Hello, packet_to_str, draw_graph, \
    save_connections, port_to_id, addr_to_id, log,   draw_graph
from  constants import RUNTIME, NODES, IP_ADDR, PORT, BUFSZ, HELLO_THRESHOLD, N, \
    HELLO_EVERY, PAUSE_EVERY, PAUSE_DURATION, LOSS_CHANCE, K


class Node(multiprocessing.Process):
    def __init__(self,queue,id):
        multiprocessing.Process.__init__(self)
        self.queue=queue #queue for suspending or killing processes
        self.id=id
        self.port=PORT +id
        self.ip=IP_ADDR
        self.address=    (self.ip, self.port)

        self.bidirN,self.unidirN,self.tempN=set(),set(),None

        self.lastRecFrom,self.lastSentTo={addr_to_id(k):datetime.now() for k in NODES},{addr_to_id(k):datetime.now() for k in NODES}
        self.starttime=datetime.now()

        "contains the history of all neighbours ever connected to and the number of packets sent to /received from them"
        self.packetHistoryN={}


        "contains the list of my bidir neighbours' neighbours obtained from the packet.recentlyHeardN of packets received from them"
        self.neighbourHistoryN={}


        "the reachabilty of each of my neighbours"
        self.reachHistoryN={}


    "check if i should be paused for PAUSE_DURATION seconds every PAUSE_EVERY seconds"
    def check_pause(self):
        if (datetime.now() - self.lastpausecheck >= timedelta(seconds=PAUSE_EVERY)):

            self.lastpausecheck = datetime.now()
            paused_proc = self.queue.get()
            self.queue.task_done()
            if paused_proc is None:  # stop process
                self.finalize_reachability()
                self.output_history()
                self.sock.close()
                sys.exit()
            elif paused_proc is self.id:  # pause process
                log("{}:sleeping".format(self.id ))

                sleep(PAUSE_DURATION)
                log("{}:waking up".format(self.id ))


    "send hello to neighbours every 2 secs"
    def hello_period(self):

        if ( datetime.now() - self.lastsent >= timedelta(seconds=HELLO_EVERY)):
            self.lastsent = datetime.now()
            self.send_neighbours()


    "start"
    def listen(self):
        then=datetime.now() -timedelta(minutes=10)
        self.lastsent=then
        self.lastpausecheck=datetime.now()
        self.lastfindneighbour=then
        while (True):
            self.check_pause()
            self.hello_period()
            self.receive()
            self.find_neighbour()


    def neighbours_count(self):
        return len(self.bidirN) + len(self.unidirN)

    def bind(self):
        self.sock  = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        fcntl.fcntl(self.sock, fcntl.F_SETFL, os.O_NONBLOCK)


    def run(self):
        log("{}: node started".format(self.id))
        self.bind()
        self.listen()


    def hello(self,addr):


        log("{}:sending hello to {}:{}".format(self.id,addr[0],addr[1]))
        receiver_id=addr_to_id(addr)

        "set packet's neighbours"

        packet = Hello(self.id, self.ip, self.port)

        packet.recentlyHeardN['unidir']=self.unidirN
        packet.recentlyHeardN['bidir']=self.bidirN

        "set last_rec and last_sent"
        now=datetime.now()
        packet.last_sent=now
        packet.last_rec=self.lastRecFrom[receiver_id]

        "update my own lastsent data"
        self.lastSentTo[receiver_id]=now

        "send packet"
        msg=packet_to_str(packet)
        self.send(msg,addr)
        self.update_packet_history(receiver_id,'sent')


    "drop packet with a probability of 5%"
    def send(self,msg,addr):

        self.sock.sendto(msg.encode(), addr)


    def receive(self):

        try:
            msg =self.sock.recv(BUFSZ)
            pckt_str=msg.decode()
        except socket.error as e:
            err = e.args[0]
            if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                # log('no data')
                return
            else:
                # a "real" error occurred
                log(e)
                sys.exit(1)
        else:
            #drop packets with 5% probability
            r = random.choice(range(100))
            if (r < LOSS_CHANCE):
                log("{}:packet lost".format(self.id))
                return

            pckt=str_to_packet(pckt_str)

            log("{}:received hello from {}".format(self.id, pckt.sender))
            self.process_hello(pckt)

            return


    "first we check when we have last received a hello from this sender. if it was more than 8 seconds ago we delete them and consider them a unidir even if we were on their neighbour's list"
    def add_neighbour(self,now,pckt,pckt_id):
        log("{}:node {}'s neighbours are:{}".format(self.id,pckt_id,pckt.recentlyHeardN))
        log("{}:my neighbours are: unidir:{} bidir:{}".format(self.id,list(self.unidirN) ,list(self.bidirN)))


        if (self.tempN!=None and addr_to_id(self.tempN) == pckt_id):
            self.tempN = None



        if ( (now - self.lastRecFrom[pckt_id] <=  timedelta(seconds=HELLO_THRESHOLD))   ):

            if( (self.id in pckt.recentlyHeardN['unidir']) or (self.id in pckt.recentlyHeardN['bidir']) ):

                self.unidirN.discard(pckt_id)


                if(pckt_id not in self.bidirN ):
                    if(len(self.bidirN)<N):
                        self.bidirN.add(pckt_id)
                        log("{}:node {} now my bidir neighbour".format(self.id, pckt_id))
                    else:
                        log("{}:cant accept node {}'s request now".format(self.id, pckt_id))


            else:
                self.bidirN.discard(pckt_id)
                self.unidirN.add(pckt_id)
                log("{}:node {} now my unidir neighbour".format(self.id, pckt_id))

        #if he hasn't sent a hello packet within threshold treat him as a new neighbour
        else:
            self.bidirN.discard(pckt_id)
            self.unidirN.add(pckt_id)
            log("{}:node {} now my unidir neighbour".format(self.id, pckt_id))



        self.update_reachability(pckt_id,'add')




    "updates the neighbour status of the node who sent hello or adds it to neigbhours if they are mutual hello pals"
    def process_hello(self,pckt ):


        now=datetime.now()
        pckt_id=packet_id(pckt)

        self.add_neighbour(now,pckt,pckt_id)


        "update my lastrec data"
        self.lastRecFrom[pckt.sender] =now


        "update my neighbour's neighbour and packet history"
        self.update_packet_history(pckt_id,'received')
        self.update_neighbours_history(pckt_id,pckt)




    "updates the neighbours history of the node who sent me the package"
    def update_neighbours_history(self,pckt_id,packet):
        self.neighbourHistoryN[pckt_id]=packet.recentlyHeardN

    "updates the number of packets sent/received from the node with id"
    def update_packet_history(self,id,type):
        if(id not in self.packetHistoryN.keys()):
            self.packetHistoryN[id]={"sent":0,"received":0}
        else:
            self.packetHistoryN[id][type]+=1

    def update_reachability(self,id,type ):
        if(type=='remove'):


            self.reachHistoryN[id]['total']+=datetime.now() -self.reachHistoryN[id]['lastAdded']


        elif(type=='add'):
            if(id in self.reachHistoryN.keys()):
                self.reachHistoryN[id]['lastAdded']=datetime.now()

            else:
                self.reachHistoryN[id]={'total':timedelta(days=0,seconds=0,microseconds=0),'lastAdded':datetime.now()}


    def finalize_reachability(self):
        for neighbours in [self.unidirN,self.bidirN]:
            for n in neighbours:
                self.update_reachability(n, 'remove')


    "removes the neighbours listed in removed from unidir/bidir"
    def remove_neighbours(self,removed):
        for r in removed:
            self.update_reachability(r,'remove')

            self.unidirN.discard(r)
            self.bidirN.discard(r)



    "send hello to neighbours every 2 secs"
    def send_neighbours(self):


        removed = set()

        "now send hello to all valid neighbours"
        for neighbours in [self.unidirN, self.bidirN]:
            for id in neighbours:
                if (datetime.now() - self.lastRecFrom[id] > timedelta(seconds=HELLO_THRESHOLD)):
                    removed.add(id)
                else:
                    self.hello(id_to_addr(id))

        self.remove_neighbours(removed)


    "possible nodes are the ones we are not neighbours with and surely not ourselves"
    def possible_new_neighbours(self):
        possible_nodes = NODES.copy()
        possible_nodes.remove(self.address)

        n=possible_nodes.copy()
        for p in possible_nodes:
            if(p in self.unidirN or p in self.bidirN):
                n.remove(p)

        return n


    "randomly send hello to a node"
    def find_neighbour(self):
        if( self.tempN!=None and datetime.now()- self.lastRecFrom[addr_to_id(self.tempN)]>=timedelta(seconds=HELLO_THRESHOLD)):
            self.tempN=None
        if(datetime.now()- self.lastfindneighbour >=timedelta(seconds=HELLO_EVERY) and self.neighbours_count()<N and self.tempN==None):

            possible_nodes=self.possible_new_neighbours()
            log("{}:possible nodes are {}".format(self.id,[addr_to_id(i) for i in possible_nodes]))
            if(len(possible_nodes)>0):
                rand_addr=random.choice(possible_nodes)
                log("{}:randomly sending neighbour req to {}".format(self.id,rand_addr))
                self.tempN=rand_addr
                self.lastRecFrom[addr_to_id(rand_addr)]=datetime.now()
                self.hello(rand_addr)

            self.lastfindneighbour=datetime.now()


    "shows the topology of network from this node's point of view"
    def network_topology(self):

        "get the neighbour history of only our bidir neighbours"
        validHistory = {}
        for k in self.neighbourHistoryN.keys():
            if (k in self.bidirN):
                validHistory[k] = {'bidir':list(self.neighbourHistoryN[k]['bidir']),'unidir':list(self.neighbourHistoryN[k]['unidir'])}


        "add my own neighbour history"
        validHistory[self.id]={'bidir':list(self.bidirN),'unidir':list(self.unidirN)}
        draw_graph(self.id, validHistory)


        return validHistory



    "draws network topology, history of packets ever sent/received,valid neighbours and reachability of each node "
    def output_history(self):


        connections=self.network_topology()
        history={"addresses":{k:str (id_to_addr(k)) for k in range(K)}, "connections":connections,"packets":self.packetHistoryN,'neighbours':list(self.bidirN),'reachability':{id: str (self.reachHistoryN[id]['total']) for id in self.reachHistoryN.keys() }}
        file = open('output/{}_history.json'.format(self.id), 'w+')
        j = json.dumps(history,indent=4)
        file.write(j)
        file.close()










