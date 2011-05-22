#!/usr/bin/python
# vim: set expandtab tabstop=4

"""A jabber bot that scans the TGE master server for games and annouces them."""

__author__ = 'Wanja Chresta <wanja dot chresta at gmail dot com>'
__version__ = '0.1'
__website__ = 'http://github.com/brachiel/rotcbot'
__license__ = 'GPLv3 or later'


from jabberbot import JabberBot, botcmd
from RotcWatcher import Watcher
import xmpp
import time
import os    # just needed to get the HOME variable

test = False

class RotcBot(JabberBot):
    def __init__(self, jid, password, res="main", debug=False):
        JabberBot.__init__(self, jid, password, res, debug)
        self.w = Watcher()
        self.server_ids = []       # enumerate keys of server_list
        self.last_rotc_update = 0

        self.roster = None

        self.EVENTS = { 'new_game': 'The first player joins a server.',
                        'game_close': 'The last player leaves a server, or a server which had players is closed.',
                        'player_change': 'A change in player numbers on a server.',
                        'new_server': 'A new server was created (any number of players, even 0).',
                        'server_close': 'A server was closed (even if it had no players)' }

    @botcmd(hidden=True)
    def l(self, mess, args):
        return self.list(mess, args)
    @botcmd
    def list(self, mess, args):
        """Displays the list of open rotc servers. Alias: l"""
        if len(self.server_ids) == 0:
            return "There are no open rotc servers. Maybe you want to host one?"

        retn = ["List of open rotc ethernet servers:"]

        for i in range(len(self.server_ids)):
            addr = self.server_ids[i]
            try:
                name = self.w.server_info[addr]['server_name']
                players = self.w.server_info[addr]['player_count']
                map = self.w.server_info[addr]['mission_name']

                retn.append("[%i] %s has %s players" % (i, name, players))
            except KeyError:
                retn.append("[%i] %s is in an unknown state" % (i, addr))

        return '\n'.join(retn)

    @botcmd(hidden=True)
    def d(self, mess, args):
        return self.details(mess, args)
    @botcmd
    def details(self, mess, args):
        """Displays the details of a given rotc server. Alias: d"""
        if args in self.server_ids:
            addr = args
            det = self.w.get_server_details(addr)
        else:
            try:
                i = int(args)
            except ValueError:
                return "Unknown id. Enter either id from list or IP"

            if i < len(self.server_ids) and self.server_ids[i] != None:
                addr = self.server_ids[i]
                det = self.w.get_server_details(addr)
            else:
                return "There is no server with this id."

        retn = ["Details for rotc ethernet server with address %s:" % addr]
        for key, value in det.items():
            retn.append("%s: %s" % (key, value))

        return '\n'.join(retn)

    @botcmd(hidden=True)
    def broadcast(self, mess, args):
        """ADMIN - broadcast a message to all users of rotcbot."""
        jid = self.get_jid(mess)

        if jid == control_room:
            self._broadcast(''.join(args))
        else:
            self.error("User %s wanted to broadcast, but he's not in the control room" % jid)

    @botcmd(hidden=True)
    def msg(self, mess, args):
        """sends a message to a jid."""
        jid = self.get_jid(mess)

        if jid == control_room:
            try:
                target, msg = args.split(' ', 1)

                self.send(target, msg)
            except ValueError:
                self.error("The correct format is: send jid message")
        else:
            self.error("User %s wanted to use msg, but he's not in the control room" % jid)

    @botcmd(hidden=True)
    def restart(self, mess, args):
        jid = self.get_jid(mess)

        if jid == control_room:
            self.quit() # we will be restarted by the supervisor
        else:
            self.error("User %s wanted to use restart, but he's not in the control room" % jid)

    @botcmd(hidden=True)
    def shutdown(self, mess=None, args=None):
        if mess is None and args is None:
            JabberBot.shutdown(self)
            return
            
        jid = self.get_jid(mess)

        if jid == control_room:
            self.log("Bang, Bang, %s shot me down, bang bang..." % jid)
            raise Exception("Shutdown rotcbot")
        else:
            self.error("User %s wanted to shutdown rotbot, but he's not in the control room" % jid)

    @botcmd(hidden=True)
    def show_contacts(self, mess, args):
        jid = self.get_jid(mess)

        if jid == control_room:
            contacts = "List of all users:\n"
            for contact in self.roster.getItems():
                try:
                    groups = self.roster.getGroups(contact)
                except e:
                    groups = "ERR " + str(e)
                contacts += '> %s - %s\n' % (str(contact), groups) 
            #self.send(control_room, contacts, message_type='groupchat')
            self.log(contacts)
        else:
            self.error("User %s wanted to use show_contacts, but he's not in the control room" % jid)


        

    #@botcmd
    #def raise_error(self, mess, args):
    #    """Tells the bot to die"""
    #    
    #    raise Exception('killed', mess)

