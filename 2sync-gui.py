#! /usr/bin/env python3

import os
import shutil
import logging
import argparse
from twosync import config, data, utils
from gi.repository import Gtk
from gi.repository import GdkPixbuf

# Commandline arguments
parser = argparse.ArgumentParser(description='2-way syncronisation for folders')
parser.add_argument('config', help='name of the configuration file')
parser.add_argument('-d', '--debug', help='use this option for debuging (write debug messages to logfile)', action='store_true', )
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

logging.info("Start program")

try:
	config = config.config(args.config)
	pdata = data.PersistenceData(config)
	root0 = data.FSData(config.roots[0], config.config_dict)
	root1 = data.FSData(config.roots[1], config.config_dict)
	changes, conflicts = utils.find_changes(pdata, root0, root1)
	for c in changes:
		max_path_len = 0
		if max_path_len < len(c):
			max_path_len = len(c)

except utils.ExitError:
	exit(100)
except Exception as e:
	logging.critical("Unknown error", e)

class CellRendererTextWindow(Gtk.Window):
	def __init__(self):
		Gtk.Window.__init__(self, title="2sync")

		self.set_default_size(1000, 600)

		self.liststore = Gtk.ListStore(str, str, str, str)
		for c in changes:
			def ico(c):
				if pdata.get_data(c) != root0.get_data(c) and pdata.get_data(c) == root1.get_data(c):
					ico = "go-next"
				elif pdata.get_data(c) != root1.get_data(c) and pdata.get_data(c) == root0.get_data(c):
					ico = "go-previous"
				else:
					ico = Gtk.STOCK_CLOSE
				return str(ico)
			def get_state(c, root):
				if pdata.get_data(c) == root.get_data(c):
					return ""

				if pdata.get_data(c) == None and root.get_data(c) != None:
					return "New"

				if pdata.get_data(c) != None and root.get_data(c) == None:
					return "Deleted"

				if type(pdata.get_data(c)) != type(root.get_data(c)):
					return "File/Folder missmatch"

				if type(pdata.get_data(c)) == data._foldertype:
					return "Properties changed"

				if pdata.get_data(c).size != root.get_data(c).size:
					return "File changed"

				if pdata.get_data(c).moddate != root.get_data(c).moddate:
					return "File changed"

				if pdata.get_data(c).stat != root.get_data(c).stat:
					return "Properties changed"

				return "?"

			self.liststore.append([str(c), get_state(c, root0), ico(c), get_state(c, root1)])
		self.liststore.set_sort_column_id(0, Gtk.SortType.ASCENDING)

		self.treeview = Gtk.TreeView(model=self.liststore)
		self.treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
		self.treeview.set_hexpand(True)
		self.treeview.set_vexpand(True)
		self.treeview.set_enable_search(True)
		self.treeview.set_rubber_banding(True)

		column_path = Gtk.TreeViewColumn("Path", Gtk.CellRendererText(), text=0)
		column_path.set_resizable(resizable=True)
		column_path.set_spacing(spacing=10)
		column_path.set_sort_column_id(0)
		self.treeview.append_column(column_path)

		column_root1 = Gtk.TreeViewColumn(config.roots[0], Gtk.CellRendererText(), text=1)
		column_root1.set_resizable(resizable=True)
		column_root1.set_spacing(spacing=10)
		column_root1.set_sort_column_id(1)
		self.treeview.append_column(column_root1)

		column_action = Gtk.TreeViewColumn("Action", Gtk.CellRendererPixbuf(), icon_name=2)
		column_action.set_resizable(resizable=True)
		column_action.set_spacing(spacing=10)
		# Deactivated, because if action is sorted the change of the sync-direction didn't work correct
		# column_action.set_sort_column_id(2)
		self.treeview.append_column(column_action)

		column_root2 = Gtk.TreeViewColumn(config.roots[1], Gtk.CellRendererText(), text=3)
		column_root2.set_resizable(resizable=True)
		column_root2.set_spacing(spacing=10)
		column_root2.set_sort_column_id(3)
		self.treeview.append_column(column_root2)

		self.treeview.get_selection().connect("changed", self.treeview_selection)

		self.lbl_path	 = Gtk.Label(xalign=0, selectable=True)
		self.lbl_detail0 = Gtk.Label(xalign=0, selectable=True)
		self.lbl_detail1 = Gtk.Label(xalign=0, selectable=True)

		icon_left 	= Gtk.Image().new_from_icon_name(size=Gtk.IconSize.BUTTON, icon_name="go-previous")
		icon_right 	= Gtk.Image().new_from_icon_name(size=Gtk.IconSize.BUTTON, icon_name="go-next")
		icon_ign 	= Gtk.Image().new_from_icon_name(size=Gtk.IconSize.BUTTON, icon_name=Gtk.STOCK_CLOSE)

		btn_sync 		= Gtk.Button(xalign=0.5, label="sync")
		btn_close 		= Gtk.Button(xalign=0.5, label="close")
		self.btn_left 	= Gtk.Button(sensitive=False, image=icon_left)
		self.btn_right 	= Gtk.Button(sensitive=False, image=icon_right)
		self.btn_ign	= Gtk.Button(sensitive=False, image=icon_ign)

		btn_sync.connect		("clicked", 	self.do_sync)
		self.btn_ign.connect	("clicked", 	self.ignore)
		self.btn_right.connect	("clicked", 	self.to_right)
		self.btn_left.connect	("clicked", 	self.to_left)

		btn_close.connect("clicked", 		Gtk.main_quit)

		grid = Gtk.Grid()
		grid.set_border_width(4)
		grid.set_row_spacing(10)
		grid.set_column_spacing(10)
		grid.attach(self.treeview, 		0, 0, 6, 1)
		grid.attach(self.lbl_path, 		0, 1, 6, 1)
		grid.attach(self.lbl_detail0, 	0, 2, 6, 1)
		grid.attach(self.lbl_detail1, 	0, 3, 6, 1)
		grid.attach(self.btn_left, 		0, 4, 1, 1)
		grid.attach(self.btn_right, 	1, 4, 1, 1)
		grid.attach(self.btn_ign, 		2, 4, 1, 1)
		grid.attach(btn_sync, 			4, 4, 1, 1)
		grid.attach(btn_close, 			5, 4, 1, 1)

		self.add(grid)

	def treeview_selection(self, selection):
		def set_labels(model, path, iter, _):
			def to_str(fdata, path):
				if type(fdata) == data._filetype:
					return "{0}:\tStat: {1:10}\tModdate: {2:10}\tSize: {3}".format(path, fdata.stat, fdata.moddate, fdata.size)
				elif type(fdata) == data._foldertype:
					return "{0}:\tStat: {1}".format(path, fdata.stat)
				return "{0}:\tDid not exist".format(path)

			path = model.get_value(iter, 0)
			data0 = root0.get_data(path)
			data1 = root1.get_data(path)
			self.lbl_path.set_text(path)
			self.lbl_detail0.set_text(to_str(data0, root0.path))
			self.lbl_detail1.set_text(to_str(data1, root1.path))

		if selection.count_selected_rows() > 0:
			self.btn_left.props.sensitive = True
			self.btn_right.props.sensitive = True
			self.btn_ign.props.sensitive = True
		else:
			self.btn_left.props.sensitive = False
			self.btn_right.props.sensitive = False
			self.btn_ign.props.sensitive = False
		if selection.count_selected_rows() == 1:
			selection.selected_foreach(set_labels, None)
		else:
			self.lbl_path.set_text("")
			self.lbl_detail0.set_text("")
			self.lbl_detail1.set_text("")

	def ignore(self, _):
		(_, selections) = self.treeview.get_selection().get_selected_rows()
		for selection in selections:
			self.liststore[selection][2] = Gtk.STOCK_CLOSE
			self.treeview.grab_focus()

	def to_right(self, _):
		(_, selections) = self.treeview.get_selection().get_selected_rows()
		for selection in selections:
			self.liststore[selection][2] = "go-next"
			self.treeview.grab_focus()

	def to_left(self, _):
		(_, selections) = self.treeview.get_selection().get_selected_rows()
		for selection in selections:
			self.liststore[selection][2] = "go-previous"
			self.treeview.grab_focus()

	def do_sync(self, _):
		for entry in self.liststore:
			if entry[2] == Gtk.STOCK_CLOSE:
				continue
			elif entry[2] == "go-previous":
				shutil.copy(root1.path + entry[0], root0.path + entry[0])
				shutil.copystat(root1.path + entry[0], root0.path + entry[0])
				pdata.add_file(entry[0], root1.get_data(entry[0]).stat, root1.get_data(entry[0]).moddate, root1.get_data(entry[0]).size)
			elif entry[2] == "go-next":
				shutil.copy(root0.path + entry[0], root1.path + entry[0])
				shutil.copystat(root0.path + entry[0], root1.path + entry[0])
				pdata.add_file(entry[0], root0.get_data(entry[0]).stat, root0.get_data(entry[0]).moddate, root0.get_data(entry[0]).size)
				
		treeiter = self.liststore.get_iter_first()
		while treeiter != None:
			if self.liststore[treeiter][2] != Gtk.STOCK_CLOSE:
				self.liststore.remove(treeiter)
			treeiter = self.liststore.iter_next(treeiter)

win = CellRendererTextWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
Gtk.main()