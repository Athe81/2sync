#! /usr/bin/env python3
import os
import sys
import pickle
import shutil
import logging
import argparse
import hashlib

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
				return True
			if pre == 0 and pos == 0 and filters[pos] != string[:len(filters[pos])]:
				stat = 0
				break
			if post == 0 and pos == sum_filters-1 and filters[pos] != string[len(filters[pos])*-1:]:
				stat = 0
				break
			if sum_filters == 1 and (pre == 0 or post == 0):
				return True
			str_pos = string[str_pos:].find(filters[pos])
			if str_pos == -1:
				stat = 0
				break
			str_pos += len(filters[pos])
		if stat == 1:
			return True
	return False

class sync():
	"""
	Main class for the syncronisation
	"""
	class data():
		"""
		A class for a root
		
		Holds the root specific data's
		"""
		def __init__(self, path):
			self.path = path
			self.files = dict()
			self.folders = dict()
			self.changed_files = set()
			self.changed_folders = set()
	def __init__(self, config):
		roots = config.roots
		self.roots = []
		self.file_conflicts = set()
		self.folder_conflicts = set()
		self.roots.append(self.data(roots[0]))
		self.roots.append(self.data(roots[1]))
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
		for x in range(len(self.roots)):
			root = self.roots[x]
			len_root_path = len(root.path)
			for path, _, files in os.walk(root.path, followlinks=False):
				sub_path = path[len_root_path:] + "/"
				if test_string(config.ignore_not_path, sub_path) == True:
					root.folders[sub_path] = self._stat(root.path + sub_path)
					for file in files:
						file = sub_path + file
						root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
					continue
			
				for file in files:
					if test_string(config.ignore_not_file, file) == True:
						file = sub_path + file
						root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
						continue
					if test_string(config.ignore_file, file) == True:
						continue
					file = sub_path + file
					root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
					
				if test_string(config.ignore_path, sub_path) == True:
					continue
				
				root.folders[sub_path] = self._stat(root.path + sub_path)
				
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
		for x in range(len(self.roots)):
			root = self.roots[x]
			root.changed_files = set(self.files) ^ set([(x, y) for x, y in root.files.items()])
			root.changed_folders = set(self.folders) ^ set([(x, y) for x, y in root.folders.items()])
			root.changed_files = set([f for (f, *_) in root.changed_files])
			root.changed_folders = set([f for (f, *_) in root.changed_folders])
			
		self.file_conflicts = set(self.roots[0].changed_files) & set(self.roots[1].changed_files)
		self.folder_conflicts = set(self.roots[0].changed_folders) & set(self.roots[1].changed_folders)
		
		# Solve conflicts
		if len(self.file_conflicts) != 0 or len(self.folder_conflicts) != 0:
			print("Please solve conflicts:")

		_file_conflicts = set()
		for sub_path in self.file_conflicts:
			for x in range(len(self.roots)):
				if sub_path in self.roots[x].files.keys():
					stat, moddate = self.roots[x].files[sub_path]
					print("File: " + self.roots[x].path + sub_path + ", Stat: " + stat + ", Moddate:" + str(moddate))
				else:
					print("File: " + self.roots[x].path + sub_path + " deleted")
			while True:
				try:
					action = int(input("0: ignore, 1: " + self.roots[0].path + sub_path + " is master, 2: " + self.roots[1].path + sub_path + " is master "))
				except ValueError:
					action = -1
				
				if action == 0:
					_file_conflicts.add(sub_path)
					break
				elif action == 1:
					self.roots[1].changed_files.remove(sub_path)
					break
				elif action == 2:
					self.roots[0].changed_files.remove(sub_path)
					break
				
				print("Wrong input. Please insert a correct input")
				
		self.file_conflicts = _file_conflicts
		
		new_folder_conflict = set()
		for sub_path in self.folder_conflicts:
			for x in range(len(self.roots)):
				if sub_path in self.roots[x].folders.keys():
					stat = self.roots[x].folders[sub_path]
					print("Folder: " + self.roots[x].path + sub_path + ", Stat: " + stat)
				else:
					print("Folder: " + self.roots[x].path + sub_path + " deleted")
			while True:
				try:
					action = int(input("0: ignore, 1: " + self.roots[0].path + sub_path + " is master, 2: " + self.roots[1].path + sub_path + " is master "))
				except KeyboardInterrupt:
					print()
					logging.critical("Exit programm while KeyboardInterrupt (ctrl + c)")
					exit()
				except ValueError:
					action = -1
					
				if action == 0:
					new_folder_conflict.add(sub_path)
					break
				elif action == 1:
					self.roots[1].changed_folders.remove(sub_path)
					break
				elif action == 2:
					self.roots[0].changed_folders.remove(sub_path)
					break
				
				print("Wrong input. Please insert a correct input")
				
			self.folder_conflicts = new_folder_conflict
				
		for x in range(len(self.roots)):
			root = self.roots[x]
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
					
			for filename in root.changed_files:
				analyse_action(filename, root.path, self.roots[1-x].path, 'file', self.file_conflicts)
				
			for filename in root.changed_folders:
				analyse_action(filename, root.path, self.roots[1-x].path, 'folder', self.folder_conflicts)
	
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
			return False
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
args = parser.parse_args()

# Config logging
# Logging to file
logging.basicConfig(level=logging.INFO, filename='2sync.log', filemode='a', format='%(levelname)s: %(asctime)s - 2sync - %(message)s')
# define a Handler for sys.stderr and add it
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
logging.getLogger('').addHandler(console)

try:
	config = config(args.config)
	sync = sync(config)
#	sync.find_changes(config)
	sync.do_action()
except ExitError:
	pass
except KeyboardInterrupt:
	print()
	logging.critical("Exit programm while KeyboardInterrupt (ctrl + c)")
except Exception as e:
	logging.critical("Unknown error", e)
	
logging.info("Exit program")
