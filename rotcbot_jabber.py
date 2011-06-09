#!/usr/bin/python
# -*- coding: utf-8 -*-

# RotcBot: A simple TGE server event broadcaster
# Copyright (c) 2011 Wanja Chresta <github.com/brachiel>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

__author__= "brachiel (Wanja Chresta)"
__licence__= "GNU GPLv3"

from jabberbot import JabberBot
from RotcWatcher import Watcher

import logging
import traceback
import time
import xmpp

# Modified bodcmd from JabberBot to allow admin commands
def botcmd(*args, **kwargs):
    """Decorator for bot command functions"""

    def decorate(func, hidden=False, name=None, admin=False, no_irc=False):
        setattr(func, '_jabberbot_command', True)
        setattr(func, '_jabberbot_hidden', hidden)
        setattr(func, '_jabberbot_admin', admin) # is this an admin-command?
        setattr(func, '_jabberbot_no_irc', no_irc) # command not available in irc?
        setattr(func, '_jabberbot_command_name', name or func.__name__)
        return func

    if len(args):
        return decorate(args[0], **kwargs)
    else:
        return lambda func: decorate(func, **kwargs)

class JabberBotExtended(JabberBot):
    """Various extensions, improvements and other gadgets to JabberBot."""
    
    def __init__(self, config):
        self.config = config
        
        custom_message_handler = self.custom_message_handler # Store the method
        super(JabberBotExtended,self).__init__(config['jabber_id'], config['jabber_password'])
        
        # The init script fucks up the method; so we have to restore it again.
        self.custom_message_handler = custom_message_handler

        self.irc = False
        self.irc_conferenceroom_tags = { ('x', xmpp.NS_MUC): [] } # TODO: This has to be changed depending on the used IRC transport
        
        self.control_room = False

        if 'name' not in config.keys():
            self.log.error("Please define a name in the configuration.")
            raise Exception("Please define a name in the configuration.")
        
    def build_reply(self, mess, text=None, private=False):
        """Build a message for responding to another message.  Message is NOT sent"""
        response = self.build_message(text)
        
        # IRC related stuff
        if self.irc and self.mess_is_from_irc(mess):
            self.log.debug("Got IRC Message. Building IRC reply.")
            
            if self.irc_allow_loud(mess.getFrom(), mess.getType()):
                private = False
            else:
                private = True
        
        if private:
            response.setTo(mess.getFrom())
            response.setType('chat')
        else:
            response.setTo(mess.getFrom().getStripped())
            response.setType(mess.getType())
        response.setThread(mess.getThread())
        return response

    def irc_allow_loud(self, jid):
        return False # defauls is no loud messages to IRC at all

    def mess_is_from_irc(self, mess):
        return mess.getFrom().getDomain() == self.config['irc_transport']

    def serve_forever(self, callback=None):
        conn = self.connect() # do one process cycle before executing on_connected
        conn.Process(1)
        
        if not callback:
            callback = self.on_connected
            
        JabberBot.serve_forever(self, callback)
        
        
    def join_room(self, room, username=None, tags={}):
        """Join the specified multi-user chat room"""
        if username is None:
            username = self._JabberBot__username.split('@')[0]
        my_room_JID = '/'.join((room, username))
        p = xmpp.Presence(to=my_room_JID)
        for (tag_name, namespace), KeyValPairs in tags.items():
            tag = p.setTag(tag_name,namespace=namespace)
            for (key, value) in KeyValPairs:
                tag.setTagData(key, value)
        self.connect().send(p)
       
       
    @botcmd(admin=True)
    def join_chat(self, mess, args):
        room = args[:(args + ' ').find(' ')]
        if not chan:
            return 'Usage: join_chat channel_name@conference_server'
        
        self.join_room(room, username)
        return 'Success'
        
    @botcmd(admin=True)
    def join_irc_chan(self, mess, args):
        if self.irc:
            chan = args[:(args + ' ').find(' ')]
            if not chan:
                return 'Usage: join_irc_chan channel_name (only the IRC name of the channel; no server or transport!).'

            room = "%s%%%s@%s" % (chan, self.config['irc_server'], self.config['irc_transport'])
            self.join_room(room, username=self.config['irc_nick'], tags=self.irc_conferenceroom_tags) 
            return 'Success'
        else:
            return 'Not connected to an IRC network.'
        
    def on_connected(self):
        c = self.config
                    
        if c['irc_server']:
            try:
                self.irc_room = "%s%%%s@%s" % (c['irc_channel'], c['irc_server'], c['irc_transport'])
                
                # We need to use the x-tag to join an IRC channel
                self.join_room(self.irc_room, username=c['irc_nick'], tags=self.irc_conferenceroom_tags)
                
                self.log.info("Joined IRC Channel: %s on %s via transport %s" % 
                                (c['irc_channel'], c['irc_server'], c['irc_transport']))
                self.irc = True
            except KeyError, e:
                self.irc = False
                self.log.error("IRC: Inconsistent or wrong IRC configuration: %s" % str(e))
        
        if c['control_room']:
            self.join_room(c['control_room'], c['name'])
            self.log.info("Joined control room %s as %s." % (c['control_room'], c['name']))
            
            self.control_room = True
        else:
            self.control_room = False


    def custom_message_handler(self, mess, text):
        reply = self.custom_message_handler_admin(mess, text)
        
        if reply: # Send reply and mark message as handled.
            self.send_simple_reply(mess, reply)
            return True
        
        if reply == False: # Ignore those messages, don't send a reply and mark them as handled.
            return True
        
        return None # custom_handler has no effect on those messages. Normal procedures are called.
        
    def custom_message_handler_admin(self, mess, text):
        """Handle admin commands, allow and report them, if used by non-admins."""
        modified_text = False
        is_irc = False
        
        # Ignore any message from users with my name
        if self.get_sender_username(mess) == self.config['name']: return False
        
        # Ignore any message from an IRC channel that doesn't begin with my name or +
        if self.irc and self.mess_is_from_irc(mess):
            # TODO: IRC is simplex; we only send messages to IRC, but don't process any replies or requests!
            return False
        
