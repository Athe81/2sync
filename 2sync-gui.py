#! /usr/bin/env python3
from gi.repository import Gtk
from gi.repository import GdkPixbuf
from twosync import config, data, utils
import os
import shutil
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

logging.info("Start program")

def prepare(config_name):
	try:
		dialog.progress.set_fraction(0.1)
		dialog.progress.set_text("Read and parse config")
		cfg = config.Config(config_name)
		dialog.progress.set_fraction(0.2)
		dialog.progress.set_text("Read saved data")
		pdata = data.PersistenceData(cfg)
		dialog.progress.set_fraction(0.4)
		dialog.progress.set_text("Read data from " + cfg.roots[0])
		if cfg.roots[0].startswith('ssh://'):
			root0 = data.SSHData(cfg.roots[0], cfg)
		else:
			root0 = data.FSData(cfg.roots[0], cfg)
		dialog.progress.set_fraction(0.6)
		dialog.progress.set_text("Read data from " + cfg.roots[1])
		if cfg.roots[1].startswith('ssh://'):
			root1 = data.SSHData(cfg.roots[1], cfg)
		else:
			root1 = data.FSData(cfg.roots[1], cfg)
		dialog.progress.set_fraction(0.8)
		dialog.progress.set_text("Analyse data")
		changes, conflicts = utils.find_changes(pdata, root0, root1)
		dialog.progress.set_fraction(1.0)
	except utils.ExitError:
		exit(100)
	except Exception as e:
		logging.critical("Unknown error", e)

	return cfg, pdata, root0, root1, changes, conflicts

