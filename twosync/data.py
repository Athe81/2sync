from stat import S_ISDIR, S_ISREG
from collections import namedtuple
from twosync import utils
from enum import Enum
import paramiko
import hashlib
import os
import pickle
import logging
import shutil

DiffType = Enum('DiffType', 'NONE NEW REMOVED TYPE MODE MTIME CONTENT')
Direction = Enum('Direction', 'LEFT RIGHT')

def do_sync(synclist):
	def cp(sub_path, src_data, dst_data):
		def cp_file(sub_path, src_data, dst_data):
			if isinstance(src_data, SSHData):
				try:
					src_data.sftp_get(src_data.path + sub_path, dst_data.path + sub_path)
				except IOError as e:
					raise
			elif isinstance(dst_data, SSHData):
				try:
					dst_data.sftp_put(src_data.path + sub_path, dst_data.path + sub_path)
				except IOError as e:
					raise
			else:
				shutil.copyfile(src_data.path + sub_path, dst_data.path + sub_path)

		def mkdir(sub_path, src_data, dst_data):
			if isinstance(dst_data, SSHData):
				try:
					dst_data.mkdir(dst_data.path + sub_path, int(src_data[sub_path].mode, 8))
				except IOError as e:
					raise
			else:
				os.mkdir(dst_data.path + sub_path, int(src_data[sub_path].mode, 8))

		if isinstance(src_data[sub_path], DataFileType):
			cp_file(sub_path, src_data, dst_data)
		elif isinstance(src_data[sub_path], DataFolderType):
			mkdir(sub_path, src_data, dst_data)

	def chmod(sub_path, data, mode):
		mode = int(mode, 8)
		if isinstance(data, SSHData):
			data.chmod(data.path + sub_path, mode)
		else:
			os.chmod(data.path + sub_path, mode)

	def utime(sub_path, dst_data, mtime):
		if isinstance(dst_data, SSHData):
			dst_data.utime(dst_data.path + sub_path, mtime)
		else:
			os.utime(dst_data.path + sub_path, times=(mtime, mtime))

	def rm(sub_path, dst_data):
		def rmdir(sub_path, dst_data):
			if isinstance(dst_data, SSHData):
				dst_data.rmdir(dst_data.path + sub_path)
			else:
				os.rmdir(dst_data.path + sub_path)

		def remove(sub_path, dst_data):
			if isinstance(dst_data, SSHData):
				dst_data.remove(dst_data.path + sub_path)
			else:
				os.remove(dst_data.path + sub_path)

		if isinstance(dst_data[sub_path], DataFileType):
			remove(sub_path, dst_data)
		else:
			rmdir(sub_path, dst_data)

	syncnew = [sync for sync in synclist if sync[2][sync[0]].diff(sync[1][sync[0]]) == DiffType.NEW]
	syncrm = [sync for sync in synclist if sync[2][sync[0]].diff(sync[1][sync[0]]) == DiffType.REMOVED]
	syncnew.sort(key=lambda path: path[0])
	syncrm.sort(key=lambda path: path[0], reverse=True)
	synclist = [sync for sync in synclist if sync not in syncnew and sync not in syncrm]

	for sync in syncnew + synclist + syncrm:
		sub_path = sync[0]
		src_data = sync[1]
		dst_data = sync[2]

		diff = dst_data[sub_path].diff(src_data[sub_path])

		if diff in [DiffType.TYPE, DiffType.REMOVED]:
			rm(sub_path, dst_data)

		if diff in [DiffType.NEW, DiffType.TYPE, DiffType.CONTENT]:
			cp(sub_path, src_data, dst_data)

		if diff in [DiffType.NEW, DiffType.TYPE, DiffType.CONTENT, DiffType.MODE]:
			chmod(sub_path, dst_data, src_data[sub_path].mode)

		if diff in [DiffType.NEW, DiffType.TYPE, DiffType.CONTENT, DiffType.MODE, DiffType.MTIME] and isinstance(src_data[sub_path], DataFileType):
			utime(sub_path, dst_data, src_data[sub_path].mtime)

class DataTypeTemplate():
	def diff(self, data):
		"""
		Returns whats the difference from data compared to self as DiffType enum
		"""
		if self == data:
			return DiffType.NONE

		if isinstance(self, DataNoneType):
			return DiffType.NEW

		if isinstance(data, DataNoneType):
			return DiffType.REMOVED

		if type(self) != type(data):
			return DiffType.TYPE

		if isinstance(self, DataFolderType):
			return DiffType.MODE

		if self.size != data.size:
			return DiffType.CONTENT

		if self.mtime != data.mtime:
			# TODO: Compare hash
			# WHILE NOT TESTING HASH, WE RETURN, THAT THE CONTENT HAS CHANGED. JUST TO BE SECURE
			# return DiffType.MTIME
			return DiffType.CONTENT

		if self.mode != data.mode:
			return DiffType.MODE

		raise ExitError("unknown diff %, %", (self, data))

