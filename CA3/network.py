import multiprocessing
import random
import time
from datetime import datetime, timedelta

from  constants import ID_OFFSET, K, RUNTIME, PAUSE_EVERY, PAUSE_DURATION
from  p2p import Node

from  util import log



def initialize_nodes_proc ():
    pause_queue = multiprocessing.JoinableQueue()


    nodes = [Node(pause_queue,i)
                 for i in range(K)]
    for n in nodes:
        n.start()


    awake_nodes=set(list(range(K)))
    to_be_woken={0:0,1:0}
    turn=0

    "send the process id to be paused to all processes"

    starttime=datetime.now()
    while(datetime.now()-starttime<timedelta(seconds=RUNTIME)):

        time.sleep(PAUSE_EVERY)

        awake_nodes.add(to_be_woken[turn])
        r = random.choice(list(awake_nodes))
        # log("2: added {} back next turn is {}".format(to_be_woken[turn],to_be_woken[(turn + 1) % 2]))
        to_be_woken[turn] = r
        turn = (turn + 1) % 2
        awake_nodes.remove(r)

        log("main: proc paused :{}".format(r))

        for i in range(K):
            pause_queue.put(r)


    # Add a poison pill for each node
    for i in range(K):
        pause_queue.put(None)



if __name__ == '__main__':
    initialize_nodes_proc ()

