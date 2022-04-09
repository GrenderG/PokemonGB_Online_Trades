import socket
import threading
import select
from websocket_client import WebsocketClient
from time import sleep
from gsc_trading_strings import GSCTradingStrings

class P2PConnection (threading.Thread):
    """
    Class which handles sending/receiving from another client.
    """
    PACKET_SIZE_BYTES = 2048
    SLEEP_TIMER = 0.01
    REQ_INFO_POSITION = 0
    LEN_POSITION = 4
    DATA_POSITION = 6
    send_request = "S"
    get_request = "G"

    def __init__(self, menu, kill_function, host='localhost', port=0):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.verbose = menu.verbose
        self.host = host
        self.port = port
        self.room = menu.room
        self.to_send = None
        self.recv_dict = {}
        self.send_dict = {}
        self.kill_function = kill_function
        self.ws = WebsocketClient(menu.server[0], menu.server[1], kill_function)
    
    def prepare_send_data(self, type, data):
        return bytearray(list((P2PConnection.send_request + type).encode()) + [(len(data) >> 8) & 0xFF, len(data) & 0xFF] + data)
    
    def prepare_get_data(self, type):
        return bytearray(list((P2PConnection.get_request + type).encode()))
    
    def reset_dict(self, type, chosen_dict):
        if type in chosen_dict.keys():
            chosen_dict.pop(type)
    
    def reset_recv(self, type):
        self.reset_dict(type, self.recv_dict)
    
    def reset_send(self, type):
        self.reset_dict(type, self.send_dict)
    
    def send_data(self, type, data):
        """
        Sends the data to the other client and prepares the dict's entry
        for responding to GETs.
        """
        self.send_dict[type] = data
        self.to_send = self.prepare_send_data(type, data)
        while self.to_send is not None:
            sleep(P2PConnection.SLEEP_TIMER)
    
    def recv_data(self, type, reset=True):
        """
        Checks if the data has been received. If not, it issues a GET.
        """
        if not type in self.recv_dict.keys():
            self.to_send = self.prepare_get_data(type)
            while self.to_send is not None:
                sleep(P2PConnection.SLEEP_TIMER)
            return None
        else:
            if reset:
                return self.recv_dict.pop(type)
            return self.recv_dict[type]

    def run(self):
        """
        Does the initial connection, gets the peer's role (client or server)
        and then executes socket_conn for handling the rest.
        """
        is_client = False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        
            try:
                s.bind((self.host, self.port))
            except Exception as e:
                print(GSCTradingStrings.socket_error_str, str(e))
                self.kill_function()
                
            s.listen(1)
            real_port = int(s.getsockname()[1])
            if self.verbose:
                print(GSCTradingStrings.p2p_listening_str.format(host=self.host, port=real_port))
                
            response = self.ws.get_peer(self.host, real_port, self.room)
            if response.startswith("SERVER"):
                is_server = True
            else:
                other_host = response[6:].split(':')[0]
                other_port = int(response[6:].split(':')[1])
                is_server = False
            
            if is_server:
                #Get client's connection
                connection, client_addr = s.accept()
                if self.verbose:
                    print(GSCTradingStrings.p2p_server_str.format(host=client_addr[0], port=client_addr[1]))

                with connection:
                    self.socket_conn(connection)
            else:
                is_client = True
        
        if not is_server:            
            #Connect to the other client
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if self.verbose:
                    print(GSCTradingStrings.p2p_client_str.format(host=other_host, port=other_port))
                s.connect((other_host, other_port))
                self.socket_conn(s)
    
    def process_received_data(self, data, connection):
        """
        Processes the received data. If it's a send, it stores
        it inside of the received dict.
        If it's a get, it sends the requested data, if present
        inside the send dict.
        """
        req_info = data[P2PConnection.REQ_INFO_POSITION:P2PConnection.REQ_INFO_POSITION+4].decode()
        req_kind = req_info[0]
        req_type = req_info[1:4]
        if req_kind == P2PConnection.send_request:
            data_len = (data[P2PConnection.LEN_POSITION] << 8) + data[P2PConnection.LEN_POSITION+1]
            self.recv_dict[req_type] = list(data[P2PConnection.DATA_POSITION:P2PConnection.DATA_POSITION+data_len])
        elif req_kind == P2PConnection.get_request:
            if req_type in self.send_dict.keys():
                connection.send(self.prepare_send_data(req_type, self.send_dict[req_type]))
    
    def socket_conn(self, connection):
        """
        Handles both reading the received data and sending.
        """
        try:
            while True:
                ready_to_read, ready_to_write, in_error = \
                   select.select(
                      [connection],
                      [connection],
                      [],
                      0)
                if len(ready_to_read) > 0:
                    data = connection.recv(self.PACKET_SIZE_BYTES)
                    if not data:
                        print(GSCTradingStrings.connection_dropped_str)
                        break
                    self.process_received_data(data, connection)
                if len(ready_to_write) > 0 and self.to_send is not None:
                    connection.send(self.to_send)
                    self.to_send = None
                sleep(P2PConnection.SLEEP_TIMER)
                
        except Exception as e:
            print(GSCTradingStrings.socket_error_str, str(e))
            self.kill_function()