##########################################################
    def send_simple_reply(self, mess, text, private=True):
        """Send a simple response to a message"""
        self.send_message( self.build_reply(mess,text, private) )

    def idle_proc(self):
        if self.last_rotc_update + 7 < int(time.time()):
            self._build_server_list()
            self.last_rotc_update = int(time.time())

    def _build_server_list(self):
        self.w.update_server_list()

        # after this is called, the RotcWatcher module will call RotcWatcher.callback_* functions which must be connected to functions that do something
        #print "I",self.w.server_info
        server_list = [ x for x,y in self.w.server_info.items() if 'new' not in y.keys() ]
        #print "L",server_list

        # update the id-list of servers to use with the "list" command
        new_ids = [None,] * len(self.server_ids) # presume all the servers are gone
        for addr in server_list:
            if addr in self.server_ids:
                i = self.server_ids.index(addr)
                new_ids[i] = addr
            else:
                new_ids.append(addr)

        self.server_ids = new_ids

    @botcmd(hidden=True)
    def s(self, mess, args):
        return self.show_events(mess, args)
    @botcmd(hidden=True)
    def show(self, mess, args):
        """Same as show_events."""
        return self.show_events(mess, args)

    @botcmd
    def show_events(self, mess, args):
        """Shows the events you've subscribed. Aliases: s, show"""
        jid = self.get_jid(mess)

        try:
            groups = self.getGroups(jid)
        except:
            print self.roster._data.keys()
            raise

        if len(groups) == 0:
            return "You haven't subscribed any events. To do so, use sub_event"
       
        msg = []
        for event,desc in self.EVENTS.items():
            if event in groups:
                msg.append('%s - %s' % (event, desc))
        return "The events you've currently subscribed:\n" + '\n'.join(msg)

    @botcmd(hidden=True)
    def sub(self, mess, args):
        """Same as sub_event."""
        return self.sub_event(mess, args)

    @botcmd
    def sub_event(self, mess, args):
        """Subscribe an event (new_game, game_close, player_change, new_server, server_close). Aliases: sub"""
        jid = self.get_jid(mess)

        if args not in self.EVENTS.keys():
            return "%s is not a valid event. Possibilities are: %s" % (args, ', '.join(self.EVENTS.keys()))

        groups = self.getGroups(jid)
        if args not in groups:
            groups.append(args)

            self.roster.setItem(jid, groups=groups)
            self.log("%s subscribed to %s" % (jid, args))

            return "You have subscribed to the %s event" % args
        else:
            return "You've already subscribed to the %s event. Nothing changed." % args


    @botcmd(hidden=True)
    def un(self, mess, args):
        return self.unsub_event(mess, args)
    @botcmd(hidden=True)
    def unsub(self, mess, args):
        """Same as unsub_event."""
        return self.unsub_event(mess, args)

    @botcmd
    def unsub_event(self, mess, args):
        """Unsubscribe an event. Aliases: un, unsub"""
        jid = self.get_jid(mess)

        groups = self.getGroups(jid)