class DataFileType(namedtuple('DataFileType', 'mode, mtime, size'), DataTypeTemplate):
	"""
	namedtuple('DataFileType', 'mode, mtime, size') extended with diff functionality
	"""

class DataFolderType(namedtuple('DataFolderType', 'mode'), DataTypeTemplate):
	"""
	namedtuple('DataFileType', 'mode, mtime, size') extended with diff functionality
	"""

class DataNoneType(namedtuple('DataNoneType', ''), DataTypeTemplate):
	"""
	Special type for data, just for diff functionality
	"""

class BasicData(object):
	def __init__(self):
		self._data = dict()

	def __getitem__(self, key):
		try:
			return self._data[key]
		except KeyError:
			return DataNoneType()

	def add_file(self, sub_path, mode, mtime, size):
		logging.info("Add file '" + sub_path + "' for sync")
		self._data[sub_path] = DataFileType(mode, mtime, size)
		
	def add_folder(self, sub_path, mode):
		logging.info("Add folder '" + sub_path + "' for sync")
		self._data[sub_path] = DataFolderType(mode)

	def remove(self, path):
		del self._data[path]

	@property
	def data(self):
		return self._data

class PersistenceData(BasicData):
	def __init__(self, config):
		logging.info("Init PersistenceData with config changed = " + str(config.config_changed))
		super().__init__()

		self._path_data = config._path_data

		self._load_data()

		# Update sync_data (saved files/folders) if config has changed
		if config.config_changed == True:
			remove = []
			logging.info("Update PersistenceData with new config")
			for path in self.data.keys():
				if isinstance(self.data[path], DataFileType):
					if not config.test_file(path[1:]):
						remove.append(path)
				elif isinstance(self.data[path], DataFolderType):
					if not config.test_folder(path[1:]):
						remove.append(path)
				else:
					print("Corrupt data: type is '" + str(type(self.data[path])) + "'")

			for path in remove:
				self.remove(path)

			config._save_config_hash()
		
	def _load_data(self):
		"""
		Loads the saved information about synchronised files and folders
		"""
		try:
			with open(self._path_data, 'rb') as f:
				self._data = pickle.load(f)
		except FileNotFoundError:
			logging.warn("Could not load data from file: '" + self._path_data + "'. File not found")
		except PermissionError as e:
			twosync.log_and_raise("Could not load data from file: '" + self._path_data + "'. No Permission", e)
		except EOFError as e:
			twosync.log_and_raise("Could not load data from file: '" + self._path_data + "'. File is corrupt", e)
	
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		try:
			with open(self._path_data, 'wb') as f: 
				pickle.dump(self._data, f)
		except Exception as e:
			twosync.log_and_raise("Could not save data to: '" + self._path_data + "'", e)
	
	def add_file(self, file, mode, mtime, size):
		super().add_file(file, mode, mtime, size)
		self._save_data()
		
	def add_folder(self, file, mode):
		super().add_folder(file, mode)
		self._save_data()

	def add(self, sub_path, data):
		self._data[sub_path] = data
		self._save_data()
		
	def remove(self, path):
		super().remove(path)
		self._save_data()

class FSData(BasicData):
	def __init__(self, path, config):
		logging.info("Init FSData with path: '" + path + "'")
		super().__init__()
		self._path = path
		self._find_files(config)

	def _find_files(self, config):
		paths_buf = []
		paths = [self.path + '/']
		while True:
			for path in paths:
				for sub_path in os.listdir(path):
					attr = os.stat(path + sub_path)
					if S_ISDIR(attr.st_mode):
						if config.test_dir(path[len(self.path):] + sub_path):
							sub_path += '/'
							self.add_folder(path[len(self.path):] + sub_path, oct(attr.st_mode)[-3:])
							paths_buf.append(path + sub_path)
					elif S_ISREG(attr.st_mode):
						if config.test_file(path[len(self.path):] + sub_path):
							self.add_file(path[len(self.path):] + sub_path, oct(attr.st_mode)[-3:], abs(int(attr.st_mtime)), attr.st_size)
			if len(paths_buf) == 0:
				break
			paths = paths_buf
			paths_buf = []

	def get_hash(self, sub_path):
		return utils.get_hash(self.path + sub_path)

	@property
	def path(self):
		return self._path

