import twosync
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

def get_str_hash(content):
	"""
	Returns the SHA1 hash of content
	"""
	_config_hash = hashlib.sha1()
	_config_hash.update(content.encode())
	return _config_hash.hexdigest()

def find_changes(pdata, fsdata_1, fsdata_2):
	"""
	Find the changed files and folders. Return 2 sets:
		set 1: changed files including conflicts
		set 2: conflicts
	"""
	changes_data1 = set([f for (f, *_) in (pdata.data.items() ^ fsdata_1.data.items())])
	changes_data2 = set([f for (f, *_) in (pdata.data.items() ^ fsdata_2.data.items())])
	conflicts = changes_data1 & changes_data2
	changes = changes_data1 | changes_data2

	# Remove conflicts on pdata, if fsdata's has no conflict
	remove = set()
	for conflict in conflicts:
		if isinstance(fsdata_1[conflict], twosync.data.DataNoneType) and isinstance(fsdata_2[conflict], twosync.data.DataNoneType):
			pdata.remove(conflict)
			remove.add(conflict)
		elif fsdata_1[conflict] == fsdata_2[conflict]:
			if isinstance(fsdata_1[conflict], twosync.data.DataFileType):
				if fsdata_1.get_hash(conflict) == fsdata_2.get_hash(conflict):
					pdata.add_file(conflict, fsdata_1[conflict].mode, fsdata_1[conflict].mtime, fsdata_1[conflict].size)
					remove.add(conflict)
			if isinstance(fsdata_1[conflict], twosync.data.DataFolderType):
				pdata.add_folder(conflict, fsdata_1[conflict].mode)
				remove.add(conflict)

	conflicts -= remove
	changes -= remove

	return changes, conflicts