#            is_irc = True
#            
#            #if mess.getFrom().getNode()[0] != '#': return False
#            
#            if mess.getType() == 'groupchat':
#                if text.startswith('+'): # Message starts with +
#                    text = text[1:].strip()
#                    modified_text = True
#                elif text.startswith(self.config['name']): # Message starts with my name
#                    text = text[len(self.config['name']):]
#                    text = text.lstrip(',:;') # remove punctuations after the name
#                    text = text.strip() # remove whitespaces
#                    modified_text = True
#                else:
#                    return False # Ignore all other messages
        
        if ' ' in text:
            command, args = text.split(' ', 1)
        else:
            command, args = text, ''
        cmd = command.lower()
        
        
        # CAUTION: All admin commands must be caught by this if, or they'll be handed down to the standard routine
        # which means everyone could execute them.
        if self.commands.has_key(cmd) and self.commands[cmd]._jabberbot_admin:
            if not is_irc and self.is_admin(mess):
                try:
                    self.log.info("The user '%s' used the admin command '%s'." % (mess.getFrom(), text))
                    return self.commands[cmd](mess, args)
                except Exception, e:
                    jid = mess.getFrom().getStripped()
                    self.log.exception('An error happened while processing a message ("%s") from %s"' % (text, jid))
                    return traceback.format_exc(e)
            else:
                self.log.info("The non admin user '%s' tried to use the admin command '%s'." % (mess.getFrom(), text))
                default_reply = 'Unknown command: "%s". Type "help" for available commands.' % cmd
                reply = self.unknown_command(mess, cmd, args)
                if reply: return reply
                else:     return default_reply
        
