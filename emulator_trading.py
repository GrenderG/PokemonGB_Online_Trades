#!/usr/bin/python3
from bgb_link_cable_server import BGBLinkCableServer
from time import sleep
from gsc_trading import GSCTrading

class PokeTrader:
    SLEEP_TIMER = 0.001

    def __init__(self):
        self.curr_recv = None
        self._server = BGBLinkCableServer(self.update_data, verbose=False, )

    def run(self):
        self._server.start()
        
    def update_data(self, data):
        self.curr_recv = data

    # Code dependant on this connection method
    def sendByte(self, byte_to_send):
        self._server.to_send = byte_to_send
        while self._server.to_send is not None:
            sleep(self.SLEEP_TIMER)
        return

    def receiveByte(self):
        while self.curr_recv is None:
            sleep(self.SLEEP_TIMER)
        recv = self.curr_recv
        self.curr_recv = None
        return recv


def transfer_func(p):
    print("Waiting for the transfer to start...")
    
    trade_c = GSCTrading(p.sendByte, p.receiveByte, target_other = "usb.bin", target_self = "emu.bin")
    res = trade_c.trade() # Read the starting information
    
    return

p = PokeTrader()
p.run()
transfer_func(p)