class MainWindow(Gtk.Window):
	def __init__(self):
		super().__init__(title="2sync")

		self.set_default_size(1000, 600)

		self.liststore = Gtk.ListStore(str, str, str, str)

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

		self.column_root0 = Gtk.TreeViewColumn('root[0]', Gtk.CellRendererText(), text=1)
		self.column_root0.set_resizable(resizable=True)
		self.column_root0.set_spacing(spacing=10)
		self.column_root0.set_sort_column_id(1)
		self.treeview.append_column(self.column_root0)

		column_action = Gtk.TreeViewColumn("Action", Gtk.CellRendererPixbuf(), icon_name=2)
		column_action.set_resizable(resizable=True)
		column_action.set_spacing(spacing=10)
		# Deactivated, because if action is sorted the change of the sync-direction didn't work correct
		# column_action.set_sort_column_id(2)
		self.treeview.append_column(column_action)

		self.column_root1 = Gtk.TreeViewColumn('root[1]', Gtk.CellRendererText(), text=3)
		self.column_root1.set_resizable(resizable=True)
		self.column_root1.set_spacing(spacing=10)
		self.column_root1.set_sort_column_id(3)
		self.treeview.append_column(self.column_root1)

		self.treeview.get_selection().connect("changed", self.treeview_selection)

		scrolled_window = Gtk.ScrolledWindow()
		scrolled_window.add(self.treeview)

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

		btn_sync.connect		("clicked", 	self.sync)
		self.btn_ign.connect	("clicked", 	self.ignore)
		self.btn_right.connect	("clicked", 	self.to_right)
		self.btn_left.connect	("clicked", 	self.to_left)

		btn_close.connect("clicked", Gtk.main_quit)

		grid = Gtk.Grid()
		grid.set_border_width(4)
		grid.set_row_spacing(10)
		grid.set_column_spacing(10)
		grid.attach(scrolled_window, 	0, 0, 6, 1)
		grid.attach(self.lbl_path, 		0, 1, 6, 1)
		grid.attach(self.lbl_detail0, 	0, 2, 6, 1)
		grid.attach(self.lbl_detail1, 	0, 3, 6, 1)
		grid.attach(self.btn_left, 		0, 4, 1, 1)
		grid.attach(self.btn_right, 	1, 4, 1, 1)
		grid.attach(self.btn_ign, 		2, 4, 1, 1)
		grid.attach(btn_sync, 			4, 4, 1, 1)
		grid.attach(btn_close, 			5, 4, 1, 1)

		self.add(grid)

		self.connect('delete-event', Gtk.main_quit)
		self.show_all()

	def update_liststore(self, changes, pdata, root0, root1):
		def ico(sub_path):
			if pdata[sub_path] != root0[sub_path] and pdata[sub_path] == root1[sub_path]:
				ico = "go-next"
			elif pdata[sub_path] != root1[sub_path] and pdata[sub_path] == root0[sub_path]:
				ico = "go-previous"
			else:
				ico = Gtk.STOCK_CLOSE
			return str(ico)

		def get_state(sub_path, root):
			diff = pdata[sub_path].diff(root[sub_path])
			if diff is data.DiffType.NONE:
				return ""
			elif diff is data.DiffType.NEW:
				return "new"
			elif diff is data.DiffType.REMOVED:
				return "removed"
			elif diff is data.DiffType.TYPE:
				return "file/folder missmatch"
			elif diff is data.DiffType.MODE:
				return "Properties changed"
			elif diff is data.DiffType.MTIME:
				return "mtime changed or file changed"
			elif diff is data.DiffType.CONTENT:
				return "file changed"

		# update column titles with path
		self.column_root0.set_title(root0.path)
		self.column_root1.set_title(root1.path)

		# update content
		for c in changes:
			self.liststore.append([str(c), get_state(c, root0), ico(c), get_state(c, root1)])
		self.liststore.set_sort_column_id(0, Gtk.SortType.ASCENDING)

	def treeview_selection(self, selection):
		def set_labels(model, path, iter, _):
			def to_str(fdata, path):
				if type(fdata) == data.DataFileType:
					return "{0}:\tStat: {1:10}\tModdate: {2:10}\tSize: {3}".format(path, fdata.mode, fdata.mtime, fdata.size)
				elif type(fdata) == data.DataFolderType:
					return "{0}:\tStat: {1}".format(path, fdata.mode)
				return "{0}:\tDid not exist".format(path)

			path = model.get_value(iter, 0)
			data0 = root0[path]
			data1 = root1[path]
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

	def sync(self, _):
		synclist = []
		for entry in self.liststore:
			if entry[2] == Gtk.STOCK_CLOSE:
				continue
			elif entry[2] == "go-previous":
				synclist.append((entry[0], root1, root0))
				# data.do_sync(entry[0], root1, root0)
				# pdata.add(entry[0], root1[entry[0]])
			elif entry[2] == "go-next":
				synclist.append((entry[0], root0, root1))
				# data.do_sync(entry[0], root0, root1)
				# pdata.add(entry[0], root0[entry[0]])
		
		data.do_sync(synclist)
		for sync in synclist:
			pdata.add(sync[0], sync[1][sync[0]])

		next_treeiter = self.liststore.get_iter_first()
		while next_treeiter != None:
			treeiter = next_treeiter
			next_treeiter = self.liststore.iter_next(treeiter)
			if self.liststore[treeiter][2] != Gtk.STOCK_CLOSE:
				self.liststore.remove(treeiter)

class ProgressDialog(Gtk.Dialog):
	def __init__(self, parent):
		super().__init__(title='Loading...', parent=parent)
		self.parent = parent
		self.prevent_close = True
		# self.set_default_size(400, 100)
		self.set_resizable(False)
		self.set_modal(True)

		self.progress = Gtk.ProgressBar(height_request=30)
		self.progress.set_valign(Gtk.Align.CENTER)
		self.progress.set_show_text(True)

		self.add_button('quit', Gtk.ResponseType.CLOSE)

		box = self.get_content_area()
		box.pack_start(self.progress, True, True, 0)

		self.connect("response", self.exit)
		self.connect("delete-event", self.exit)
		# ignore escape key
		self.connect('key-press-event', self.ignore)

		self.show_all()

	def ignore(self, dialog, event):
		return True # Ignore

	def exit(self, dialog, response, *args):
		if response == Gtk.ResponseType.CLOSE:
			self.prevent_close = False
			self.close()
			self.parent.close()
		else:
			return self.prevent_close

window = MainWindow()
dialog = ProgressDialog(window)

def start_gui():
	Gtk.main()

# start gui
gui = threading.Thread(target=start_gui)
gui.start()

# TODO: run in Thread an exit if dialog is closed manually
config, pdata, root0, root1, changes, conflicts = prepare(args.config)
window.update_liststore(changes, pdata, root0, root1)

# prog.join()
dialog.prevent_close = False
dialog.close()