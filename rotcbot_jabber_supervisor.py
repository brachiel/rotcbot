#!/usr/bin/python

# script starts another script and makes sure it gets restarted when it dies.
# also puts errors in global vars of new script

import traceback
import time

SCRIPT = '/home/rotc/rotcbot_jabber/rotcbot_jabber.py'

globs = { 'supervisor_errors': [] }

while 1:
    try:
        execfile(SCRIPT, globs)
    except Exception, err:
	print repr(err)

        if len(err.args) > 0:
            if str(err.args[0]) == 'Shutdown rotcbot':
                break

        traceback.print_exc()
	globs['supervisor_errors'] = [ err ]

    print "RESTARTING ROTCBOT..."
    time.sleep(7)

print "SHUTDOWN ROTCBOT..."

