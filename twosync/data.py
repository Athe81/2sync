from twosync.utils import test_string, log_and_raise
from collections import namedtuple
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
		filename = "saved_data"
		try:
			with open(filename, 'rb') as f:
				self._data = pickle.load(f)
		except FileNotFoundError:
			logging.warn("Could not load data from file: '" + filename + "'. File not found")
		except PermissionError as e:
			log_and_raise("Could not load data from file: '" + filename + "'. No Permission", e)
		except EOFError as e:
			log_and_raise("Could not load data from file: '" + filename + "'. File is corrupt", e)
	
	def _save_data(self):
		"""
		Save the informations about synchronised files and folders
		"""
		filename = "saved_data"
		try:
			with open(filename, 'wb') as f: 
				pickle.dump(self._data, f)
		except Exception as e:
			log_and_raise("Could not save data to: '" + filename + "'", e)
	
	def add_file(self, file, stat, moddate, size):
		super().add_file(file, stat, moddate, size)
		self._save_data()
		
	def add_folder(self, file, stat):
		super().add_folder(file, stat)
		self._save_data()
		
	def remove(self, path):
		super().remove(path)
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
		
	@property
	def path(self):
		return self._path