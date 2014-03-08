#! /usr/bin/env python3
import os
import pickle
import shutil
import logging

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
	def __init__(self, roots):
		self.roots = []
		self.file_conflicts = set()
		self.folder_conflicts = set()
		self.roots.append(self.data(roots[0]))
		self.roots.append(self.data(roots[1]))
		self.files = []
		self.folders = []
		self.copy = []
		self.remove = []
	
	def _load_data(self):
		"""
		Loads the saved information about synchronised files and folders
		"""
		try:
			f = open('folders', 'rb')
		except FileNotFoundError:
			logging.error("Could not load data from: '" + 'folders' + "' not found")
			pass # TODO: Throw Exception
		else:
			self.folders = pickle.load(f)
			f.close()

		try:
			f = open('files', 'rb')
		except FileNotFoundError:
			logging.error("Could not load data from: '" + 'files' + "' not found")
			pass # TODO: Throw Exception
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
		except:
			logging.error("Could not save data to: '" + 'folders' + "'")
			pass # TODO: Throw Exception
		
		try:
			with open('files', 'wb') as f:
				pickle.dump(self.files, f)
		except:
			logging.error("Could not save data to: '" + 'files' + "'")
			pass # TODO: Throw Exception
			
	def _stat(self, file):
		"""
		Return the permissions for a file or folder
		"""
		try:
			return oct(os.lstat(file).st_mode)[-3:]
		except:
			logging.error("Could not read stat from: '" + file + "'")
		
	def _moddate(self, file):
		"""
		Return the last modification date from a file or folder
		"""
		try:
			return os.lstat(file).st_mtime
		except:
			logging.error("Could not read moddate from: '" + file + "'")
	
	def _test_string(self, parsed_filters, string):
		"""
		Test a string with the ignore filters
		
		Returns True if the file/folder should be synchronised or False if not
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
	
	def _find_files(self, config):
		"""
		Read files/folders from root's
		
		If file/folder match the filters it will be saved with last modfication date and permissions
		"""
		for x in range(len(self.roots)):
			root = self.roots[x]
			len_root_path = len(root.path)
			for path, _, files in os.walk(root.path, followlinks=False):
				# if path == root.path:
					# continue
				sub_path = path[len_root_path:] + "/"
				if self._test_string(config.ignore_not_path, sub_path) == True:
					root.folders[sub_path] = self._stat(root.path + sub_path)
					for file in files:
						file = sub_path + file
						root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
					continue
			
				for file in files:
					if self._test_string(config.ignore_not_file, file) == True:
						file = sub_path + file
						root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
						continue
					if self._test_string(config.ignore_file, file) == True:
						continue
					file = sub_path + file
					root.files[file] = (self._stat(root.path + file), self._moddate(root.path + file))
					
				if self._test_string(config.ignore_path, sub_path) == True:
					continue
				
				root.folders[sub_path] = self._stat(root.path + sub_path)
				
	def find_changes(self, config):
		"""
		Prepare the changed files for the synchronisation
		
		Test if files/folders should be syncronised
		Compare it with the saved informations
		Check if conflicts exist (file/folder changed on both root's)
		Ask user for conflict solution
		Save the necessary actions  
		"""
		self._load_data()
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

		new_file_conflict = set()
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
				except KeyboardInterrupt:
					print()
					exit()
				except:
					action = -1
					pass
				
				if action == 0:
					new_file_conflict.add(sub_path)
					break
				elif action == 1:
					self.roots[1].changed_files.remove(sub_path)
					break
				elif action == 2:
					self.roots[0].changed_files.remove(sub_path)
					break
				
				print("Wrong input. Please insert a correct input")
				
		self.file_conflicts = new_file_conflict
		
		new_folder_conflict = set()
		for sub_path in self.folder_conflicts:
			for x in range(len(self.roots)):
				if sub_path in self.roots[x].folders.keys():
					stat = self.roots[x].folders[sub_path]
					print("Folder: " + self.roots[x].path + sub_path + ", Stat: " + stat)
				else:
					print("Folder: " + self.roots[x].path + sub_path + " deleted")
			while True:
				action = input("0: ignore, 1: " + self.roots[0].path + sub_path + " is master, 2: " + self.roots[1].path + sub_path + " is master ")
				try: action = int(action)
				except: action = -1
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
	def __init__(self):
		logging.debug("Create config object")
		
		self._keys = ['root']
		self._parse_keys = ['ignore not file', 'ignore file', 'ignore not path', 'ignore path']
		self._config = dict()
		
		for key in (self._keys + self._parse_keys): 
			self._config[key] = []
	
	def _parse_exp(self, value):
		"""
		Parses the "ignore" values
		
		Is used to parse the ignore values. After parsing it can be used with "test_string"
		"""
		logging.debug("Parse expression: '" + value + "'")
		
		pre, post = 0, 0
		if value[:1] == "*":
			pre = 1
			value = value[1:]
		if value[-1:] == "*":
			post = 1
			value = value[:-1]
		return (pre, post, value.split("*"))
	
	def parse(self, path):
		"""
		Parse a config-file
		
		Parse the given config-file an test if the config-file match the specifications  
		"""
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
					logging.error("Invalid key: '" + key + "' in config-file: '" + filename + "'")
					# TODO: Throw error
					return 1
				if key in self._parse_keys:
					value = self._parse_exp(value)
				# save value to key
				config = self._config[key]
				config.append(value)
				
		except FileNotFoundError:
			logging.critical("Config-file: '" + filename + "' could not found")
			# TODO: Throw errornotwendig
			return 1
		# Check 2 roots exist
		if len(self._config['root']) != 2:
			logging.critical("Config-file: '" + filename + "' need to had 2 root keys")
			# TODO: Throw error
			return 1
		return 0
	
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

# Config logging
# Logging to file
logging.basicConfig(level=logging.DEBUG, filename='2sync.log', filemode='w')
# define a Handler for sys.stderr and add it
console = logging.StreamHandler()
console.setLevel(logging.WARNING)
logging.getLogger('').addHandler(console)

config = config()
if config.parse('config') != 0:
	print("Error: Config file has error")
	exit()

sync = sync(config.roots)
sync.find_changes(config)

sync.do_action()

logging.info("Exit program")
