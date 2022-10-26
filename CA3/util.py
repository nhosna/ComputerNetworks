import json
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt

from  constants import PORT, IP_ADDR, LOGGING


def log(txt):
    if(LOGGING):
        print("[{}]-{}".format(datetime.now().time(),txt))

class Hello:
    def __init__(self,sender,ip,port ):
        self.sender=sender
        self.ip=ip
        self.port=port
        self.type="Hello"
        self.last_sent=None
        self.last_rec=None
        self.recentlyHeardN={ }



class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)




def str_to_packet(pckt_str):
    pckt_json = json.loads(pckt_str)
    pckt = Hello(None, None, None)
    pckt.ip = pckt_json["IP"]
    pckt.sender = pckt_json["Id"]
    pckt.port = pckt_json["Port"]
    pckt.recentlyHeardN = json.loads(pckt_json["Neigbours"])
    pckt.type = pckt_json["Type"]
    pckt.last_rec = str_to_date(pckt_json["LastRec"])
    pckt.last_sent =str_to_date( pckt_json["LastSent"])
    return pckt


"makes hello packet"

def date_to_str(d):
    return  d.strftime('%y-%m-%d %H:%M:%S.%f')

def str_to_date(s):
    datetime.strptime(s, '%y-%m-%d %H:%M:%S.%f')

def packet_to_str(packet):
    pckt = {}
    pckt["IP"] = packet.ip
    pckt["Id"] = packet.sender
    pckt["Port"] = packet.port
    pckt["Neigbours"] =  json.dumps(packet.recentlyHeardN , cls=SetEncoder)
    pckt["Type"] = packet.type
    pckt["LastRec"] = date_to_str(packet.last_rec)
    pckt["LastSent"] = date_to_str(packet.last_sent)
    pckt_str = json.dumps(pckt)

    return pckt_str


"gets id of packet by concatenating ip and port"


def packet_id(packet):
    # return "{}:{}".format(packet.ip, packet.port)
    return packet.sender

def addr_to_id(address):
    return port_to_id(address[1])

def port_to_id(port):
    return port-PORT

def id_to_addr(id):
    port=PORT+id
    address=IP_ADDR
    return (address,port)


"neighbours={id:{'bidir':set(),'unidir':set}}"
def draw_graph(id, neighbours):


    G = nx.DiGraph()

    for n in neighbours.keys():
        G.add_node(n)
        for b in neighbours[n]['bidir']:
            G.add_node(b)
            G.add_edge(n,b) #if a node b is inside node n's bidir neighbours then an edge from n to b is drawn



    plt.title("network topology from node {}".format(id))
    nx.draw_networkx(G,with_labels=True,node_color='c')
    plt.savefig("output/{}_topology.png".format(id))


"saves the connections between a node's neighbours"
def save_connections(id,neighbours):
    file=open('output/{}_connections.json'.format(id),'w+')

    j=json.dumps(neighbours)
    file.write(j)
    file.close()


