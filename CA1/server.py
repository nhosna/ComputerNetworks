# !/usr/bin/env python
# --*-- coding: utf-8 --*--

import socket
import os

from os import listdir
from os.path import isfile, join


import signal
import sys
from config import ConfigFile
from telnet  import EmailClient
import shutil

import logging
import threading
import time
from constants import *
BUFSIZE = 1024

configlock = threading.Lock()

FORMAT = '[%(asctime)s] (%(threadName)-10s) %(message)s'

logging.basicConfig(level=logging.DEBUG,
                    format=FORMAT)



MAILMSGCONTENT = "You have reached your threshold limit."



def signal_handler(sig, frame):
    listen_sock.close()
    log('Server stop', 'Server closed')
    sys.exit()


signal.signal(signal.SIGINT, signal_handler)

def fileProperty(filepath):
    fileMessage = []
    fileMessage.append(os.path.basename(filepath))
    return ' '.join(fileMessage)

try:
    HOST = socket.gethostbyname(socket.gethostname())
except socket.gaierror:
    HOST = '127.0.0.1'
CWD = os.getenv('HOME')

def log(func, cmd):
    logmsg = time.strftime("%Y-%m-%d %H-%M-%S [-] " + func)
    # print("\033[31m%s\033[0m: \033[32m%s\033[0m" % (logmsg, cmd))
    print("{}:{}".format(logmsg, cmd))

#logs to log file
def logg(func,cmd):
    logging.info("{}:{}".format(func, cmd))