class SSHData(BasicData, paramiko.client.SSHClient):
	class TSPolicy(paramiko.client.MissingHostKeyPolicy):
		"""User-defined MissingHostKeyPolicy"""

		def missing_host_key(self, client, hostname, key):
			# print(str(hostname))
			# print(str(key.get_base64()))
			# print(str([hex(x) for x in key.get_fingerprint()]))
			print(str(key.get_fingerprint()))

			# Raise paramiko.SSHException

	def __init__(self, path, config):
		logging.info("Init SSHData with path: '" + path + "'")
		BasicData.__init__(self)
		paramiko.client.SSHClient.__init__(self)

		self._ssh_adr = path
		self._host = None
		self._port = 22
		self._user = None
		self._path = '/'

		self._parse_adr(self._ssh_adr)
		self.set_missing_host_key_policy(self.TSPolicy())

		self.connect(self._host, self._port, self._user)
		self._sftp_client = self.open_sftp()
		self._find_files(config)

	def _parse_adr(self, ssh_adr):
		"""Returns a tuple with host, port, user and path from the parsed ssh adress"""
		self._host = ssh_adr[6:]

		if self._host.find('@') >= 0:
			self._user, self._host = self._host.split('@')

		if self._host.find("/") >= 0:
			self._host, self._path = self._host.split("/", 1)

		if self._host.find(':') >= 0:
			self._host, portstr = self._host.split(':')
			self._port = int(portstr)

		# Load ssh_config
		conf = paramiko.config.SSHConfig()
		for config_file in ['/etc/ssh/ssh_config', '~/.ssh/config']:
			try:
				conf.parse(open(os.path.expanduser(config_file)))
			except:
				pass

		# Update config with data from ssh_config
		if 'user' in conf.lookup(self._host):
			self._user = conf.lookup(self._host)['user']

		if 'port' in conf.lookup(self._host):
			self._port = int(conf.lookup(self._host)['port'])

		# Must be the last. (after user, port)
		if 'hostname' in conf.lookup(self._host):
			self._host = conf.lookup(self._host)['hostname']

	def _find_files(self, config):
		paths_buf = []
		paths = [self.path + '/']
		while True:
			for path in paths:
				for sub_path in self._sftp_client.listdir_attr(path):
					if S_ISDIR(sub_path.st_mode):
						if config.test_dir(path[len(self.path):] + sub_path.filename):
							sub_path.filename += '/'
							self.add_folder(path[len(self.path):] + sub_path.filename, oct(sub_path.st_mode)[-3:])
							paths_buf.append(path + sub_path.filename)
					elif S_ISREG(sub_path.st_mode):
						if config.test_file(path[len(self.path):] + sub_path.filename):
							self.add_file(path[len(self.path):] + sub_path.filename, oct(sub_path.st_mode)[-3:], abs(int(sub_path.st_mtime)), sub_path.st_size)
			if len(paths_buf) == 0:
				break
			paths = paths_buf
			paths_buf = []

	def get_hash(self, sub_path):
		stdin, stdout, stderr = self.exec_command('sha1sum "' + self.path + sub_path + '"', timeout=10)

		err = stderr.read()
		if len(err) > 0:
			print('Error returned:', err)
		data = stdout.read()
		data, _ = data.split(' ', 1)
		return data

	def _sftp_connection(self):
		if not self.get_transport().is_authenticated():
			self.connect(self._host, self._port, self._user)
		try:
			# Test ist connection ist alive
			self._sftp_client.normalize('.')
		except:
			# Reconnect if not
			self._sftp_client = self.open_sftp()

	def sftp_get(self, remotepath, localpath):
		self._sftp_connection()
		self._sftp_client.get(remotepath, localpath)

	def sftp_put(self, localpath, remotepath):
		self._sftp_connection()
		self._sftp_client.put(localpath, remotepath)

	def chmod(self, path, mode):
		self._sftp_connection()
		self._sftp_client.chmod(path, mode)

	def utime(self, path, mtime):
		self._sftp_connection()
		self._sftp_client.utime(path, times=(mtime, mtime))

	def mkdir(self, path, mode):
		self._sftp_connection()
		self._sftp_client.mkdir(path, mode)

	def rmdir(self, path):
		self._sftp_connection()
		self._sftp_client.rmdir(path)

	def remove(self, path):
		self._sftp_connection()
		self._sftp_client.remove(path)

	@property
	def path(self):
		return self._path