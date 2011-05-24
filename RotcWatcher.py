# vim: set tabstop=4 expandtab sw=4:

import urllib
import string

import MasterServer

class Watcher(object):
    def __init__(self):
        self.server_info = dict()

    def update_server_list(self):
        server_list = MasterServer.getServerList()
        if not server_list: # Master server didn't answer
            return None

        for addr in server_list:
            if addr not in self.server_info:
                self.server_info[addr] = dict() # new server
                self.server_info[addr]['new'] = True

        for addr in self.server_info.keys():
            self.update_server(addr)

    def update_server(self, addr):
        ping = MasterServer.pingServer(addr)
        if not ping:
            if addr in self.server_info:
                delete = True
                if 'new' not in self.server_info[addr]:
                    self.callback_server_noping(addr)
                else:
                    del(self.server_info[addr])
            return False

        details = MasterServer.getServerDetails(addr)
        if not details:
            if addr in self.server_info:
                if 'new' not in self.server_info[addr]:
                    self.callback_server_close(addr)

                del(self.server_info[addr])
            return False

        for key, val in ping.items() + details.items():
            if key in self.server_info[addr]:
                oldval = self.server_info[addr][key]

                if oldval != val:
                    self.callback_detail_change(addr, key, oldval, val)

            self.server_info[addr][key] = val

        if 'new' in self.server_info[addr].keys():
            self.callback_new_server(addr)
            del(self.server_info[addr]['new'])

        return self.server_info[addr]

    def get_server_list(self):
        """Get the server list from the server watcher and return a list of
           tuples containing (addr, #player, name)."""

        self.update_server_list()
        server_list = []
        for addr, details in self.server_info.items():
            server_list.append((addr, details['player_count'], details['server_name']))
        return server_list

    def get_server_details(self, addr):
        return self.update_server(addr)

    def callback_server_noping(self, addr, server_details=None):
        if 'no_ping' in self.server_info[addr]:
            self.server_info[addr]['no_ping'] += 1
        else:
            self.server_info[addr]['no_ping'] = 1

        if self.server_info[addr]['no_ping'] > 5:
            self.callback_server_close(addr, server_details)
            del(self.server_info[addr])

    def callback_server_close(self, addr, server_details=None):
        pass

    def callback_detail_change(self, addr, key, old_val=None, new_val=None):
        pass

    def callback_new_server(self, addr, server_details=None):
        pass



