from gi.repository import Gtk, GLib, GObject
from twosync import config, data, utils
import threading
import paramiko
import socket

class TSPolicy(paramiko.client.MissingHostKeyPolicy):
	"""User-defined MissingHostKeyPolicy"""
	transient_for = None

	@classmethod
	def set_transient_for(cls, transient_for):
		cls.transient_for = transient_for

	@classmethod
	def get_transient_for(cls):
		return cls.transient_for

	def missing_host_key(self, client, hostname, key):
		fingerprint = ''
		for x in key.get_fingerprint():
			if len(fingerprint) > 0:
				fingerprint += ":"
			fingerprint += hex(x)[-2:]

		text = 'Missing host key for %s' % hostname
		secondary_text = 'Unknown fingerprint:\n%s\n\nDo you like to add?' % fingerprint
		
		missing_host_key_dlg = MissingHostKeyDlg(text, secondary_text, self.get_transient_for())

		if missing_host_key_dlg.ask():
			paramiko.client.AutoAddPolicy().missing_host_key(client, hostname, key)
		else:
			# Raise an own error
			paramiko.client.RejectPolicy().missing_host_key(client, hostname, key)

class MainWin(object):
	def __init__(self, pdata, roots):
		self.builder = Gtk.Builder()
		self.builder.add_from_file("glade/main_win.glade")
		self.builder.connect_signals(self)

		self.win = self.builder.get_object('win_sync')
		self.root0_column = self.builder.get_object('win_sync_treeview_column_root0')
		self.root1_column = self.builder.get_object('win_sync_treeview_column_root1')
		self.treestore = self.builder.get_object('win_sync_treestore')
		self.treeview = self.builder.get_object('win_sync_treeview')
		self.btn_left = self.builder.get_object('win_sync_tbt_left')
		self.btn_right = self.builder.get_object('win_sync_tbt_right')
		self.btn_none = self.builder.get_object('win_sync_tbt_none')
		self.btn_sync = self.builder.get_object('win_sync_tbt_sync')

		self.lbl_sub_path = self.builder.get_object('lbl_sub_path')
		self.lbl_root0_path = self.builder.get_object('lbl_root0_path')
		self.lbl_root1_path = self.builder.get_object('lbl_root1_path')
		self.lbl_root0_detail = self.builder.get_object('lbl_root0_detail')
		self.lbl_root1_detail = self.builder.get_object('lbl_root1_detail')

		self.pdata = pdata
		self.roots = roots

	def show_all(self, blocking=False):
		GLib.idle_add(self.win.show_all)

	def run(self):
		self.win.run()

	def set_sensitive(self, widget, state):
		GLib.idle_add(widget.set_sensitive, state)

	def set_toolbuttons_sensitive(self, state):
		self.set_sensitive(self.btn_left, state)
		self.set_sensitive(self.btn_right, state)
		self.set_sensitive(self.btn_none, state)

	def set_text(self, widget, text):
		GLib.idle_add(widget.set_text, text)

	def set_sync_icon(self, icon_name):
		(_, selections) = self.treeview.get_selection().get_selected_rows()
		for selection in selections:
			self.treestore[selection][2] = icon_name
			self.treeview.grab_focus()

	def do_update_liststore(self, changes):
		def _update(self, changes):
			def get_icon_name(sub_path, pdata, roots):
				if pdata[sub_path] != roots[0][sub_path] and pdata[sub_path] == roots[1][sub_path]:
					ico = "go-next"
				elif pdata[sub_path] != roots[1][sub_path] and pdata[sub_path] == roots[0][sub_path]:
					ico = "go-previous"
				else:
					ico = Gtk.STOCK_CLOSE

				return str(ico)

			def get_state(sub_path, root):
				diff = self.pdata[sub_path].diff(root[sub_path])
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
			GLib.idle_add(self.root0_column.set_title, self.roots[0].path)
			GLib.idle_add(self.root1_column.set_title, self.roots[1].path)

			# prepare changes as sorted list
			changes = list(changes)
			changes.sort()

			stack = []
			# update content
			for change in changes:
				parent = None
				for pos in range(len(stack), 0, -1):
					if change.startswith(stack[pos-1][0]):
						parent = stack[pos-1][1]
						stack = stack[:pos]
						break

				iter_ = self.treestore.insert(parent, -1, [str(change), get_state(change, self.roots[0]), get_icon_name(change, self.pdata, self.roots), get_state(change, self.roots[1])])

				if type(self.roots[0][change]) == data.DataFolderType or type(self.roots[1][change]) == data.DataFolderType:
					stack.append((change, iter_))

			self.treeview.expand_all()
			self.treestore.set_sort_column_id(0, Gtk.SortType.ASCENDING)

		GLib.idle_add(_update, self, changes)

	def do_sync(self):
		def update_callback(now, max_, path=None):
			if progress_dlg.dlg.get_visible():
				progress_dlg.update(path, now/max_)
			else:
				raise InterruptedError

		buf = []
		rows = []

		progress_dlg = ProgressDlg('2sync - sync data', 'prepare sync', self.win)
		progress_dlg.set_btn_close_event(progress_dlg.close)
		progress_dlg.show_all()

		progress_dlg.update('prepare', 0.1)

		# Get all rows from first level and save in buf
		for row in self.treestore:
			buf.append(row)

		# Get one row from buf and save it in rows
		# Save all childs to buf and loop
		while len(buf) > 0:
			row = buf.pop()
			rows.append(row)
			child_iter = row.iterchildren()
			for child_row in child_iter:
				buf.append(child_row)

		synclist = []
		for row in rows:
			if row[2] == Gtk.STOCK_CLOSE:
				continue
			elif row[2] == "go-previous":
				synclist.append((row[0], self.roots[1], self.roots[0]))
			elif row[2] == "go-next":
				synclist.append((row[0], self.roots[0], self.roots[1]))

		sync = data.SyncData(synclist)
		synced = []
		while not sync.finished():
			try:
				synced.append(sync.sync_next(update_callback))
			except InterruptedError:
				break

			except socket.timeout as e:
				error_dlg = ErrorDlg('2sync - Error', 'Connection timeout', progress_dlg.dlg)
				error_dlg.set_btn_close_event(error_dlg.close)
				error_dlg.run()

			except Exception as e:
				error_dlg = ErrorDlg('2sync - Error', str(e), progress_dlg.dlg)
				error_dlg.set_btn_close_event(error_dlg.close)
				error_dlg.run()

		for sync in synclist:
			if sync[0] in synced:
				self.pdata.add(sync[0], sync[1][sync[0]])
				sync[2].add(sync[0], sync[1][sync[0]])

		GLib.idle_add(self.treestore.clear)
		changes, conflicts = utils.find_changes(self.pdata, self.roots[0], self.roots[1])
		self.do_update_liststore(changes)
		
		# Check if still shown
		if progress_dlg.dlg.get_visible():
			progress_dlg.close()

	###############################
	## signal events
	###############################
	def on_win_sync_delete_event(self, *args):
		for root in self.roots:
			try:
				root.close()
			except:
				pass
		Gtk.main_quit()

	def on_win_sync_treeview_row_activated(self, widget, path, column):
		# TODO: Select all childs
		pass

	def on_win_sync_treeview_selection_changed(self, widget):
		def set_labels(model, path, iter, _):
			def to_str(fdata):
				if type(fdata) == data.DataFileType:
					return "\tStat: %s\tModdate: %s\tSize: %s" % (fdata.mode, fdata.mtime, fdata.size)
				elif type(fdata) == data.DataFolderType:
					return "\tStat: %s" % fdata.mode
				return "\tDid not exist"

			path = model.get_value(iter, 0)
			data0 = self.roots[0][path]
			data1 = self.roots[1][path]
			self.lbl_sub_path.set_text(path)
			self.lbl_root0_path.set_text(self.roots[0].path)
			self.lbl_root1_path.set_text(self.roots[1].path)
			self.lbl_root0_detail.set_text(to_str(data0))
			self.lbl_root1_detail.set_text(to_str(data1))

		if widget.count_selected_rows() > 0:
			self.set_toolbuttons_sensitive(True)
		else:
			self.set_toolbuttons_sensitive(False)

		if widget.count_selected_rows() == 1:
			widget.selected_foreach(set_labels, None)
		else:
			self.set_text(self.lbl_sub_path, "")
			self.set_text(self.lbl_root0_path, "")
			self.set_text(self.lbl_root1_path, "")
			self.set_text(self.lbl_root0_detail, "")
			self.set_text(self.lbl_root1_detail, "")

	def on_win_sync_treestore_row_deleted(self, widget, path):
		if widget.get_iter_first() == None:
			self.set_sensitive(self.btn_sync, False)

	def on_win_sync_treestore_row_inserted(self, widget, path, iter_):
		self.set_sensitive(self.btn_sync, True)

	def on_win_sync_tbt_left_clicked(self, widget):
		self.set_sync_icon("go-previous")

	def on_win_sync_tbt_right_clicked(self, widget):
		self.set_sync_icon("go-next")

	def on_win_sync_tbt_none_clicked(self, widget):
		self.set_sync_icon(Gtk.STOCK_CLOSE)

	def on_win_sync_tbt_sync_clicked(self, widget):
		thread = threading.Thread(target=self.do_sync)
		thread.daemon = True
		thread.start()