# TODO: If we allow replies from IRC, we want to reenable this code.
#        if is_irc and self.commands.has_key(cmd) and self.commands[cmd]._jabberbot_no_irc:
#            return "The command '%s' is not available on IRC. Please use my jabber interface: %s" % \
#                                                                        (cmd, self.jid.getStripped())
                
        # If the command is not found, try to find the best matching command
        if not self.commands.has_key(cmd):
            # No hidden commands, no admin commands
            cmds = [ name for (name, command) in self.commands.iteritems() 
                        if not command._jabberbot_hidden and not command._jabberbot_admin ]
            cmds.sort()
                        
            # we look for the first matching command alpabetically, deleting the last character of all commands
            # every loop. So eventually, "sh" will match "show" before "show_snow".
            matching_command = None
            for n in range(-1, -max([len(x) for x in cmds]), -1):
                try:
                    i = [ x[:n] for x in cmds ].index(cmd)
                    matching_command = cmds[i]
                    break
                except ValueError:
                    continue
                    
            if matching_command:
                self.log.debug("%s cmd: %s" % (str(mess.getFrom()), text))
                if is_irc and self.commands[matching_command]._jabberbot_no_irc:
                    return "The command '%s' is not available on IRC. Please use my jabber interface: %s" % \
                                                                        (matching_command, self.jid.getStripped())
                                                                        
                try:
                    return self.commands[matching_command](mess, args)
                except Exception, e:
                    jid = mess.getFrom().getStripped()
                    self.log.exception('An error happened while processing a message ("%s") from %s"' % (text, jid))
                    return traceback.format_exc(e)
        else:        
            self.log.debug("%s cmd: %s" % (str(mess.getFrom()), text))
        
    
