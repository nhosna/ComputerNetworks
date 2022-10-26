
#!/usr/bin/env python
# --*-- coding: utf-8 --*--
import os
import select
import signal
import socket
import sys
import time
from cmd import Cmd



class FTPClient(Cmd):
    def __init__(self):
        Cmd.__init__(self)
        Cmd.intro = "Starting FTPClient. Type HELP to list commands.\n"
        Cmd.prompt = ">>> "
        self.socket = None
        self.dataSocket=None
        self.server_ip="127.0.1.1"

    def CWD(self,*args):
        pass
    def PWD (self,*args):
        pass
    def MKD (self,*args):
        pass
    def RMD (self,*args):
        pass
    def PASS (self,*args):
        pass
    def USER (self,*args):
        pass
    def HELP (self,*args):
        pass
    def QUIT(self,*args):
        socket_list = [ self.socket]
        read_sockets, write_sockets, error_sockets = select.select(
            socket_list, [], [])
        for sock in read_sockets:
            if sock == self.socket:
                try:
                    data = sock.recv(1024)
                except socket.error:
                    print("Server closed connection")
                    self.do_quit()
                else:  # socket data
                    if not data:
                        print('Disconnected from server')
                        self.do_quit()
                        break
                    else:  # message from server
                        sys.stdout.write(data.decode('utf-8'))
                        self.do_quit()
                        break


    "handle dataport comm with server for getting list of files"
    def LIST(self,*args):

        socket_list = [self.socket]
        while(True): ##handle error sending message too if sending failed send message from server and exit loop

            # Get the list sockets which are readable
            read_sockets, write_sockets, error_sockets = select.select(
                socket_list, [], [])

            for sock in read_sockets:
                if sock == self.socket:#command from server in commandsocket
                    try:
                        data = sock.recv(1024)
                    except socket.error:
                        print("Server closed connection")
                        break
                    else:  # socket data
                        if not data:
                            print('Disconnected from server')
                            # self.do_quit()
                            return
                        else:  # message from server
                            command_code= data.decode('utf-8').strip().split(" ")[0]
                            sys.stdout.write(data.decode('utf-8'))
                            if(command_code== "226"):
                                self.disconnect_datasocket()
                                return
                            elif (command_code ==  '550'):#file unavailable
                                self.disconnect_datasocket()
                                return
                            elif (command_code==  '150'):
                                self.connect_to_datasocket()
                                socket_list.append(self.dataSocket)
                            else:
                                self.disconnect_datasocket()
                                return
                else:  # data in datasocket
                    try:
                        data = sock.recv(1024)
                    except socket.error:
                        print("Server closed connection")
                        break
                    else:  # socket data
                        if not data:
                            print('Disconnected from server')
                            break
                        else:  # data from server
                            sys.stdout.write(data.decode('utf-8'))

    def DL(self,*args):
        file_name=args[0]
        socket_list = [self.socket]
        file_parts=file_name.split(".")
        if (len(file_parts) > 1):
            file_name = time.strftime("{}-%Y-%m-%d %H-%M-%S.{}".format(file_parts[0], file_parts[1]))
        else:
            file_name = time.strftime("{}-%Y-%m-%d %H-%M-%S".format(file_parts[0]))

        file = open(file_name, 'w+')
        file.close()

        while (True):  ##handle error sending message too if sending failed send message from server and exit loop


            read_sockets, write_sockets, error_sockets = select.select(
                socket_list, [], [])

            for sock in read_sockets:
                if sock == self.socket:  # command from server in commandsocket
                    try:
                        data = sock.recv(1024)
                    except socket.error:
                        print("Server closed connection")
                        break
                    else:  # socket data
                        if not data:
                            print('Disconnected from server')
                            return
                        else:  # message from server
                            command_code =  data.decode('utf-8').strip().split(" ")[0]
                            sys.stdout.write(data.decode('utf-8'))

                            if (command_code ==  '226'):#finished sending
                                self.disconnect_datasocket()
                                return
                            elif (command_code ==  '550'): #file unavailable
                                self.disconnect_datasocket()
                                os.remove(file_name)
                                return
                            elif (command_code ==  '425'): #cant open data conn
                                self.disconnect_datasocket()
                                os.remove(file_name)
                                return
                            elif (command_code ==  '150'):#starting data connection
                                print("connecting to datasocket")
                                self.connect_to_datasocket()
                                socket_list.append(self.dataSocket)
                                # break
                            else:
                                os.remove(file_name)
                                self.disconnect_datasocket()
                                return
                else:  # data in datasocket
                    try:
                        data = sock.recv(1024)
                    except socket.error:
                        print("Server closed connection")
                        break
                    else:  # socket data
                        if not data:
                            print('Disconnected from server')
                            break
                        else:  # data from server
                            # sys.stdout.write(data.decode('utf-8'))
                            file = open(file_name, 'a')
                            file.write(data.decode('utf-8'))
                            file.close()

    def connect_to_datasocket(self ):
        self.dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dataSocket.connect((self.server_ip, self.dataPort))

    def disconnect_datasocket(self):
        # close(self.dataSocket)
        self.dataSocket.close()

    def set_dataport(self,dataPort):
        self.dataPort=int (dataPort.rstrip())

    def connect(self ):

        def signal_handler(sig, frame):
            self.do_quit()

        signal.signal(signal.SIGINT, signal_handler)

        while(len(sys.argv)!=2):
            print("Usage: client.py <port>")
            return
        self.ftp_port=int (sys.argv[1])
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.server_ip, self.ftp_port))
        self.socket.send("PSV".encode('utf-8'))  # send passive command to know which data port to connect to

        while True:
            socket_list = [sys.stdin, self.socket]
            read_sockets, write_sockets, error_sockets = select.select(
                socket_list, [], [])

            for sock in read_sockets:
                if sock == self.socket:
                    try:
                        data = sock.recv(1024)
                    except socket.error:
                        print("Server closed connection")
                        self.do_quit()
                    else: #socket data
                        if not data:
                            print('Disconnected from server')
                            self.do_quit()
                            break
                        else: #message from server
                            args = data.decode('utf-8').split(" ")
                            if (args[0] == "PSV"):
                                self.set_dataport(args[1])

                            sys.stdout.write(data.decode('utf-8'))

                else: # user entered a message
                    msg = sys.stdin.readline().rstrip()
                    args=msg.split(" ")
                    cmd=args[0]
                    args=[a for a in args[1:]]

                    ##TODO use this instead

                    self.socket.send(msg.encode('utf-8')) #send user message to server
                    try:
                        func = getattr(self,cmd )  ##call the function corresponding to the command
                        func(*args)
                    except AttributeError as err:#command invalid
                        pass

    def do_quit(self):
        if self.socket is not None:
            if self.socket.fileno() != -1:
                self.socket.close()
        sys.exit( )


if __name__ == '__main__':
    client=FTPClient()
    client.connect()