class ServerThread(threading.Thread):
    def __init__(self, commSock, data_sock, address, config):
        threading.Thread.__init__(self)
        self.authenticated = False
        self.cwd = CWD
        self.commSock = commSock  # communication socket as command channel
        self.address = address
        self.config = config
        self.data_sock = data_sock  # the same instance of sock is passed to every server thread to accept data connections on that port
        self.mailserver = "smtp.gmail.com"
        self.mailport = 465
        self.mailsender = MAILSENDER
        self.mailpassword = MAILPWD


    def close_data_sock(self):
        try:
            data = self.dataSock.recv(BUFSIZE).rstrip()
            try:
                cmd = data.decode('utf-8')
            except AttributeError:
                cmd = data
            if not cmd:  # when client closes connection
                self.stop_data_sock()
            else:
                print(cmd)
        except socket.error as err:  # connection closed by peer
            log('Receive', err)
            self.stop_data_sock()

    def check_username_password(self, username, password):
        for user in self.config.data["users"]:
            if (user["user"] == username):
                if (user["password"] == password):
                    return True
                else:
                    return False

        return False

    def send_alert(self, user):
        ##TODO implement this
        if (user["alert"] == True):
            print("sending alert email")
            mail = EmailClient(self.mailserver, self.mailport, self.mailsender, self.mailpassword)
            mail.send_mail(user['email'], MAILMSGCONTENT)
            logg('DL', 'Sent alert email to user {} at email {}'.format(self.username, user['email']))

    def check_user_threshold(self):
        for user in self.config.data["accounting"]["users"]:
            if (user["user"] == self.username):
                if (int(user["size"]) < int(self.config.data["accounting"]["threshold"])):
                    logg("DL","User {}'s download size has reached threshold".format(self.username))
                    self.send_alert(user)
                    return

    def check_admin_rights(self, filename):
        filename = "./" + filename
        if (self.config.data["authorization"]["enable"]):
            if self.username not in self.config.data["authorization"]["admins"] and filename in \
                    self.config.data["authorization"]["files"]:
                return False

            return True

    def check_user_limit(self, filesize):
        for user in self.config.data["accounting"]["users"]:
            if (user["user"] == self.username):
                downloadLimit = int(user["size"])
                if (downloadLimit < filesize):  # user doesnt have threshold so return user dict
                    return False
                else:
                    user["size"] = str(downloadLimit - filesize)  # user can proceed with download
                    self.update_config()
                    return True

    def update_config(self):
        configlock.acquire()
        self.config.set_config(self.config.data)
        configlock.release()

    def run(self):

        self.send_welcome()
        while True:
            try:
                data = self.commSock.recv(BUFSIZE).rstrip()
                try:
                    cmd = data.decode('utf-8')
                except AttributeError:
                    cmd = data
                log('Received data', cmd)
                if not cmd:
                    "after sending 221 to client, client closes socket first then server closes client's commSock"
                    logg('Server','Client at {} {} quitted.'.format(self.address,self.commSock))
                    self.commSock.close()
                    break
            except socket.error as err:
                log('Receive', err)
                self.commSock.close()
                break
            try:
                splitted = cmd.split(" ")
                cmd, args = splitted[0], splitted[1:] if len(splitted) > 1 else []
                func = getattr(self, cmd)  ##call the function corresponding to the command
                func(*args)

            except AttributeError as err:
                self.send_command('500 Error \r\n')
                log('Receive', err)

    def start_data_sock(self):
        log('startDataSock', 'Opening a data channel')
        self.dataSock, self.address = self.data_sock.accept()

    def stop_data_sock(self):
        log('stopDataSock', 'Closing data channel')
        try:
            self.dataSock.close()
        except socket.error as err:
           log('stopDataSock', err)

    def send_command(self, cmd):
        self.commSock.send(cmd.encode('utf-8'))

    def send_data(self, data):
        self.dataSock.send(data.encode('utf-8'))

    def USER(self, *args):
        if (len(args) != 1):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return
        user = args[0]
        log("USER", user)
        self.send_command('331 User name okay, need password.\r\n')
        self.username = user

    def PASS(self, *args):
        if (len(args) != 1):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return
        passwd = args[0]
        log("PASS", passwd)

        if not self.username:
            self.send_command('503 Bad sequence of commands.\r\n')

        elif not self.check_username_password(self.username, passwd):
            self.send_command('‫‪430‬‬ ‫‪Invalid‬‬ ‫‪username‬‬ ‫‪or‬‬ ‫‪password. ‬\r\n')
            self.username = None
        else:
            self.send_command('230 User logged in, proceed.\r\n')
            self.authenticated = True
            logg('AUTH',"User {} logged in".format(self.username))

    def LIST(self, *args):
        if (len(args) != 0):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return

        if not self.authenticated:
            self.send_command("332 Need account for login.\r\n")
            return
        pathname = self.cwd

        self.send_command('150 Here is listing.\r\n')
        self.dataSock, address = self.data_sock.accept()

        # TODO what is if and else?

        if not os.path.isdir(pathname):
            fileMessage = fileProperty(pathname)
            self.dataSock.sock(fileMessage + '\r\n')

        else:
            onlyfiles = [f for f in listdir(pathname) if isfile(join(pathname, f))]
            for file in onlyfiles:
                fileMessage = file
                self.send_data(fileMessage + '\r\n')
        self.send_command('‫‪226‬‬ ‫‪List‬‬ ‫‪transfer‬‬ ‫‪done.\r\n')

        self.close_data_sock()
        logg('LIST', "User {} received list at {}".format(self.username,pathname))


    def PSV(self, *args):
        self.send_command("PSV {}\r\n".format(self.config.data["dataChannelPort"]))

    def DL(self, *args):
        if (len(args) != 1):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return

        if not self.authenticated:
            self.send_command("332 Need account for login.\r\n")
            return
        file_name = args[0]

        file_location = os.path.join(self.cwd, file_name)
        if not os.path.exists(file_location):
            self.send_command('550 DL failed File %s not exists.\r\n' % file_location)
            return
        try:
            file_size = os.path.getsize(file_location)

            if not (self.check_user_limit(
                    file_size)):  # checks user limit if user can download update and return True else return False
                self.send_command("‫‪425‬‬ ‫‪Can't‬‬ ‫‪open‬‬ ‫‪data‬‬ ‫‪connection.\r\n")
                return
            if not (self.check_admin_rights(file_name)):
                self.send_command(
                    "‫‪550‬‬ ‫‪File‬‬ ‫‪unavailable.\r\n")  # todo check to see if another error code for this exits
                logg("DL","Unauthorized user {} attempted to download {}".format(self.username,file_location))
                return
            if not os.path.exists(file_location):
                return
            try:
                file = open(file_location, 'r')
            except OSError as err:
                log('DL', err)
                return
        except IOError:

            self.send_command("‫‪550‬‬ ‫‪File‬‬ ‫‪unavailable.\r\n")
            return

        self.send_command('150 Opening data connection.\r\n')
        self.dataSock, address = self.data_sock.accept()

        while True:
            data = file.read(BUFSIZE)
            if not data: break
            self.send_data(data)
        file.close()
        self.send_command('226 Transfer complete.\r\n')
        self.check_user_threshold()  # checks user threshold and sends email if needed

        "close dataSock only after client closes first"
        self.close_data_sock()
        logg('DL',"User {} downloaded {} with size {}.".format(self.username,file_location,file_size))


    def CWD(self, *args):
        if (len(args) > 1):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return

        if not self.authenticated:
            self.send_command("332 Need account for login.\r\n")
            return
        if len(args) == 0:
            self.cwd = os.getenv('HOME')
        else:

            dirpath = args[0]
            if (dirpath == '..'):
                self.cwd = os.path.abspath(os.path.join(self.cwd, '..'))
            else:
                if (dirpath[0:2] == "./"):
                    dirpath = dirpath[2:]
                pathname = dirpath.endswith(os.path.sep) and dirpath or os.path.join(self.cwd, dirpath)
                log('CWD', pathname)
                if not os.path.exists(pathname) or not os.path.isdir(pathname):
                    self.send_command('550 CWD failed Directory not exists.\r\n')
                    return
                self.cwd = pathname
        self.send_command('‫‪250‬‬ ‫‪Successful‬‬ ‫‪Change. ‬\r\n')

    def PWD(self, *args):
        if (len(args) != 0):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return

        if not self.authenticated:
            self.send_command("332 Need account for login.\r\n")
            return
        log('PWD', "{}".format(self.cwd))
        self.send_command('257 "%s".\r\n' % self.cwd)

    def MKD(self, *args):

        if not (len(args)==1 or (len(args) == 2 and args[0] == '-i')):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return
        if not self.authenticated:
            self.send_command(  "332 Need account for login.\r\n")
            return
        if (len(args) == 1):  # create directory
            dirname = args[0]
            pathname = dirname.endswith(os.path.sep) and dirname or os.path.join(self.cwd, dirname)
            log('MKD', pathname)
            try:
                os.mkdir(pathname)
                self.send_command('257 {} created.\r\n'.format(pathname))
                logg("MKD","User {} created directory {}".format(self.username,pathname))
            except OSError:
                self.send_command('550 MKD failed Directory "%s" already exists.\r\n' % pathname)
        elif (len(args) == 2 and args[0] == '-i'):  # create new file
            dirname = args[1]
            pathname = dirname.endswith(os.path.sep) and dirname or os.path.join(self.cwd, dirname)

            try:
                fd = os.open(pathname, os.O_CREAT)
                os.close(fd)
                self.send_command('257 {} created.\r\n'.format(dirname))
                logg("MKD","User {} created file {}".format(self.username,pathname))

            except OSError:
                self.send_command('550 MKD failed Directory "%s" already exists.\r\n' % pathname)


    def RMD(self, *args):
        if not (len(args) == 1 or (len(args) == 2 and args[0] == '-f')):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return
        if not self.authenticated:
            self.send_command("332 Need account for login.\r\n")
            return
        if (len(args) == 1):
            dirname = args[0]
            pathname = dirname.endswith(os.path.sep) and dirname or os.path.join(self.cwd, dirname)
            log('RMD', pathname)
            # TODO doesnt work when file doesnt exist remove
            if not os.path.exists(pathname):
                self.send_command('550 RMDIR failed File "%s" not exists.\r\n' % pathname)
            else:
                try:
                    os.remove(pathname)
                    self.send_command('250 {} deleted.\r\n'.format(dirname))
                    logg("MKD", "User {} deleted file {}".format(self.username, pathname))

                except OSError:
                    self.send_command('550 RMDIR failed File "%s" not exists.\r\n' % pathname)

        elif (len(args) == 2 and args[0] == '-f'):  # remove directory
            dirname = args[1]
            pathname = dirname.endswith(os.path.sep) and dirname or os.path.join(self.cwd, dirname)
            log('RMD', pathname)
            # TODO doesnt work when file doesnt exist remove
            if not os.path.exists(pathname):
                self.send_command('550 RMDIR failed Directory "%s" not exists.\r\n' % pathname)

            else:
                try:
                    shutil.rmtree(pathname)
                    self.send_command('250 {} deleted.\r\n'.format(pathname))
                    logg("MKD", "User {} deleted directory {}".format(self.username, pathname))

                except OSError:
                    self.send_command('550 RMDIR failed Directory "%s" not exists.\r\n' % pathname)


    def HELP(self, *args):
        if (len(args) != 0):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return

        help = """
USER <name>, username for authentication.
PASS <password>, password for authentication
PWD , display current directory
MKD [-i] <name> , create a new file/directory
RMD [-f] <name>, remove a file/directory
LIST ,list files in directory
CWD <path> , change current dir
DL <name> ,download file from server
HELP , displays help information.
QUIT .terminate client session       
\r\n
            """
        self.send_command(help)

    def QUIT(self, *args):
        if (len(args) != 0):
            self.send_command('501 Syntax error in parameters or arguments.\r\n')
            return
        log('QUIT', '{} {}'.format(self.address,self.commSock))
        self.send_command('221 Successful Quit \r\n')


    def send_welcome(self):
        self.send_command('220 Welcome.\r\n')


