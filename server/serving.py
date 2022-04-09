#!/usr/bin/env python

import asyncio
import websockets
import threading
import signal
import os
from random import Random
from time import sleep
import ipaddress

link_rooms = {}

class WebsocketServer (threading.Thread):
    '''
    Class which handles responding to the websocket requests.
    '''
    
    def __init__(self, host="localhost", port=11111):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.host = host
        self.port = port

    async def link_function(websocket, data, path):
        '''
        Handler which either registers a client to a room, or links
        two clients together.
        Decides which one is the client and which one is the server in the
        P2P connection randomly.
        '''
        room = 100000
        if len(path) >= 11:
            room = int(path[6:11])
            valid = True
            try:
                ip = ipaddress.ip_address(data.split(":")[0])
            except ValueError:
                if data.split(":")[0] != "localhost":
                    valid = False
            if valid:
                if room not in link_rooms.keys():
                    link_rooms[room] = [data, websocket]
                else:
                    info = link_rooms.pop(room)
                    rnd = Random()
                    rnd.seed()
                    user = rnd.randint(0,1)
                    repl = ["SERVER", "CLIENT"]
                    if user == 0:
                        repl = ["CLIENT", "SERVER"]
                    reply_old = repl[0] + data
                    reply_new = repl[1] + info[0]
                    await info[1].send(reply_old)
                    await websocket.send(reply_new)
        return room

    async def handler(websocket, path):
        """
        Gets the data and then calls the proper handler while keeping
        the connection active.
        """
        curr_room = 100000
        while True:
            try:
                data = await websocket.recv()
            except websockets.ConnectionClosed:
                print(f"Terminated")
                if curr_room in link_rooms.keys():
                    link_rooms.pop(curr_room)
                break
            except Exception as e:
                print('Websocket server error:', str(e))
                if curr_room in link_rooms.keys():
                    link_rooms.pop(curr_room)

            if path.startswith("/link/"):
                curr_room = await WebsocketServer.link_function(websocket, data, path)

    def run(self):
        """
        Runs the server in a second Thread in order to keep
        the program responsive.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_server = websockets.serve(WebsocketServer.handler, self.host, self.port)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

def exit_gracefully():
    os._exit(1)

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    exit_gracefully()

ws = WebsocketServer()
ws.start()

signal.signal(signal.SIGINT, signal_handler)

while True:
    sleep(1)