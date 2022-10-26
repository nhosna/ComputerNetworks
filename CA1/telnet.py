import base64,  socket, ssl

class EmailClient:
    def __init__(self,server,port,sender,password):
        self.server=server
        self.port=port
        self.sender=sender
        self.password=password


    def connect(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sockssl = ssl.wrap_socket(self.s)
        self.sockssl.connect((self.server, self.port))
        respon = self.sockssl.recv(2048)

    def hello(self):
        heloMesg = 'HELO hosna\r\n'
        self.sockssl.send(heloMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)

    def login(self):
        authMesg = 'AUTH LOGIN\r\n'
        crlfMesg = '\r\n'
        self.sockssl.send(authMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        user64 = base64.b64encode(self.sender.encode('utf-8'))
        pass64 = base64.b64encode(self.password.encode('utf-8'))
        self.sockssl.send(user64)
        self.sockssl.send(crlfMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        self.sockssl.send(pass64)
        self.sockssl.send(crlfMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
    def email(self,receiver,message):
        fromMesg = 'MAIL FROM: <' + self.sender + '>\r\n'
        self.sockssl.send(fromMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        # Tell server the message's recipient
        rcptMesg = 'RCPT TO: <' + receiver + '>\r\n'
        self.sockssl.send(rcptMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        # Give server the subject
        dataMesg = 'DATA\r\n'
        self.sockssl.send(dataMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)

        mailbody = message + '\r\n'
        self.sockssl.send(mailbody.encode('utf-8'))
        fullStop = '\r\n.\r\n'
        self.sockssl.send(fullStop.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        # Signal the server to quit
        quitMesg = 'QUIT\r\n'
        self.sockssl.send(quitMesg.encode('utf-8'))
        respon = self.sockssl.recv(2048)
        # Close the socket to finish
        self.sockssl.close()

    def send_mail(self,receiver,message):
        self.connect()
        self.hello()
        self.login()
        self.email(receiver,message)

