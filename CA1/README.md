FTP Client Server
---

1)Gmail's SMTP service is used to send email to clients so set 


    MAILPWD = "<google-password>"
    MAILSENDER = "<google-email>"
    
in constants.py

*Don't forget to change your google account's security settings to allow 3'rd
party apps to use its mail service

2) client connects to CommandChannelPort specified in config.json

Usage
--
    python server.py
    python client.py <command-port>






