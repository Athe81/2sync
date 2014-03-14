#! /usr/bin/env python3
import os
import sys
import pickle
import shutil
import logging
import argparse
import hashlib
from collections import namedtuple

def log_and_raise(msg, e=None):
	"""
	Log the exception message an raise a ExitError
	
	The ExitError is for exceptions with a known reason.
	Exceptions with a unknown reason should not be handelt with this function. 
	"""
	logging.critical(msg)
	if e != None:
		logging.debug(e)
	raise ExitError(msg)

class ExitError(Exception):
	"""
	User-defined Exception for all known Exceptions
	
	This is used for Exceptions who stop the programm, with an known reason.
	If the reason is unknown the original Exception will passed to the main program 
	"""
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

def get_hash(file):
	"""
	Returns the SHA1 hash of a file
	"""
	_config_hash = hashlib.sha1()
	
	try:
		f = open(file, 'rb')
		_config_hash.update(f.read())
	except FileNotFoundError as e:
		log_and_raise("File: '" + file + "' does not exist", e)
	except PermissionError as e:
		log_and_raise("No permission to file: '" + file + "'", e)
	f.close()
	return _config_hash.hexdigest()

def test_string(parsed_filters, string):
	"""
	Test a string with the given, parsed filters
	
	Returns True if the string match or False if not
	"""
	for (pre, post, filters) in parsed_filters:
		stat = 1
		str_pos = 0
		sum_filters = len(filters)
		for pos in range(sum_filters):
			if sum_filters == 1 and pre == 0 and post == 0 and string == filters[0]:
				logging.debug("'" + string + "' matched filter: '" + str(pre) + ", " + str(post) + ", " + str(filters) + "'")
				return True
			if pre == 0 and pos == 0 and filters[pos] != string[:len(filters[pos])]:
				stat = 0
				break
			if post == 0 and pos == sum_filters-1 and filters[pos] != string[len(filters[pos])*-1:]:
				stat = 0
				break
			if sum_filters == 1 and (pre == 0 or post == 0):
				logging.debug("'" + string + "' matched filter: '" + str(pre) + ", " + str(post) + ", " + str(filters) + "'")
				return True
			str_pos = string[str_pos:].find(filters[pos])
			if str_pos == -1:
				stat = 0
				break
			str_pos += len(filters[pos])
		if stat == 1:
			logging.debug("'" + string + "' matched filter: '" + str(pre) + ", " + str(post) + ", " + str(filters) + "'")
			return True
		logging.debug("'" + string + "' doesn't matched filter: '" + str(pre) + ", " + str(post) + ", " + str(filters) + "'")
	return False

class BasicData(object):
	_filetype = namedtuple('_filetype', 'stat, moddate')
	_foldertype = namedtuple('_foldertype', 'stat')

	def __init__(self):
		self._files = dict()
		self._folders = dict()
		
	def add_file(self, file, stat, moddate):
		self._files[file] = self._filetype(stat, moddate)
		
	def add_folder(self, folder, stat):
		self._folders[folder] = self._foldertype(stat)
		
	def get_file(self, file):
		return self._files[file]
		
	def get_folder(self, folder):
		return self._folders[folder]
	
	@property
	def files(self):
		# return [(k, v) for k, v in self._files.items()]
		return self._files
	
	@property
	def folders(self):
		# return [(k, v) for k, v in self._folders.items()]
		return self._folders

class PersistenceData(BasicData):
	# TODO: Convert configname to data filename
	def __init__(self):
		super().__init__()
		self._load_data()
		
	def _load_data(self):
		"""
		Loads the saved information about synchronised files and folders
		"""
		try:
			f = open('saved_data', 'rb')
		except FileNotFoundError:
			logging.warn("Could not load data from file: '" + 'files' + "'. File not found")
		except PermissionError as e:
			log_and_raise("Could not load data from file: '" + 'folders' + "'. No Permission", e)
		else:
			for (key, values) in pickle.load(f):
				if len(values) == 2:
					self.add_file(key, values[0], values[1])
				else:
					self.add_folder(key, values[0])
			f.close()
	
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		try:
			with open('saved_data', 'wb') as f: 
				pickle.dump([(k, [v.stat, v.moddate]) for k, v in self._files.items()] + [(k, [v.stat]) for k, v in self._folders.items()], f)
		except Exception as e:
			log_and_raise("Could not save data to: '" + 'folders' + "'", e)
	
	def add_file(self, file, stat, moddate):
		super().add_file(file, stat, moddate)
		self._save_data()
		
	def add_folder(self, file, stat):
		super().add_folder(file, stat)
		self._save_data()