#        if args not in self.EVENTS.keys():
#            return "%s is not a valid event. Possibilities are: %s" % (args, ', '.join(self.EVENTS.keys()))

        if args not in groups:
            return "You are not subscribed to the event '%s'" % args

        while args in groups:
            groups.remove(args)

        self.roster.setItem(jid, groups=groups)
        self.log("%s unsubscribed from %s" % (jid, args))

        return "You've been unsubscribed to the event '%s'" % args
    
    def getGroups(self, jid):
        if not self.roster.getItem(jid):
            return []
        else:
            return self.roster.getGroups(jid)

    def get_jid(self, mess):
        global irc, irc_transport, irc_server

        type = mess.getType()
        jid = mess.getFrom()

        if irc and irc_transport and jid.getDomain() == irc_transport:
            type = 'irc'

        print "Get JID: %s %s: " % (str(jid), type),

        if type == 'groupchat':
            jid = jid.getStripped()

        elif type == 'irc':
            node = jid.getNode().split('%') # split IRC server from chan name
            if len(node) >= 2 and node[0][0] == '#': # is channel -> converting to user
                jid.setNode("%s%%%s" % (jid.getResource(), irc_server))
                jid = jid.getStripped()
            else: # is user
                jid.setNode("%s%%%s" % (node[0], irc_server))
                jid = jid.getStripped()

        else: # normal jabber chat
            jid = jid.getStripped()

        print str(jid)
        return jid
            
    def _broadcast(self, msg):
        self._broadcast_event(None, msg)

    def _broadcast_event(self, event, msg):

        #for jid in self.roster.getItems():

        # build a list of unique jids
        jid_status = {}
        for jid, (show, status) in self._JabberBot__seen.items():
            jid = str(jid)
            jid = jid[: (jid + '/').find('/')]
#        for jid in self.roster.getItems():
#            show = self.roster.getStatus(jid)
#            jid = str(self.roster.getRawItem(jid)) # stripped
#            jid = str(jid)

            if show is self.AVAILABLE:
                jid_status[jid] = show

        for jid in jid_status.keys():
            groups = self.getGroups(jid)
            if groups and (event == None or event in groups): # None is broadcast to all
                print "%s: %s < %s" % (event, jid, msg)
                self.send(jid, msg, message_type='chat')

#            level = self.notice_level[jid]
#        for jid, level in self.notice_level.items():
#            if show is self.AVAILABLE:
#            if level >= min_level:
#                self.send(jid, msg, message_type='chat')

    def _announce_player_change(self, addr, from_players, to_players):
        if addr not in self.w.server_info:
            return

        name = self.w.server_info[addr]['server_name']

        msg = "Server '%s' has now %s player(s)" % (name, to_players)

        print "Server '%s' went from %s players to %s players." % (name, from_players, to_players)

        self._broadcast_event('player_change', msg)
        if from_players == 0 and to_players >= 1: # first player joins
            self._broadcast_event('new_game', msg)
        elif from_players >= 1 and to_players == 0: # last player leaves
            self._broadcast_event('game_close', msg)

    def _announce_new_server(self, addr):
        if addr not in self.w.server_info:
            self._broadcast_event('new_server', "A new server was created. Details are unknown")
            return

        name = self.w.server_info[addr]['server_name']
        players = self.w.server_info[addr]['player_count']

        msg = "The new Server '%s' has %s player(s)" % (name, players)
        self._broadcast_event('new_server', msg)
        if players > 0:
            self._broadcast_event('new_game', msg)

    def _announce_server_close(self, addr):
        if addr not in self.w.server_info.keys():
            self._broadcast_event('server_close', "The server %s was closed." % addr)
            return

        if 'server_name' in self.w.server_info.keys():
            name = self.w.server_info[addr]['server_name']
        else:
            name = addr

        if 'player_count' in self.w.server_info.keys():
            players = self.w.server_info[addr]['player_count']
        else:
            players = None


        if players != None:
            msg = "The Server '%s' was closed having %s player(s)" % (name, players)
        else:
            msg = "The Server '%s' was closed" % name

        self._broadcast_event('server_close', msg)

        if players:
            self._broadcast_event('game_close', msg)

###############################################

# get login informations
option = dict()
home_dir = os.getenv('HOME')
config_file = home_dir + '/.rotcbot_jabber'