class DlgTemplate(object):
	def __init__(self, first_text, secondary_text, gui_file, transient_for=None):
		self.builder = Gtk.Builder()
		self.builder.add_from_file(gui_file)
		self.builder.connect_signals(self)

		self.dlg = self.builder.get_object('dlg')

		self.set_first_text(first_text)
		self.set_secondary_text(secondary_text)
		if transient_for is not None:
			self.set_transient_for(transient_for)

	def show_all(self):
		GLib.idle_add(self.dlg.show_all)

	def close(self):
		GLib.idle_add(self.dlg.close)

	def set_first_text(self, first_text):
		GLib.idle_add(self.dlg.set_markup, '<b>%s</b>' % first_text)

	def set_secondary_text(self, secondary_text):
		GLib.idle_add(self.dlg.format_secondary_text, secondary_text)

	def set_transient_for(self, transient_for):
		GLib.idle_add(self.dlg.set_transient_for, transient_for)

	def run(self):
		def _run(event):
			self.dlg.run()
			event.set()
		event = threading.Event()
		GLib.idle_add(_run, event)
		event.wait()

class ProgressDlg(DlgTemplate):
	def __init__(self, first_text, secondary_text, transient_for=None):
		super().__init__(first_text, secondary_text, "glade/progress_dlg.glade", transient_for)

		self.prg = self.builder.get_object('prg_bar')
		self.btn_close_event = Gtk.main_quit

	def update(self, secondary_text=None, fraction=None):
		if secondary_text != None:
			self.set_secondary_text(secondary_text)

		if fraction != None:
			self.set_fraction(fraction)

	def set_fraction(self, fraction):
		GLib.idle_add(self.prg.set_fraction, fraction)

	def set_btn_close_event(self, event):
		self.btn_close_event = event

	###############################
	## signal events
	###############################
	def on_dlg_response(self, widget, response, *args):
		if response == Gtk.ResponseType.CLOSE:
			self.btn_close_event()