#TODO: If we allow replies from IRC, we want to reenable this code.
#        # If we changed the text, we need to execute an exact matching command now. Otherwise the original
#        # method tries to execute the unmodified text (since it has it's own copy).
#        if modified_text:
#            if self.commands.has_key(cmd):
#                try:
#                    return self.commands[cmd](mess, args)
#                except Exception, e:
#                    self.log.exception('An error happened while processing a message ("%s") from %s: %s"' % (text, jid, reply))
#                    return traceback.format_exc(e)
#            else:
#                # We can always reply here, since we are going to repsond to irc in private mode anyway.
#                default_reply = 'Unknown command: "%s". Type "help" for available commands.' % cmd
#                return default_reply 
            
        return None

    def unknown_command(self, mess, cmd, args):
        "We have to define this function because we use a custom message handler."
        type = mess.getType()

        if type == "groupchat": 
            return False # This is not None, so the default routine to generate an "unknown message" kicks in
        else:
            return 'Unknown command: "%s". Type "help" for available commands.' % cmd
        

    def broadcast(self, message, only_available=True, to_groups=set()):
        """Broadcast a message to all users 'seen' by this bot.

        If the parameter 'only_available' is True, the broadcast
        will not go to users whose status is not 'Available'."""
        
        # Parse to_groups to set for convenience
        if isinstance(to_groups, list):
            to_groups = set(to_groups)
        elif isinstance(to_groups, str) or isinstance(to_groups, unicode):
            to_groups = set([to_groups])
        
        # we use the seen list to figure out which roster users are online,
        # and we choose only one resource for every jid
        jids = {}
        
        for jid, (show, status) in self._JabberBot__seen.items():
            if not jid.getNode(): # We don't care for transports and such
                continue
                
            if not only_available or show is self.AVAILABLE:
                jid_str = jid.getStripped()
                if jid_str in jids.keys():
                    # Compare the priorities, and choose the one with the higher one
                    if self.roster.getPriority(str(jids[jid_str])) < self.roster.getPriority(str(jid)):
                        jids[jid_str] = jid
                else:
                    jids[jid_str] = jid
                
        #for jid_str, jid in jids.items():
        for jid_str in self.roster.getItems():
            if jid_str in jids.keys():
                jid = jids[jid_str]
            else:
                continue

            if self.irc and jid.getDomain() == self.config['irc_transport']:
                chan = jid.getNode()
                chan = chan[:(chan+'%').find('%')] # get the channel name
                jid = xmpp.JID(jid.getStripped()) # copy the jid, so we don't change the original one
                jid.setResource(chan)
                message_type = 'groupchat'
            else:
                message_type = 'chat'
                
            if len(to_groups) > 0:
                groups = self.roster.getGroups(jid_str)
                    
                if to_groups.issubset(groups):
                    self.log.debug("<%s %s %s" % (list(to_groups), jid_str, message))
                    self.send(jid, message, message_type=message_type)
                else:
                    self.log.debug("X %s is not in %s for %s" % (list(to_groups), groups, jid))
            else:
                self.send(jid, message, message_type=message_type)
                self.log.debug("< %s %s" % (jid, message))

    def callback_presence(self, conn, presence):
           
        super(JabberBotExtended,self).callback_presence(conn, presence)
           
        jid, type_, show, status = presence.getFrom(), \
                presence.getType(), presence.getShow(), \
                presence.getStatus()
                
        try:
            subscription = self.roster.getSubscription(unicode(jid.__str__()))
        except KeyError:
            return
        except AttributeError:
            return
        
        if type_ == 'subscribe':
            if subscription in ('to', 'both', 'from'):
                self.was_subscribed(presence)
        elif type_ == 'subscribed':
            self.was_subscribed(presence)
            
    def was_subscribed(self, presence):
        self.log.info("New subscriber: %s" % str(presence.getFrom()))

    @botcmd
    def help(self, mess, args):
        """Returns a help string listing available options.

        Automatically assigned to the "help" command."""
        if self.is_admin(mess):
            is_admin = True
        else:
            is_admin = False
            
        if self.mess_is_from_irc(mess):
            is_irc = True
        else:
            is_irc = False
        
        if not args:
            if self.__doc__:
                description = self.__doc__.strip()
            else:
                description = 'Available commands:'

            usage = ""
            if is_admin:
                usage += '\n'.join(sorted([
                    'ADMIN %s: %s' % (name, (command.__doc__ or '(undocumented)').strip().split('\n', 1)[0])
                    for (name, command) in self.commands.iteritems() if name != 'help' and not command._jabberbot_hidden 
                    and command._jabberbot_admin
                ]))
                
            if is_irc:
                usage += '\n'.join(sorted([
                    '%s: %s' % (name, (command.__doc__ or '(undocumented)').strip().split('\n', 1)[0])
                    for (name, command) in self.commands.iteritems() if name != 'help' and not command._jabberbot_hidden 
                    and not command._jabberbot_admin and not command._jabberbot_no_irc
                ]))
            else:
                usage += '\n'.join(sorted([
                    '%s: %s' % (name, (command.__doc__ or '(undocumented)').strip().split('\n', 1)[0])
                    for (name, command) in self.commands.iteritems() if name != 'help' and not command._jabberbot_hidden 
                    and not command._jabberbot_admin
                ]))
                    
            usage = usage + '\n\nType help <command name> to get more info about that specific command.'
        else:
            description = ''
            if args in self.commands:
                usage = self.commands[args].__doc__.strip() or 'undocumented'
            else:
                usage = 'That command is not defined.'

        top = self.top_of_help_message()
        bottom = self.bottom_of_help_message()
        if top   : top = "%s\n\n" % top
        if bottom: bottom = "\n\n%s" % bottom

        return '%s%s\n\n%s%s' % (top, description, usage, bottom)

 #####################################
 
    @botcmd(admin=True)
    def set_presence(self, mess, args):
        status = ['online', 'away', 'chat', 'dnd', 'xa', 'unavailable']
        if args in status:
            self.status_type = args
            return "Success"
        else:
            return "Error. Possibilities: %s" % ' '.join(status)
        
        
        
    @botcmd(admin=True)
    def add_group(self, mess, text):
        """Adds the specified user to the specified group."""
        args = text.split(' ', 1)
        if len(args) >= 2:
            jid = args[0]
            group = args[1]
            
            try:
                groups = set(self.roster.getGroups(jid))
            except KeyError:
                return "There is no user with that jid."
                
            if group not in groups:
                groups.add(group)
                self.roster.setItem(jid, groups=list(groups))
                return "Added %s to %s's groups." % (group, jid)
            else:
                return "%s was already in %s's groups." % (group, jid)
        else:
            return "Usage: add_group <user> <group>"

    @botcmd(admin=True)
    def remove_group(self, mess, text):
        """Adds the specified user to the specified group."""
        args = text.split(' ', 1)
        if len(args) >= 2:
            jid = args[0]
            group = args[1]
            
            try:
                groups = set(self.roster.getGroups(jid))
            except KeyError:
                return "There is no user with that jid."
            
            if group in groups:
                groups.remove(group)
                self.roster.setItem(jid, groups=list(groups))
                return "Removed %s from %s's groups." % (group, jid)
            else:
                return "%s isn't in %s's groups." % (group, jid)
        else:
            return "Usage: remove_group <user> <group>"
        
        
    @botcmd(admin=True)
    def show_groups(self, mess, text):
        """Shows all groups of a given user"""
        jid = text[:(text+' ').find(' ')]
        
        try:
            groups = set(self.roster.getGroups(jid))
        except KeyError:
            return "There is no user with that jid."
        return "User %s has groups: %s" % (jid, list(groups))
    
    def is_admin(self, mess):
        # TODO: This is only for testing!
        if mess.getFrom().getStripped() == self.config['control_room']:
            return True
        else:
            return False
        
    @botcmd(admin=True)
    def show_roster(self, mess, text):
        """Shows all users and their groups."""
        
        response = "Roster:\n"
        for jid in self.roster.getItems():
            response += "* %s: %s\n" % (jid, self.roster.getGroups(jid))
            
        return response
        
    @botcmd(admin=True)
    def msg(self, mess, args):
        """Send a message to a user."""
        try:
            target, msg = args.split(' ', 1)
            self.send(target, msg)
            return "Success"
        except ValueError:
            return "The correct format is: msg jid message"
        
    @botcmd(admin=True)
    def to_all(self, mess, text):
        """Broadcast a message to *all* users (even the ones who are offline)."""
        if len(text) > 0:
            self.broadcast(text, only_available=False)
            return "Success"
        else:
            return "No message given."
   
    @botcmd(admin=True)
    def to_available(self, mess, text):
        """Broadcast a message to all users who are online."""
        if len(text) > 0:
            self.broadcast(text, only_available=True)
            return "Success"
        else:
            return "No message given."
        
    @botcmd(admin=True)
    def to_group(self, mess, args):
        """Broadcast a message to all users who are in the given group."""
        try:
            group, msg = args.split(' ', 1)
            self.broadcast(msg, only_available=True, to_groups=group)
            return "Success"
        except ValueError:
            return "The correct format is: to_group group message"
        
    @botcmd(admin=True)
    def quit(self, mess=None, args=None):
        """Shutdown the bot."""
        self.log.info("Shutting down the bot...")
        super(JabberBotExtended,self).quit()
        
        