# TODO: This should be replaced by the argparse module
try:
    f = open(config_file, 'r')
except IOError, e:
    print "Failed to open config file '%s'" % config_file
    raise e

for line in f.readlines():
    line = line.rstrip('\n')
    try:
        key, value = line.split(' = ')
    except ValueError:
        key = line
        value = 'true'

    option[key] = value

# if irc transport is configured, we connect to the irc conference channel,
# and accept queries from users of that irc server
try:
    irc_transport = option['irc_transport']
    irc_server = option['irc_server']
    irc_channel = option['irc_channel']
    irc_nick = option['irc_nick']
    irc_jid = "%s%%%s@%s/%s" % (irc_channel, irc_server, irc_transport, irc_nick)
    irc = True
    print "Found irc configuration."
except KeyError:
    irc = False
    print "No irc configuration found"
    

# control_room is a conference room on a jabber server, where the log is posted
# and special commands can be called by whoever is in that room.
# Thus, it would be wise to lock the channel.
try:
    control_room = option['control_room']
except KeyError:
    control_room = None

try:
    bot = RotcBot(option['username'], option['password'], res='prod')
except KeyError, e:
    print "You need to define username and password for the bot in the config file."
    raise e

# define handler functions
# TODO: These should be defined in a subclass 
def detail_change(addr, key, oldval, newval):
    global bot
    if key == 'player_count':
        bot._announce_player_change(addr, int(oldval), int(newval))

def new_server(addr):
    global bot
    bot._announce_new_server(addr)

def server_close(addr):
    global bot
    bot._announce_server_close(addr)

    if addr in bot.server_ids:
        bot.server_ids.remove(addr)

def log(s):
    global bot, control_room

    print s
    if control_room:
        bot.send(control_room, s, message_type='groupchat')


def error_handler(error):
    log("ERR: %s" % error)


def unknown_command(mess, cmd, args):
    """Print the message of the user to the control room."""
    if mess.getType() == "groupchat":
        return None

    jid = mess.getFrom().getStripped()
    bot.send(control_room, "%s: %s %s" % (jid, cmd, ''.join(args)), message_type='groupchat')
    return """Sorry, I don't know that command - but I forwarded your message to the admins, so they might fix that. Use "help" for available commands."""

def was_subscribed(jid):
    """By default, new users get subscribed to the new_game event"""
    jid = str(jid)
    print "New user subscribed: %s" % jid
    groups = bot.roster.getGroups(jid)
    groups.append("new_game")

    bot.roster.setItem(jid, groups=groups)

    bot.send(jid, "Hi! I'll tell you about new rotc games. You can subscribe to various server events, like get notified, when a new empty server is created, or the player count of a server changes. Use the help command, to get more information.")

# End method definitions. Now hook them
bot.error = error_handler
bot.unknown_command = unknown_command
bot.was_subscribed = was_subscribed
bot.log = log

# run the build once before connecting, to avoid anouncing of long open servers
# if the bot crashes
bot._build_server_list()

if not test:
    bot.w.callback_new_server = new_server
    bot.w.callback_detail_change = detail_change
    bot.w.callback_server_close = server_close


# we are started by a supervisor script
# if it gives us previous errors, we'll send them to the admin
def connected():
    global bot, irc, irc_jid, control_room

    if irc:
        print "Joining IRC Channel %s" % irc_jid
        p = xmpp.Presence(to=irc_jid)
        p.setTag('x',namespace=xmpp.NS_MUC).setTagData('password','')
        bot.connect().send(p)
#        bot.join_room(irc_jid)

    # join control room (XMPP MUC) if configured
    if control_room:
        print "Joining Control Room %s" % control_room
        bot.join_room(control_room)

    try:
        supervisor_errors # will raise NameError if it's not defined

        log("ERR: The supervisor had to restart the script; here are the messages:")
        for err in supervisor_errors:
            log("ERR: %s" % str(err))

    except NameError:
        pass

#### All preparations done. Now, start the bot
bot.serve_forever(connected)