def serverListener():
    global listen_sock
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    global data_sock
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


    config = ConfigFile()

    if (config.data['logging']['enable']):
        path = config.data['logging']['path']
        file_handler = logging.FileHandler(path)
        file_handler.setFormatter(logging.Formatter(FORMAT))
        logging.getLogger().addHandler(file_handler)


    #listen on the datachannel port and commandchannel port specified by config
    listen_sock.bind((HOST, config.data["commandChannelPort"]))
    listen_sock.listen(5)
    data_sock.bind((HOST, config.data["dataChannelPort"]))
    data_sock.listen(5)

    log('Server started', 'Listen on: %s, %s' % listen_sock.getsockname())
    logg('Server started', 'Listen on: %s, %s' % listen_sock.getsockname())
    while True:
        connection, address = listen_sock.accept()
        f = ServerThread(connection, data_sock, address, config)  ##create a new thread for each user conn
        f.start()
        log('Accept', 'Created a new connection {} ,{}  '.format(address, connection))
        logg('Accept', 'Created a new connection {} ,{}  '.format(address, connection))


if __name__ == "__main__":
    log('Start ftp server', 'Enter q or Q to stop ftpServer...')
    listener = threading.Thread(target=serverListener)
    serverListener()
    listener.start()

    if input().lower() == "q":
        listen_sock.close()
        log('Server stop', 'Server closed')
        sys.exit()
