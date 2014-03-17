import hashlib
import logging

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