class ErrorDlg(DlgTemplate):
	def __init__(self, first_text, secondary_text, transient_for=None):
		super().__init__(first_text, secondary_text, "glade/error_dlg.glade", transient_for)

		self.btn_close_event = Gtk.main_quit

	def run(self):
		super().run()
		GLib.idle_add(self.btn_close_event)

	def set_btn_close_event(self, event):
		self.btn_close_event = event

	###############################
	## signal events
	###############################
	def on_dlg_response(self, widget, response, *args):
		if response == Gtk.ResponseType.OK:
			if isinstance(self.btn_close_event, list):
				for event in self.btn_close_event:
					event()
			else:
				self.btn_close_event()
				GLib.idle_add(self.dlg.close)

class MissingHostKeyDlg(DlgTemplate):
	def __init__(self, first_text, secondary_text, transient_for=None):
		super().__init__(first_text, secondary_text, "glade/missing_host_key_dlg.glade", transient_for)
		if transient_for != None:
			self.set_transient_for(transient_for)
		self._answer = None

	def ask(self):
		super().run()
		GLib.idle_add(self.dlg.close)
		return self._answer

	###############################
	## signal events
	###############################
	def on_dlg_response(self, widget, response):
		if response == Gtk.ResponseType.YES:
			self._answer = True

		if response == Gtk.ResponseType.NO:
			self._answer = False

class TwoSyncGUI(object):
	def __init__(self, config_name):
		self.roots = []

		progress_dlg = ProgressDlg('2sync - Read data', 'startup')
		progress_dlg.show_all()
		TSPolicy.set_transient_for(progress_dlg.dlg)
		transient_for = progress_dlg.dlg

		try:
			progress_dlg.update('load config', 0.01)
			cfg = config.Config(config_name) # Expected exceptions: PermissionError, FileNotFoundError
			
			progress_dlg.update('load saved data', 0.02)
			self.pdata = data.PersistenceData(cfg) # Expected exceptions: FileNotFoundError, PermissionError, EOFError (File corrupt)

			if cfg.roots[0].startswith('ssh://'):
				progress_dlg.update('connect to %s' % cfg.roots[0], 0.05)
				self.roots.append(data.SSHData(cfg.roots[0], cfg, progress_dlg.update, TSPolicy)) # Expected exceptions: paramiko.ssh_exception.SSHException, socket.gaierror, ConnectionRefusedError
			else:
				progress_dlg.update('read data from %s' % cfg.roots[0], 0.05)
				self.roots.append(data.FSData(cfg.roots[0], cfg, progress_dlg.update)) # Expected exceptions: PermissionError

			if cfg.roots[1].startswith('ssh://'):
				progress_dlg.update('connect to %s' % cfg.roots[1], 0.50)
				self.roots.append(data.SSHData(cfg.roots[1], cfg, progress_dlg.update, TSPolicy)) # Expected exceptions: paramiko.ssh_exception.SSHException, socket.gaierror, ConnectionRefusedError
			else:
				progress_dlg.update('read data from %s' % cfg.roots[1], 0.50)
				self.roots.append(data.FSData(cfg.roots[1], cfg, progress_dlg.update)) # Expected exceptions: PermissionError

			progress_dlg.update('analyse data', 0.95)
			changes, conflicts = utils.find_changes(self.pdata, self.roots[0], self.roots[1])

			main_win = MainWin(self.pdata, self.roots)
			main_win.do_update_liststore(changes)
			main_win.show_all()

			transient_for = main_win.win

			progress_dlg.close()

		# except paramiko.ssh_exception.SSHException as e:
		# 	error_dlg = ErrorDlg('2sync - Error', str(e), transient_for)
		# 	error_dlg.run()

		except socket.timeout as e:
			error_dlg = ErrorDlg('2sync - Error', 'Connection timeout', transient_for)
			error_dlg.run()
			# raise

		except Exception as e:
			error_dlg = ErrorDlg('2sync - Error', str(e), transient_for)
			error_dlg.run()
			# raise

	def quit(self):
		Gtk.main_quit()