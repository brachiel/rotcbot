import struct
import select
import time

from socket import *

MASTER_SERVER = "74.63.12.22:28002"
KEY = 0

def _str_to_bin(string):
    return chr(len(string)) + string

def _extract_str(data):
    i = ord(data[0])+1
    string = data[1:i]
    return string, data[i:]

def _wait_for_socket(sock):
    #try:
    #    reader = select.poll()
    #    reader.register(sock)

    #    ret = reader.poll(2000)
    #    return ret # may return None
    #except AttributeError:  # OS doesn't support select.poll

    inlist, outlist, errlist = select.select([ sock ], [], [], 2)
    return len(inlist)

def _build_header(packet_type):
    global KEY
    session = 1
    KEY += 1
    flags = 2 # NoStringCompress

    session_key = ( (session << 16) | (KEY & 0xFFFF) )

    return struct.pack('<BBI', packet_type, flags, session_key)


def getServerList(game_type='rotc-ethernet', mission_type='Any'):
    """Gets a list of the running rotc servers, and calls callback with the list as an argument."""
    global MASTER_SERVER
    global KEY

    server_list = None
    session = 1
    KEY += 1
    session_key = ( session << 16 | KEY & 0xFFFF )
    flags = 2 # NoStringCompress

    # Set the socket parameters
    (host, port) = MASTER_SERVER.split(':')
    port = int(port)
    addr = (host, port)

    header = _build_header(6) # GetServerList
    filters = struct.pack('<BBIIBBhB', 
            0, #minPlayers
            64, #maxPlayers
            2, #regionMask
            0, #version
            0, #filterFlags
            0, #maxBots
            0, #minCPU
            0, #buddyCount
            )
    SERVER_LIST_REQUEST = ''.join([header, "\xff", # header and separator
                          _str_to_bin(game_type),  # game type 
                          _str_to_bin(mission_type),  # mission type
                          filters ]) 

    # Create socket
    UDPSock = socket(AF_INET,SOCK_DGRAM)
    UDPSock.sendto(SERVER_LIST_REQUEST, addr)

    # read messages



    server_list = []
    numPacketsRecvd = 0
    while 1:
        ready = _wait_for_socket(UDPSock)
        if not ready:
            print "Server didn't answer in time."
            break

        data = UDPSock.recv(1024)

        if not data:
            continue

        packetType = struct.unpack("!B",data[0])[0]

        if packetType == 8:
            numPacketsRecvd += 1
            try:
                unpacked = struct.unpack('<BBIBBH', data[0:10])
                data = data[4:] # will be shifted again later
            except struct.error:
                print "ERROR while unpacking! The master server sent an uncompatible server information - this server will be ignored."
                continue           
#BBBBH', data)

            key, packetIndex, packetTotal, numServers = unpacked[2:6]
            for i in range(numServers):
                data = data[6:]
                unpacked = struct.unpack('<BBBBH', data[0:6])

                ip = '.'.join([ str(x) for x in unpacked[0:4] ])
                port = unpacked[4]

                server_list.append("%s:%s" % (ip, port))

            if numPacketsRecvd >= packetTotal:
                break

    # Close socket
    UDPSock.close()

    return server_list

def pingServer(ip):
    global KEY

    serverinfo = dict()

    (host, port) = ip.split(':')
    port = int(port)
    addr = (host, port)

    SERVER_PING = _build_header(14) # GamePingRequest

    UDPSock = socket(AF_INET, SOCK_DGRAM)
    a = time.time()
    UDPSock.sendto(SERVER_PING, addr)

    ready = _wait_for_socket(UDPSock)
    b = time.time()
    if not ready:
        print "Server didn't answer"
        return None
    ping = int((b-a)*1000)

    data = UDPSock.recv(1024)

    packet_type, flags, key = struct.unpack('<BBI', data[0:6])
    data = data[6:]

    protocolVersion, data = _extract_str(data) # should be VER1

    unpacked = struct.unpack('<III', data[0:12]) # version numbers
    data = data[12:]

    serverName, data = _extract_str(data)

    return { 'server_name': serverName, 'ping': ping }



def getServerDetails(ip):
    global KEY

    serverinfo = dict()

    (host, port) = ip.split(':')
    port = int(port)
    addr = (host, port)

    SERVER_QUERY = _build_header(18) # GameInfoRequest

    UDPSock = socket(AF_INET,SOCK_DGRAM)
    UDPSock.sendto(SERVER_QUERY, addr)

    ready = _wait_for_socket(UDPSock)
    if not ready:
        print "Server didn't answer in time"
        UDPSock.close()
        return None

    data = UDPSock.recv(1024)

    packet_type, flags, key = struct.unpack('<BBI', data[0:6])

    # get the strings
    serverinfo['game_type']       , data = _extract_str(data[6:])
    serverinfo['game_version']    , data = _extract_str(data)
    serverinfo['mission_type']    , data = _extract_str(data)
    dummy , data = _extract_str(data) # don't know why this is necessary
    serverinfo['mission_name']    , data = _extract_str(data)
    serverinfo['mission_homepage'], data = _extract_str(data)

    serverinfo['status'], serverinfo['player_count'], serverinfo['max_players'], \
    serverinfo['bot_count'], serverinfo['server_cpu'] = struct.unpack('<BBBBh', data[0:6])

    serverinfo['server_info'], data = _extract_str(data[6:])

    return serverinfo

#print getServerList()
#print pingServer("84.23.68.56:28000")
#print getServerDetails("84.23.68.56:28000")

