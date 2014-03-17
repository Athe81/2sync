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
	#for (_, pre, post, filters) in parsed_filters:
	for filters in parsed_filters:
		logging.info("Test '" + string + "' with filter: '" + filters.full + "'")
		stat = 1
		str_pos = 0
		sum_filters = len(filters.values)
		for pos in range(sum_filters):
			# zero *, string = filter
			if sum_filters == 1 and filters.preglob == 0 and filters.postglob == 0 and string == filters.values[0]:
				logging.debug("'" + string + "' matched filter: '" + str(filters.full) + "'")
				return True
			# no pre *, first pos, filter != string
			if filters.preglob == 0 and pos == 0 and filters.values[pos] != string[:len(filters.values[pos])]:
				stat = 0
				break
			# no post *, last pos, filter != string
			if filters.postglob == 0 and pos == sum_filters-1 and filters.values[pos] != string[len(filters.values[pos])*-1:]:
				stat = 0
				break
			# one filter, no pre or post *
			if sum_filters == 1 and (filters.preglob == 0 or filters.postglob == 0):
				logging.debug("'" + string + "' matched filter: '" + str(filters.full) + "'")
				return True
			str_pos2 = string[str_pos:].find(filters.values[pos])
			if str_pos2 == -1:
				stat = 0
				break
			str_pos += len(filters.values[pos])
		if stat == 1:
			logging.debug("'" + string + "' matched filter: '" + str(filters.full) + "'")
			return True
		logging.debug("'" + string + "' doesn't matched filter: '" + str(filters.full) + "'")
	return False

def find_changes(pdata, fsdata_1, fsdata_2):
	"""
	Find the changed files and folders. Return 2 lists and 2 sets:
		1 list: changed files as tuple (file, rootnumber)
		2 list: changed folders as tuple (folder, rootnumber)
		3 set: file conflicts
		4 set: folder conflicts
	"""
	fsdata1_changed_files = set([f for (f, *_) in (pdata.files.items() ^ fsdata_1.files.items())])
	fsdata2_changed_files = set([f for (f, *_) in (pdata.files.items() ^ fsdata_2.files.items())])
	conflicts = fsdata1_changed_files & fsdata2_changed_files
	fsdata1_changed_files -= conflicts
	fsdata2_changed_files -= conflicts
	changed_files = [(f,0) for f in fsdata1_changed_files] + [(f,1) for f in fsdata2_changed_files]

	# Remove conflicts on pdata, if fsdata's has no conflict
	remove = set()
	for file in conflicts:
		if fsdata_1.get_file(file) == None and fsdata_2.get_file(file) == None:
			pdata.remove_file(file)
			remove.add(file)
		elif fsdata_1.get_file(file) == fsdata_2.get_file(file) and get_hash(fsdata_1.path + file) == get_hash(fsdata_2.path + file):
			pdata.add_file(file, fsdata_1.get_file(file).stat, fsdata_1.get_file(file).moddate, fsdata_1.get_file(file).size)
			remove.add(file)
	file_conflicts = conflicts - remove

	fsdata1_changed_folders = set([f for (f, *_) in (pdata.folders.items() ^ fsdata_1.folders.items())])
	fsdata2_changed_folders = set([f for (f, *_) in (pdata.folders.items() ^ fsdata_2.folders.items())])
	conflicts = fsdata1_changed_folders & fsdata2_changed_folders
	fsdata1_changed_folders -= conflicts
	fsdata2_changed_folders -= conflicts
	changed_folders = [(f,0) for f in fsdata1_changed_folders] + [(f,1) for f in fsdata2_changed_folders]

	# Remove conflicts on pdata, if fsdata's has no conflict
	remove = set()
	for folder in conflicts:
		if fsdata_1.get_folder(folder) == None and fsdata_2.get_folder(folder) == None:
			pdata.remove_folder(folder)
			remove.add(folder)
		elif fsdata_1.get_folder(folder) == fsdata_2.get_folder(folder):
			pdata.add_folder(folder, fsdata_1.get_folder(folder).stat)
			remove.add(folder)
	folder_conflicts = conflicts - remove

	return changed_files, changed_folders, file_conflicts, folder_conflicts

