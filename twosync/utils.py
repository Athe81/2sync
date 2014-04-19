import hashlib
import logging
import twosync

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

def test_string(parsed_filters, string):
	"""
	Test a string with the given, parsed filters
	
	Returns True if the string match or False if not
	"""
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
		if fsdata_1.get_data(conflict) == None and fsdata_2.get_data(conflict) == None:
			pdata.remove(conflict)
			remove.add(conflict)
		elif fsdata_1.get_data(conflict) == fsdata_2.get_data(conflict):
			if type(fsdata_1.get_data(conflict)) == twosync.data._filetype:
				if get_hash(fsdata_1.path + conflict) == get_hash(fsdata_2.path + conflict):
					pdata.add_file(conflict, fsdata_1.get_data(conflict).stat, fsdata_1.get_data(conflict).moddate, fsdata_1.get_data(conflict).size)
					remove.add(conflict)
			if type(fsdata_1.get_data(conflict)) == twosync.data._foldertype:
				pdata.add_folder(conflict, fsdata_1.get_data(conflict).stat)
				remove.add(conflict)

	conflicts -= remove
	changes -= remove

	return changes, conflicts