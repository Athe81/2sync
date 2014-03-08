#! /usr/bin/env python3
import os
import pickle
import shutil

class sync():
	class data():
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
	
	def __load_data(self):
		try:
			f = open('folders', 'rb')
		except FileNotFoundError:
			pass # TODO: Add Errorhandling
		else:
			self.folders = pickle.load(f)
			f.close()

		try:
			f = open('files', 'rb')
		except FileNotFoundError:
			pass # TODO: Add Errorhandling
		else:
			self.files = pickle.load(f)
			f.close()
			
	def __save_data(self):
		# TODO: Add errorhandling
		with open('folders', 'wb') as f: 
			pickle.dump(self.folders, f)
		with open('files', 'wb') as f:
			pickle.dump(self.files, f)
			
	def __stat(self, file):
		# TODO: Add FileNotFoundError
		return oct(os.lstat(file).st_mode)[-3:]
		
	def __moddate(self, file):
		# TODO: Add FileNotFoundError
		return os.lstat(file).st_mtime
	
	def __test_string(self, parsed_filters, string):
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
	
	def __find_files(self, config):
		for x in range(len(self.roots)):
			root = self.roots[x]
			len_root_path = len(root.path)
			for path, _, files in os.walk(root.path, followlinks=False):
				# if path == root.path:
					# continue
				sub_path = path[len_root_path:] + "/"
				if self.__test_string(config.ignore_not_path, sub_path) == True:
					root.folders[sub_path] = self.__stat(root.path + sub_path)
					for file in files:
						file = sub_path + file
						root.files[file] = (self.__stat(root.path + file), self.__moddate(root.path + file))
					continue
			
				for file in files:
					if self.__test_string(config.ignore_not_file, file) == True:
						file = sub_path + file
						root.files[file] = (self.__stat(root.path + file), self.__moddate(root.path + file))
						continue
					if self.__test_string(config.ignore_file, file) == True:
						continue
					file = sub_path + file
					root.files[file] = (self.__stat(root.path + file), self.__moddate(root.path + file))
					
				if self.__test_string(config.ignore_path, sub_path) == True:
					continue
				
				root.folders[sub_path] = self.__stat(root.path + sub_path)
				
	def find_changes(self, config):
		self.__load_data()
		self.__find_files(config)
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
				action = input("0: ignore, 1: " + self.roots[0].path + sub_path + " is master, 2: " + self.roots[1].path + sub_path + " is master ")
				try: action = int(action)
				except: action = -1
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
				self.folders = [(folder, stat) for (folder, stat) in self.folders if folder != sub_path] + [(sub_path, self.__stat(src_root + sub_path))]
				
		for x in self.copy:
			(sub_path, src_root, dst_root, file_folder) = x
			if file_folder == 'file':
				print('Copy: ' + src_root + sub_path + ' to ' + dst_root + sub_path)
				shutil.copy(src_root + sub_path, dst_root + sub_path)
				shutil.copystat(src_root + sub_path, dst_root + sub_path)
				self.files = [(file, stat_mod) for (file, stat_mod) in self.files if file != sub_path] + [(sub_path, (self.__stat(src_root + sub_path), self.__moddate(src_root + sub_path)))]
		
		self.remove = list(self.remove)
		self.remove.sort(reverse=True)
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'file']:
			(dst_root, sub_path) = x
			print('Remove file: ' + dst_root + sub_path)
			os.remove(dst_root + sub_path)
			self.files = [(file, stat_mod) for (file, stat_mod) in self.files if file != sub_path]
			
		for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in self.remove if x == 'folder']:
			(dst_root, sub_path) = x
			print('Remove folder: ' + dst_root + sub_path)
			os.rmdir(dst_root + sub_path)
			self.folders = [(folder, stat) for (folder, stat) in self.folders if folder != sub_path]
			
		self.__save_data()
		
class config():
	def __init__(self):
		self.__keys = ['root']
		self.__parse_keys = ['ignore not file', 'ignore file', 'ignore not path', 'ignore path']
		self.__config = dict()
		
		for key in (self.__keys + self.__parse_keys): 
			self.__config[key] = []
	
	def __parse_exp(self, value):
		pre = 0
		post = 0
		if value[:1] == "*":
			pre = 1
			value = value[1:]
		if value[-1:] == "*":
			post = 1
			value = value[:-1]
		return (pre, post, value.split("*"))
	
	def parse(self, path):
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
				if not key in (self.__keys + self.__parse_keys):
					print("Error: '" + key + "' is not a valid key")
					return 1
				if key in self.__parse_keys:
					value = self.__parse_exp(value)
				# save value to key
				config = self.__config[key]
				config.append(value)
				
		except FileNotFoundError:
			print("Config file '" + path + "' could not found") # TODO: create a real error message
			return 1
		# Check 2 roots exist
		if len(self.__config['root']) != 2:
			print(self.__config['root'])
			print("The config file has not 2 root keys")
			return 1
		return 0
	
	@property
	def roots(self):
		return self.__config['root']
	
	@property
	def ignore_file(self): 
		return self.__config['ignore file']
	
	@property
	def ignore_not_file(self):
		return self.__config['ignore not file']
	
	@property
	def ignore_path(self):
		return self.__config['ignore path']
	
	@property
	def ignore_not_path(self):
		return self.__config['ignore not path']

config = config()
if config.parse('config') != 0:
	print("Error: Config file has error")
	exit()

sync = sync(config.roots)
sync.find_changes(config)

sync.do_action()