class BasicData(object):
	_filetype = namedtuple('_filetype', 'stat, moddate, size')
	_foldertype = namedtuple('_foldertype', 'stat')

	def __init__(self):
		self._files = dict()
		self._folders = dict()
		
	def add_file(self, file, stat, moddate, size):
		logging.info("Add file '" + file + "' for sync")
		self._files[file] = self._filetype(stat, moddate, size)
		
	def add_folder(self, folder, stat):
		logging.info("Add folder '" + folder + "' for sync")
		self._folders[folder] = self._foldertype(stat)
		
	def get_file(self, file):
		if file in self._files:
			return self._files[file]
		else:
			return None
		
	def get_folder(self, folder):
		if folder in self._folders:
			return self._folders[folder]
		else:
			return None
	
	def remove_file(self, file):
		del self._files[file]
		
	def remove_folder(self, folder):
		del self._folders[folder]
	
	@property
	def files(self):
		return self._files
	
	@property
	def folders(self):
		return self._folders

class PersistenceData(BasicData):
	# TODO: Convert configname to data filename
	def __init__(self, config_changed):
		logging.info("Init PersistenceData with config changed = " + str(config_changed))
		super().__init__()
		self._load_data()
		# Update sync_data (saved files/folders) if config has changed
		if config_changed == True:
			logging.info("Update PersistenceData with new config")
			for file in self.files.keys():
				if test_string(config['ignore file'], file[1:]) == True:
					self.remove_file(file)
			for folder in self.folders.keys():
				if test_string(config['ignore path'], folder[1:]) == True:
					self.remove_folder(folder)
			config._save_config_hash()
		
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
			for (key, data_type, values) in pickle.load(f):
				if data_type == "file":
					self.add_file(key, values[0], values[1], values[2])
				elif data_type == "folder":
					self.add_folder(key, values[0])
				else:
					log_and_raise("Error on loading Data. Unknown data_type: '" + data_type + "'")
			f.close()
	
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		try:
			with open('saved_data', 'wb') as f: 
				pickle.dump([(k, "file", [v.stat, v.moddate, v.size]) for k, v in self._files.items()] + [(k, "folder", [v.stat]) for k, v in self._folders.items()], f)
		except Exception as e:
			log_and_raise("Could not save data to: '" + 'folders' + "'", e)
	
	def add_file(self, file, stat, moddate, size):
		super().add_file(file, stat, moddate, size)
		self._save_data()
		
	def add_folder(self, file, stat):
		super().add_folder(file, stat)
		self._save_data()
		
	def remove_file(self, file):
		super().remove_file(file)
		self._save_data()
		
	def remove_folder(self, folder):
		super().remove_folder(folder)
		self._save_data()

