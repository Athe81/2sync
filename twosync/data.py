from twosync.utils import test_string, log_and_raise
from collections import namedtuple
import hashlib
import os
import pickle
import logging

_filetype 	= namedtuple('_filetype', 'stat, moddate, size')
_foldertype = namedtuple('_foldertype', 'stat')



class BasicData(object):
	def __init__(self):
		self._data = dict()

	def add_file(self, file, stat, moddate, size):
		logging.info("Add file '" + file + "' for sync")
		self._data[file] = _filetype(stat, moddate, size)
		
	def add_folder(self, folder, stat):
		logging.info("Add folder '" + folder + "' for sync")
		self._data[folder] = _foldertype(stat)

	def get_data(self, path):
		try:
			return self._data[path]
		except KeyError:
			return None

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
			logging.info("Update PersistenceData with new config")
			for path in self.data.keys():
				if type(path) == _filetype:
					print("File")
					if test_string(config['ignore file'], file[1:]) == True:
						self.remove_file(file)
				elif type(path) == _foldertype:
					print("Folder")
					if test_string(config['ignore path'], folder[1:]) == True:
						self.remove_folder(folder)
				else:
					print("Corrupt data")
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
			log_and_raise("Could not load data from file: '" + self._path_data + "'. No Permission", e)
		except EOFError as e:
			log_and_raise("Could not load data from file: '" + self._path_data + "'. File is corrupt", e)
	
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		try:
			with open(self._path_data, 'wb') as f: 
				pickle.dump(self._data, f)
		except Exception as e:
			log_and_raise("Could not save data to: '" + self._path_data + "'", e)
	
	def add_file(self, file, stat, moddate, size):
		super().add_file(file, stat, moddate, size)
		self._save_data()
		
	def add_folder(self, file, stat):
		super().add_folder(file, stat)
		self._save_data()
		
	def remove(self, path):
		super().remove(path)
		self._save_data()

	def analyse_data(self, fsdata_1, fsdata_2):
		"""
		# Find the changed files and folders. Return 2 sets:
		# 	set 1: changed files including conflicts
		# 	set 2: conflicts
		"""
		changes_data1 = set([f for (f, *_) in (self.data.items() ^ fsdata_1.data.items())])
		changes_data2 = set([f for (f, *_) in (self.data.items() ^ fsdata_2.data.items())])
		conflicts = changes_data1 & changes_data2

		# Remove conflicts on self, if fsdata's has no conflict
		remove = set()
		for conflict in conflicts:
			if fsdata_1.get_data(conflict) == None and fsdata_2.get_data(conflict) == None:
				self.remove(conflict)
				remove.add(conflict)
			elif fsdata_1.get_data(conflict) == fsdata_2.get_data(conflict):
				if type(fsdata_1.get_data(conflict)) == twosync.data._filetype:
					if get_hash(fsdata_1.path + conflict) == get_hash(fsdata_2.path + conflict):
						self.add_file(conflict, fsdata_1.get_data(conflict).stat, fsdata_1.get_data(conflict).moddate, fsdata_1.get_data(conflict).size)
						remove.add(conflict)
				if type(fsdata_1.get_data(conflict)) == twosync.data._foldertype:
					self.add_folder(conflict, fsdata_1.get_data(conflict).stat)
					remove.add(conflict)

		conflicts -= remove
		changes = changes_data1 | changes_data2

		return changes, conflicts

	def get_change_details(self, data_1, data_2):
		pass

class FSData(BasicData):
	def __init__(self, path, config_dict):
		logging.info("Init FSData with path: '" + path + "'")
		super().__init__()
		self._path = path
		if path[0:6] == 'ssh://':
			log_and_raise("Error: ssh is not suported")
		else:
			self._find_files(config_dict)

	def _find_files(self, config_dict):
		"""
		Read files/folders from root's
		
		If file/folder match the filters it will be saved with last modfication date and permissions
		"""

		len_root_path = len(self._path)
		for path, _, files in os.walk(self._path, followlinks=False):
			sub_path = path[len_root_path:]

			# Add files and folders if 'ignore not path' match to folder
			if test_string(config_dict['ignore not path'], sub_path) == True:
				self.add_folder(sub_path)

				for file in files:
					self.add_file(sub_path  + "/" + file)
				return
			
			if test_string(config_dict['ignore path'], sub_path) == True:
				return
			
			# Add while 'ignore path' doesn't match
			self.add_folder(sub_path)
			
			for file in files:
				# Add file if 'ignore not file' match the filename
				if test_string(config_dict['ignore not file'], file) == True:
					self.add_file(sub_path  + "/" + file)
					continue
				
				# Ignore file if the 'ignore file' match the filename
				if test_string(config_dict['ignore file'], file) == True:
					continue
				
				# Add file if 'ignore not file' and 'ignore file' not matched
				self.add_file(sub_path  + "/" + file)

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

	def add(self, path):
		# path = self._path + "/" + path
		if os.path.isfile(path):
			self.add_file(path)
		elif os.path.isdir(path):
			self.add_folder(path)
		
	@property
	def path(self):
		return self._path