class RotcBot(JabberBotExtended, Watcher, logging.Handler):
    """rotcbot informs you about server events like when a new game takes place, or a new player joins a game. \
There are various event you can subscribe to; use "sub_event" for a list of possible events. Note: You can use \
short versions of the commands, as long as they're unabbiguous. So you can use "sh" for show, and "su" for sub_event."""
    
    def __init__(self, configuration):
        super(RotcBot,self).__init__(configuration)
        Watcher.__init__(self)
        logging.Handler.__init__(self)
        
        # Logging stuff
        chandler = logging.StreamHandler()
        chandler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        self.log.addHandler(chandler)

        self.setLevel(logging.INFO) # Only send INFO messages to the control room
        self.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        self.log.addHandler(self)
        
        # The messages that go to the console
        self.log.setLevel(logging.DEBUG)
        
        
        #####
        self.server_ids = []       # enumerate keys of server_list
        self.last_rotc_update = 0

        self.EVENTS = { 'new_game': 'The first player joins a server.',
                        'game_close': 'The last player leaves a server, or a server which had players is closed.',
                        'player_change': 'A change in player numbers on a server.',
                        'new_server': 'A new server was created (any number of players, even 0).',
                        'server_close': 'A server was closed (even if it had no players)' }
                        
        # Build the server list
        self._build_server_list()
        
        # Connect the events
        self.callback_new_server = self._callback_new_server
        self.callback_detail_change = self._callback_detail_change
        self.callback_server_close = self._callback_server_close
    
    ### Internal methods
    def emit(self, record): # This is for the logging module
        if self.control_room:
            msg = self.format(record)
            self.send(self.config['control_room'], msg, message_type='groupchat')
        
    def idle_proc(self):    
        JabberBotExtended.idle_proc(self)
        
        if self.last_rotc_update + 7 < int(time.time()):
            self._build_server_list()
            self.last_rotc_update = int(time.time())

    def was_subscribed(self, presence):
        jid = presence.getFrom().getStripped()
        
        self.sub_event(presence.getFrom(), 'new_game')
        log.info("New user '%s' subscribed to us." % jid)
        self.send(jid, "Hi! I'll tell you about new rotc games. You can subscribe to various server events, like get "+
                    +"notified, when a new empty server is created, or the player count of a server changes. Use the "+
                    +"help command, to get more information.")
    ###
    
    def irc_allow_loud(self, jid, type):
        if type == 'groupchat':
            try:
                groups = self.roster.getGroups(jid.getStripped())

                if 'irc_loud' in groups:
                    return True
                else:
                    return False
            except KeyError:
                return False
        else: # we always reply normally to normal chats
            return True
    
    ###
    
    @botcmd(no_irc=True)
    def show_events(self, mess, args):
        """Shows the events you've subscribed."""
        jid = mess.getFrom().getStripped()

        try:
            groups = set(self.roster.getGroups(jid))
        except:
            self.log.warn(self.roster._data.keys())
            raise

        if len(groups) == 0 or ('Not in roster' in groups and len(groups) == 1):
            return "You haven't subscribed any events. To do so, use sub_event"
       
        msg = []
        for event,desc in self.EVENTS.items():
            if event in groups:
                msg.append('%s - %s' % (event, desc))
        return "The events you've currently subscribed:\n" + '\n'.join(msg)

    @botcmd(no_irc=True)
    def sub_event(self, mess, args, jid=None):
        """Subscribe an event (new_game, game_close, player_change, new_server, server_close)."""
        if not jid:
            jid = mess.getFrom().getStripped()

        if args not in self.EVENTS.keys():
            return "%s is not a valid event. Possibilities are: %s" % (args, ', '.join(self.EVENTS.keys()))

        groups = set(self.roster.getGroups(jid))
        if args not in groups:
            groups.add(args)

            self.roster.setItem(jid, groups=list(groups))
            self.log.info("%s subscribed to %s" % (jid, args))

            return "You have subscribed to the %s event" % args
        else:
            return "You've already subscribed to the %s event. Nothing changed." % args
        
    @botcmd(no_irc=True)
    def unsub_event(self, mess, args):
        """Unsubscribe an event."""
        jid = mess.getFrom().getStripped()

        groups = set(self.roster.getGroups(jid))

        if args not in groups:
            return "You are not subscribed to the event '%s'" % args

        groups.remove(args)

        self.roster.setItem(jid, groups=list(groups))
        self.log("%s unsubscribed from %s" % (jid, args))

        return "You've been unsubscribed to the event '%s'" % args


    @botcmd
    def details(self, mess, args):
        """Displays the details of a given rotc server."""
        if args in self.server_ids:
            addr = args
            det = self.get_server_details(addr)
        else:
            try:
                i = int(args)
            except ValueError:
                return "Unknown id. Enter either id from list or IP"

            if i < len(self.server_ids) and self.server_ids[i] != None:
                addr = self.server_ids[i]
                det = self.get_server_details(addr)
            else:
                return "There is no server with this id."

        retn = ["Details for rotc ethernet server with address %s:" % addr]
        for key, value in det.items():
            retn.append("%s: %s" % (key, value))
            
        return '\n'.join(retn)

    @botcmd
    def list(self, mess, args):
        """Displays the list of open rotc servers."""
        if len(self.server_ids) == 0:
            return "There are no open rotc servers. Maybe you want to host one?"

        retn = ["List of open rotc ethernet servers:"]

        for i in range(len(self.server_ids)):
            addr = self.server_ids[i]
            try:
                name = self.server_info[addr]['server_name']
                players = self.server_info[addr]['player_count']
                #map = self.server_info[addr]['mission_name']

                retn.append("[%i] %s has %s players" % (i, name, players))
            except KeyError:
                retn.append("[%i] %s is in an unknown state" % (i, addr))

        return '\n'.join(retn)

