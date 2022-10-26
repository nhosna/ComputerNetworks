import json



class ConfigFile:
    def __init__(self):
        # self.commandPort=None
        # self.dataPort=None
        # self.users=[]
        # self.accounting=[]
        self.get_config()

    def set_config(self,data):

        with open('config.json', 'w') as f:
            json.dump(data, f)
        self.data=data

    def get_config(self):
        with open('config.json') as json_file:
            self.data = json.load(json_file)
            # self.commandPort=self.data ["commandChannelPort"]
            # self.dataPort=self.data ["dataChannelPort"]
            # self.users=self.data ["users"]
            # self.accounting=self.data ["accounting"]
            # self.authorization=self.data ["authorization"]["enable"]
            # self.logging=self.data ["logging"]["enable"]
            # self.admins=self.data ["authorization"]["admins"]
            # self.adminFiles=self.data ["authorization"]["files"]

if __name__ == '__main__':
    config=ConfigFile()
    print(config.users)