class FSData(BasicData):
	def __init__(self, path, config_dict):
		logging.info("Init FSData with path: '" + path + "'")
		super().__init__()
		self._path = path
		self._find_files(config_dict)

	def _find_files(self, config_dict):
		"""
		Read files/folders from root's
		
		If file/folder match the filters it will be saved with last modfication date and permissions
		"""

		len_root_path = len(self._path)
		for path, _, files in os.walk(self._path, followlinks=False):
			sub_path = path[len_root_path:] + "/"

			# Add files and folders if 'ignore not path' match to folder
			if test_string(config_dict['ignore not path'], sub_path) == True:
				self.add_folder(sub_path)
				for file in files:
					self.add_file(sub_path + file)
				return
			
			if test_string(config_dict['ignore path'], sub_path) == True:
				return
			
			# Add while 'ignore path' doesn't match
			self.add_folder(sub_path)
			
			for file in files:
				# Add file if 'ignore not file' match the filename
				if test_string(config_dict['ignore not file'], file) == True:
					self.add_file(sub_path + file)
					continue
				
				# Ignore file if the 'ignore file' match the filename
				if test_string(config_dict['ignore file'], file) == True:
					continue
				
				# Add file if 'ignore not file' and 'ignore file' not matched
				self.add_file(sub_path + file)

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

	def _size(self, file):
		"""
		Return the file size
		"""
		try:
			return os.path.getsize(file)
		except OSError as e:
			log_and_raise("Could not read size from: '" + file + "'", e)
	
	def add_file(self, file):
		path = self._path + "/" + file
		super().add_file(file, self._stat(path), self._moddate(path), self._size(path))
		
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
		self.sync_data = PersistenceData(config.config_changed)
		self.root0 = FSData(config.roots[0], config.config_dict)
		self.root1 = FSData(config.roots[1], config.config_dict)
		self.file_conflicts = set()
		self.folder_conflicts = set()
		self.copy = []
		self.remove = []
			
		self._find_changes(config)
		
	def _find_changes(self, config):
		"""
		Prepare the changed files for the synchronisation
		
		Test if files/folders should be syncronised
		Compare it with the saved informations
		Check if conflicts exist (file/folder changed on both root's)
		Ask user for conflict solution
		Save the necessary actions
		"""
		changed_files, changed_folders, file_conflicts, folder_conflicts = find_changes(self.sync_data, self.root0, self.root1)

		# Solve conflicts
		if len(file_conflicts) != 0 or len(folder_conflicts) != 0:
			print("Please solve conflicts:")
		
		
		# TODO: Find out, what changed and just update the changes
		_file_conflicts = set()
		for sub_path in file_conflicts:
			for root in (self.root0, self.root1):
				if sub_path in root.files.keys():
					print("File: " + root.path + sub_path + ", Stat: " + root.files[sub_path].stat + ", Moddate: " + str(root.files[sub_path].moddate) + ", Size: " + str(root.files[sub_path].size))
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
					changed_files.append((sub_path,0))
					break
				elif action == 2:
					changed_files.append((sub_path,1))
					break
				
				print("Wrong input. Please insert a correct input")
				
		file_conflicts = _file_conflicts
		
		_folder_conflict = set()
		for sub_path in folder_conflicts:
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
					_folder_conflict.add(sub_path)
					break
				elif action == 1:
					changed_folders.append((sub_path,0))
					break
				elif action == 2:
					changed_folders.append((sub_path,1))
					break
				
				print("Wrong input. Please insert a correct input")
				
			folder_conflicts = _folder_conflict

		def analyse_action(sub_path, src_root, dst_root, file_folder):
			def mark_for_copy(sub_path, src_root, dst_root, file_folder):
				self.copy.append((sub_path, src_root, dst_root, file_folder))
				
			def mark_for_remove(sub_path, dst_root, file_folder):
				self.remove.append((sub_path, dst_root, file_folder))
				
			if os.path.exists(src_root + sub_path):
				mark_for_copy(sub_path, src_root, dst_root, file_folder)
			else:
				mark_for_remove(sub_path, dst_root, file_folder)
			
		for (f, r) in changed_files:
			if r == 0:
				analyse_action(f, self.root0.path, self.root1.path, 'file')
			else:
				analyse_action(f, self.root1.path, self.root0.path, 'file')
			
		for (f, r) in changed_folders:
			if r == 0:
				analyse_action(f, self.root0.path, self.root1.path, 'folder')
			else:
				analyse_action(f, self.root1.path, self.root0.path, 'folder')
	
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
				if self.root0.path == src_root:
					root = self.root0
				else:
					root = self.root1
				self.sync_data.add_folder(sub_path, root.get_folder(sub_path).stat)
				
		for x in self.copy:
			(sub_path, src_root, dst_root, file_folder) = x
			if file_folder == 'file':
				print('Copy: ' + src_root + sub_path + ' to ' + dst_root + sub_path)
				shutil.copy(src_root + sub_path, dst_root + sub_path)
				shutil.copystat(src_root + sub_path, dst_root + sub_path)
				# Update self.files
				if self.root0.path == src_root:
					root = self.root0
				else:
					root = self.root1
				self.sync_data.add_file(sub_path, root.get_file(sub_path).stat, root.get_file(sub_path).moddate, root.get_file(sub_path).size)
		
		self.remove = list(self.remove)
		self.remove.sort(reverse=True)
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'file']:
			(dst_root, sub_path) = x
			print('Remove file: ' + dst_root + sub_path)
			os.remove(dst_root + sub_path)
			# Update self.files
			self.sync_data.remove_file(sub_path)
			
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'folder']:
			(dst_root, sub_path) = x
			print('Remove folder: ' + dst_root + sub_path)
			os.rmdir(dst_root + sub_path)
			# Update self.folders
			self.sync_data.remove_folder(sub_path)
		
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

	_filter = namedtuple('_filter', 'full, preglob, postglob, values')

	def __init__(self, configname):
		logging.info("Create config object")
		
		self._keys = ['root']
		self._parse_keys = ['ignore not file', 'ignore file', 'ignore not path', 'ignore path']
		self._config = dict()
		self._configname = configname
		self.configname_hash = ".hash_" + configname
		self._hexdigest = ""

		for key in (self._keys + self._parse_keys):
			self._config[key] = []
		
		self._config_changed = self._config_changed(self._configname)
		self._parse(self._configname)
		
	def _config_changed(self, configname):
		"""
		Create sha1 hash for config. Compare it with the existing sha1 hash for config. Save the new hash.
		"""
		logging.info("Check if config-file has changed")
		
		self._hexdigest = get_hash(configname)
		
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
		return self._filter(value, pre, post, value.split("*"))
	
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
	def config_dict(self):
		"""
		Returns the dictionary with the parsed config
		"""
		return self._config
	
	@property
	def roots(self):
		"""
		Returns a list with the roots 
		"""
		return self._config['root']
	
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