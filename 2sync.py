#! /usr/bin/env python3
from gi.repository import Gtk, GObject
import gui
import logging
import argparse
import threading

# Commandline arguments
parser = argparse.ArgumentParser(description='2-way syncronisation for folders')
parser.add_argument('config', help='name of the configuration file')
parser.add_argument('-d', '--debug', action='store_true', help='use this option for debuging (write debug messages to logfile)')
args = parser.parse_args()

# Config logging
# Set loglevel für logfile
if args.debug == True:
	log_level = logging.DEBUG
else:
	log_level = logging.INFO

# Logging to file	
logging.basicConfig(level=log_level, filename='2sync.log', filemode='a', format='%(levelname)s: %(asctime)s - 2sync - %(message)s')
# define a Handler for sys.stderr and add it
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
logging.getLogger('').addHandler(console)

# Needed for running threads
GObject.threads_init()

thread = threading.Thread(target=gui.TwoSyncGUI, args=[args.config])
thread.daemon = True
thread.start()

try:
	Gtk.main()
except:
	Gtk.main_quit()