###### RotcWatcher methods

    # wait connecting the events until we've run _build_server_list(), so we don't announce the servers when we crashed
    def _callback_server_close(self, addr, server_details=None):
        self._announce_server_close(addr)
        
        if addr in self.server_ids:
            self.server_ids.remove(addr)

    def _callback_detail_change(self, addr, key, old_val=None, new_val=None):
        if key == 'player_count':
            self._announce_player_change(addr, int(old_val), int(new_val))

    def _callback_new_server(self, addr, server_details=None):
        self._announce_new_server(addr)

    
    def _build_server_list(self):
        self.update_server_list()

        # after this is called, the RotcWatcher module will call RotcWatcher.callback_* functions which must be connected to functions that do something
        server_list = [ x for x,y in self.server_info.items() if 'new' not in y.keys() ]

        # update the id-list of servers to use with the "list" command
        new_ids = [None,] * len(self.server_ids) # presume all the servers are gone
        for addr in server_list:
            if addr in self.server_ids:
                i = self.server_ids.index(addr)
                new_ids[i] = addr
            else:
                new_ids.append(addr)

        self.server_ids = new_ids


    def _announce_player_change(self, addr, from_players, to_players):
        if addr not in self.server_info:
            return

        name = self.server_info[addr]['server_name']

        msg = "Server '%s' has now %s player(s)." % (name, to_players)
        self.log.info(msg)

        self.broadcast(msg, to_groups='player_change')
        if from_players == 0 and to_players >= 1: # first player joins
            self.broadcast(msg, to_groups='new_game')
        elif from_players >= 1 and to_players == 0: # last player leaves
            self.broadcast(msg, to_groups='game_close')

    def _announce_new_server(self, addr):
        if addr not in self.server_info:
            self.broadcast("A new server was created. Details are unknown", to_groups='new_server')
            return

        name = self.server_info[addr]['server_name']
        players = self.server_info[addr]['player_count']

        msg = "The new Server '%s' has %s player(s)" % (name, players)
        self.log.info(msg)
        
        self.broadcast(msg, to_groups='new_server')
        if players > 0:
            self.broadcast(msg, to_groups='new_game')

    def _announce_server_close(self, addr):
        if addr not in self.server_info.keys():
            self.broadcast("The server %s was closed." % addr, to_groups='server_close')
            return

        if 'server_name' in self.server_info.keys():
            name = self.server_info[addr]['server_name']
        else:
            name = addr

        if 'player_count' in self.server_info.keys():
            players = self.server_info[addr]['player_count']
        else:
            players = None


        if players != None:
            msg = "The Server '%s' was closed having %s player(s)" % (name, players)
        else:
            msg = "The Server '%s' was closed" % name

        self.broadcast(msg, to_groups='server_close')
        self.log.info(msg)

        if players:
            self.broadcast(msg, 'game_close')

def load_config(config_file=None):    
    if not config_file:
        import os
        home_dir = os.getenv('HOME')
        config_file = home_dir + '/.rotcbot_jabber'

    # Those are the defaults
    config = {
        'master_server': 'spica.dyndns.info:28002'
    }
    
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
            value = True

        config[key] = value
        
    f.close()
    
    return config


if __name__ == "__main__":
    
    # TODO: Read the configfile location from argv (argparse?)
    
    bot_configuration = load_config()
    bot = RotcBot(bot_configuration)
    bot.serve_forever()