class FSData(BasicData):
	def _stat(self, file):
		"""
		Return the permissions for a file or folder
		"""
		try:
			return oct(os.lstat(file).st_mode)[-3:]
		except PermissionError:
			log_and_raise("Could not read stat from: '" + file + "'", e)
	
	def _moddate(self, file):
		"""
		Return the last modification date from a file or folder
		"""
		try:
			return os.lstat(file).st_mtime
		except Exception as e:
			log_and_raise("Could not read moddate from: '" + file + "'", e)
			
	def __init__(self, path):
		self._path = path
		super().__init__()
	
	def add_file(self, file):
		path = self._path + "/" + file
		super().add_file(file, self._stat(path), self._moddate(path))
		
	def add_folder(self, folder):
		path = self._path + "/" + folder
		super().add_folder(folder, self._stat(path))
		
	@property
	def path(self):
		return self._path

class sync(object):
	"""
	Main class for the syncronisation
	"""
	def __init__(self, config):
		self.sync_data = PersistenceData()
		self.root0 = FSData(config.roots[0])
		self.root1 = FSData(config.roots[1])
		self.file_conflicts = set()
		self.folder_conflicts = set()
		self.files = []
		self.folders = []
		self.copy = []
		self.remove = []
		
		self._load_data()
		if config.config_changed == True:
			self.files = [(x, y) for x, y in self.files if test_string(config.ignore_file, x[1:]) == False]
			self.folders = [(x, y) for x, y in self.folders if test_string(config.ignore_path, x[1:]) == False]
			self._save_data
			config._save_config_hash()
			
		self._find_changes(config)
		# self._find_changes(config)
	
	def _load_data(self):
		"""
		Loads the saved information about synchronised files and folders
		"""
		try:
			f = open('folders', 'rb')
		except FileNotFoundError:
			logging.warn("Could not load data from file: '" + 'folders' + "'. File not found")
		except PermissionError as e:
			log_and_raise("Could not load data from file: '" + 'folders' + "'. No Permission", e)
		else:
			self.folders = pickle.load(f)
			f.close()

		try:
			f = open('files', 'rb')
		except FileNotFoundError:
			logging.warn("Could not load data from file: '" + 'files' + "'. File not found")
		except PermissionError as e:
			log_and_raise("Could not load data from file: '" + 'folders' + "'. No Permission", e)
		else:
			self.files = pickle.load(f)
			f.close()
			
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		try:
			with open('folders', 'wb') as f: 
				pickle.dump(self.folders, f)
		except :
			log_and_raise("Could not save data to: '" + 'folders' + "'")
		
		try:
			with open('files', 'wb') as f:
				pickle.dump(self.files, f)
		except PermissionError:
			log_and_raise("Could not save data to: '" + 'files' + "'", e)
			
	def _stat(self, file):
		"""
		Return the permissions for a file or folder
		"""
		try:
			return oct(os.lstat(file).st_mode)[-3:]
		except PermissionError:
			log_and_raise("Could not read stat from: '" + file + "'", e)
		
	def _moddate(self, file):
		"""
		Return the last modification date from a file or folder
		"""
		try:
			return os.lstat(file).st_mtime
		except Exception as e:
			log_and_raise("Could not read moddate from: '" + file + "'", e)
				
	def _find_files(self, config):
		"""
		Read files/folders from root's
		
		If file/folder match the filters it will be saved with last modfication date and permissions
		"""
		def _test_and_add(sub_path, files):
			"""
			Test files and folder with ignore filters and returns the files and folder who sould synchronised
			"""
			# Add files and folders if 'ignore not path' match to folder
			if test_string(config.ignore_not_path, sub_path) == True:
				root.add_folder(sub_path)
				for file in files:
					root.add_file(sub_path + file)
				return
			
			if test_string(config.ignore_path, sub_path) == True:
				return
			
			# Add while 'ignore path' doesn't match
			root.add_folder(sub_path)
			
			for file in files:
				# Add file if 'ignore not file' match the filename
				if test_string(config.ignore_not_file, file) == True:
					root.add_file(sub_path + file)
					continue
				
				# Ignore file if the 'ignore file' match the filename
				if test_string(config.ignore_file, file) == True:
					continue
				
				# Add file if 'ignore not file' and 'ignore file' not matched
				root.add_file(sub_path + file)

		for root in (self.root0, self.root1):
			len_root_path = len(root.path)
			logging.debug("Test files for root: '" + root.path + "'")
			for path, _, files in os.walk(root.path, followlinks=False):
				sub_path = path[len_root_path:] + "/"
				_test_and_add(sub_path, files)
		
	def _find_changes(self, config):
		"""
		Prepare the changed files for the synchronisation
		
		Test if files/folders should be syncronised
		Compare it with the saved informations
		Check if conflicts exist (file/folder changed on both root's)
		Ask user for conflict solution
		Save the necessary actions  
		"""
		self._find_files(config)
		
		for root in (self.root0, self.root1):
			root.changed_files = self.sync_data.files.items() ^ root.files.items()
			root.changed_folders = self.sync_data.folders.items() ^ root.folders.items()
			root.changed_files = set([f for (f, *_) in root.changed_files])
			root.changed_folders = set([f for (f, *_) in root.changed_folders])
		
		self.file_conflicts = self.root0.changed_files & self.root1.changed_files
		self.folder_conflicts = self.root0.changed_folders & self.root1.changed_folders
		
		for file in self.root0.files:
			self.sync_data.add_file(file, stat=self.root0.get_file(file).stat, moddate=self.root0.get_file(file).moddate)
		for folder in self.root0.folders:
			self.sync_data.add_folder(folder, stat=self.root0.get_folder(folder).stat)
		
		# for sub_path in self.file_conflicts:
			# TODO: WORK 
			# self._inspect_content(sub_path)
		
		# Solve conflicts
		if len(self.file_conflicts) != 0 or len(self.folder_conflicts) != 0:
			print("Please solve conflicts:")

		_file_conflicts = set()
		for sub_path in self.file_conflicts:
			for root in (self.root0, self.root1):
				if sub_path in root.files.keys():
					print("File: " + root.path + sub_path + ", Stat: " + root.files[sub_path].stat + ", Moddate:" + str(root.files[sub_path].moddate))
				else:
					print("File: " + root.path + sub_path + " deleted")
			while True:
				try:
					action = int(input("0: ignore, 1: " + self.root0.path + sub_path + " is master, 2: " + self.root1.path + sub_path + " is master "))
				except ValueError:
					action = -1
				
				if action == 0:
					_file_conflicts.add(sub_path)
					break
				elif action == 1:
					self.root1.changed_files.remove(sub_path)
					break
				elif action == 2:
					self.root0.changed_files.remove(sub_path)
					break
				
				print("Wrong input. Please insert a correct input")
				
		self.file_conflicts = _file_conflicts
		
		new_folder_conflict = set()
		for sub_path in self.folder_conflicts:
			for root in (self.root0, self.root1):
				if sub_path in root.folders.keys():
					print("Folder: " + root.path + sub_path + ", Stat: " + root.folders[sub_path].stat)
				else:
					print("Folder: " + root.path + sub_path + " deleted")
			while True:
				try:
					action = int(input("0: ignore, 1: " + self.root0.path + sub_path + " is master, 2: " + self.root1.path + sub_path + " is master "))
				except ValueError:
					action = -1
					
				if action == 0:
					new_folder_conflict.add(sub_path)
					break
				elif action == 1:
					self.root1.changed_folders.remove(sub_path)
					break
				elif action == 2:
					self.root0.changed_folders.remove(sub_path)
					break
				
				print("Wrong input. Please insert a correct input")
				
			self.folder_conflicts = new_folder_conflict
				
		for root in (self.root0, self.root1):
			def analyse_action(sub_path, src_root, dst_root, file_folder, conflicts):
				def mark_for_copy(sub_path, src_root, dst_root, file_folder):
					self.copy.append((sub_path, src_root, dst_root, file_folder))
					
				def mark_for_remove(sub_path, dst_root, file_folder):
					self.remove.append((sub_path, dst_root, file_folder))
					
				if filename in conflicts:
					return
				if os.path.exists(src_root + sub_path):
					mark_for_copy(sub_path, src_root, dst_root, file_folder)
				else:
					mark_for_remove(sub_path, dst_root, file_folder)
			if root == self.root0:
				other_root = self.root1
			else:
				other_root = self.root0
				
			for filename in root.changed_files:
				analyse_action(filename, root.path, other_root.path, 'file', self.file_conflicts)
				
			for filename in root.changed_folders:
				analyse_action(filename, root.path, other_root.path, 'folder', self.folder_conflicts)
	
	def do_action(self):
		"""
		Execute the syncronisation
		"""
		self.copy = list(self.copy)
		self.copy.sort()
		for x in self.copy:
			(sub_path, src_root, dst_root, file_folder) = x
			if file_folder == 'folder':
				if not os.path.exists(dst_root + sub_path):
					print("Create dir: " + dst_root + sub_path)
					os.mkdir(dst_root + sub_path)
				print('Update ' + dst_root + sub_path + ' with data from ' + src_root + sub_path)
				shutil.copystat(src_root + sub_path, dst_root + sub_path)
				# Update self.folders
				self.folders = [(folder, stat) for (folder, stat) in self.folders if folder != sub_path] + [(sub_path, self._stat(src_root + sub_path))]
				
		for x in self.copy:
			(sub_path, src_root, dst_root, file_folder) = x
			if file_folder == 'file':
				print('Copy: ' + src_root + sub_path + ' to ' + dst_root + sub_path)
				shutil.copy(src_root + sub_path, dst_root + sub_path)
				shutil.copystat(src_root + sub_path, dst_root + sub_path)
				# Update self.files
				self.files = [(file, stat_mod) for (file, stat_mod) in self.files if file != sub_path] + [(sub_path, (self._stat(src_root + sub_path), self._moddate(src_root + sub_path)))]
		
		self.remove = list(self.remove)
		self.remove.sort(reverse=True)
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'file']:
			(dst_root, sub_path) = x
			print('Remove file: ' + dst_root + sub_path)
			os.remove(dst_root + sub_path)
			# Update self.files
			self.files = [(file, stat_mod) for (file, stat_mod) in self.files if file != sub_path]
			
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'folder']:
			(dst_root, sub_path) = x
			print('Remove folder: ' + dst_root + sub_path)
			os.rmdir(dst_root + sub_path)
			# Update self.folders
			self.folders = [(folder, stat) for (folder, stat) in self.folders if folder != sub_path]
			
		self._save_data()
		
class config(object):
	"""
	The config object open a config file an prepare it for usage
	
	After parsing a config file. The Data can be used for the program.
	The format ist spezialised for this program. It has the following keys:
		root: Is a path for the folders who sould synchronised (has to set 2 times: "source" and "target")
		ignore file: which files has to be ignored for synchronisation
		ignore path: which directories has to be ignored for synchronisation
		ignore not file: files who sould synchronised, but match ignore file
		ignore not path: directory who sould synchronised, but match ignore path
	root has to be a absolutley path to a directory
	All ignore-keys can use * at the value as placeholder for everything
	"""
	def __init__(self, configname):
		logging.info("Create config object")
		
		self._keys = ['root']
		self._parse_keys = ['ignore not file', 'ignore file', 'ignore not path', 'ignore path']
		self._config = dict()
		self._configname = configname
		self._hexdigest = ""
		self.configname_hash = ".hash_" + configname
		
		for key in (self._keys + self._parse_keys):
			self._config[key] = []
		
		self._config_changed = self._config_changed(self._configname)
		self._parse(self._configname)
		
	def _config_changed(self, configname):
		"""
		Create sha1 hash for config. Compare it with the existing sha1 hash for config. Save the new hash.
		"""
		logging.info("Check if config-file has changed")
		_config_hash = hashlib.sha1()
		
		try:
			f = open(configname, 'rb')
			_config_hash.update(f.read())
			self._hexdigest = _config_hash.hexdigest()
		except FileNotFoundError as e:
			log_and_raise("Config-file: '" + configname + "' does not exist", e)
		except PermissionError as e:
			log_and_raise("No permission to config-file: '" + configname + "'", e)
		else:
			f.close()
		
		saved_hash = ''
		try:
			f = open(self.configname_hash, 'r')
		except FileNotFoundError:
			logging.info("No hash key for config-file: '" + configname + "'")
		except PermissionError as e:
			log_and_raise("No permission to read hash-file: '" + self.configname_hash + "'", e)
			pass
		else:
			saved_hash = f.read()
			saved_hash[:-1]
			f.close()
		
		if self._hexdigest == saved_hash:
			logging.info("config-file has not changed")
			return False
		logging.info("config-file has changed")
		return True
	
	def _save_config_hash(self):
		try:
			f = open(self.configname_hash, 'w')
			f.write(self._hexdigest)
		except PermissionError as e:
			log_and_raise("No permission to write hash-file: '" + self.configname_hash + "'", e)
		else:
			f.close()
	
	def _parse_exp(self, value):
		"""
		Parses the "ignore" values
		
		Is used to parse the ignore values. After parsing it can be used with "test_string"
		"""
		logging.info("Parse expression: '" + value + "'")
		
		pre, post = 0, 0
		if value[:1] == "*":
			pre = 1
			value = value[1:]
		if value[-1:] == "*":
			post = 1
			value = value[:-1]
		return (pre, post, value.split("*"))
	
	def _parse(self, path):
		"""
		Parse a config-file
		
		Parse the given config-file an test if the config-file match the specifications  
		"""
		
		logging.info("Parse config-file: '" + path + "'")
		try:
			# Open config file and parse content.
			for line in open(path, 'r'):
				# remove whitespaces
				line = line.strip()
				# ignore if comment and empty line
				if line[0:1] == '#' or len(line) == 0:
					continue
				# split line into key, value
				key, value = line.split("=", 1)
				# remove whitespaces
				key = key.strip()
				value = value.strip()
				if not key in (self._keys + self._parse_keys):
					log_and_raise("Invalid key: '" + key + "' in config-file: '" + path + "'")
				if key in self._parse_keys:
					value = self._parse_exp(value)
				# save value to key
				config = self._config[key]
				config.append(value)
				
		except FileNotFoundError as e:
			log_and_raise("Config-file: '" + path + "' does not exist", e)
		
		except PermissionError as e:
			log_and_raise("No permission on config-file: '" + path + "'", e)
			
		# Check if 2 roots exist
		if len(self._config['root']) != 2:
			log_and_raise("Config-file: '" + path + "' need to had 2 root keys", e)
	
	@property
	def roots(self):
		"""
		Returns a list with the roots 
		"""
		return self._config['root']
	
	@property
	def ignore_file(self):
		"""
		Returns a list with the parsed 'ignore file' values
		"""
		return self._config['ignore file']
	
	@property
	def ignore_not_file(self):
		"""
		Returns a list with the parsed 'ignore not file' values
		"""
		return self._config['ignore not file']
	
	@property
	def ignore_path(self):
		"""
		Returns a list with the parsed 'ignore path' values
		"""
		return self._config['ignore path']
	
	@property
	def ignore_not_path(self):
		"""
		Returns a list with the parsed 'ignore not path' values
		"""
		return self._config['ignore not path']
	
	@property
	def config_changed(self):
		"""
		Returns True if the config has changed or is new. Otherwise it returns False
		"""
		return self._config_changed
	
	@property
	def configname(self):
		"""
		Returns the config name
		"""
		return self._configname

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
	config = config(args.config)
	sync = sync(config)
	sync.do_action()
except ExitError:
	pass
except KeyboardInterrupt:
	print()
	logging.critical("Exit programm while KeyboardInterrupt (ctrl + c)")
except Exception as e:
	logging.critical("Unknown error", e)
	
logging.info("Exit program")
