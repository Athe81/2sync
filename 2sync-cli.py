import os
import shutil
import logging
import argparse
from twosync import config, data, utils

def analyse_action(sub_path, src_root, dst_root):
	def file_folder(path_data):
		if type(path_data) == data._filetype:
			return "file"
		elif type(path_data) == data._foldertype:
			return "folder"
		else:
			utils.log_and_raise("Corrupt data: '" + path_data + "'")

	def mark_for_copy(sub_path, src_root, dst_root, file_folder):
		copy.append((sub_path, src_root, dst_root, file_folder))
		
	def mark_for_remove(sub_path, dst_root, file_folder):
		remove.append((sub_path, dst_root, file_folder))

	if os.path.exists(src_root.path + sub_path):
		mark_for_copy(sub_path, src_root.path, dst_root.path, file_folder(src_root.get_data(sub_path)))
	else:
		mark_for_remove(sub_path, dst_root.path, file_folder(pdata.get_data(sub_path)))

def do_action(copy, remove):
	"""
	Execute the syncronisation
	"""
	copy = list(copy)
	copy.sort()
	for x in copy:
		(sub_path, src_root, dst_root, file_folder) = x
		if file_folder == 'folder':
			if not os.path.exists(dst_root + sub_path):
				print("Create dir: " + dst_root + sub_path)
				os.mkdir(dst_root + sub_path)
			print('Update ' + dst_root + sub_path + ' with data from ' + src_root + sub_path)
			shutil.copystat(src_root + sub_path, dst_root + sub_path)
			# Update folders
			if root0.path == src_root:
				pdata.add_folder(sub_path, root0.get_data(sub_path).stat)
			else:
				pdata.add_folder(sub_path, root1.get_data(sub_path).stat)
			
	for x in copy:
		(sub_path, src_root, dst_root, file_folder) = x
		if file_folder == 'file':
			print('Copy: ' + src_root + sub_path + ' to ' + dst_root + sub_path)
			shutil.copy(src_root + sub_path, dst_root + sub_path)
			shutil.copystat(src_root + sub_path, dst_root + sub_path)
			# Update files
			if root0.path == src_root:
				pdata.add_file(sub_path, root0.get_data(sub_path).stat, root0.get_data(sub_path).moddate, root0.get_data(sub_path).size)
			else:
				pdata.add_file(sub_path, root1.get_data(sub_path).stat, root1.get_data(sub_path).moddate, root1.get_data(sub_path).size)
	
	remove = list(remove)
	remove.sort(reverse=True)
	for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in remove if x == 'file']:
		(dst_root, sub_path) = x
		print('Remove file: ' + dst_root + sub_path)
		os.remove(dst_root + sub_path)
		# Update files
		pdata.remove(sub_path)
		
	for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in remove if x == 'folder']:
		(dst_root, sub_path) = x
		print('Remove folder: ' + dst_root + sub_path)
		os.rmdir(dst_root + sub_path)
		# Update folders
		pdata.remove(sub_path)

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
	config = config.config(args.config)
	pdata = data.PersistenceData(config.config_changed)
	root0 = data.FSData(config.roots[0], config.config_dict)
	root1 = data.FSData(config.roots[1], config.config_dict)
	copy = []
	remove = []
	action = dict()
	changes, conflicts = utils.find_changes(pdata, root0, root1)
	changes -= conflicts

	# Solve conflicts
	if len(conflicts) != 0:
		print("Please solve conflicts:")
	
	# TODO: Find out, what changed and just update the changes
	for sub_path in conflicts:
		for root in (root0, root1):
			_data = root.get_data(sub_path)
			if _data == None:
				print("File: '" + root.path + sub_path + "' does not exist")
			elif type(_data) == data._filetype:
				print("File: " + root.path + sub_path + ", Stat: " + _data.stat + ", Moddate: " + str(_data.moddate) + ", Size: " + str(_data.size))
			elif type(_data) == data._foldertype:
				print("Folder: " + root.path + sub_path + ", Stat: " + _data.stat)
			else:
				utils.log_and_raise("Corrupt pdata for path: '" + sub_path + "'")
		while True:
			try:
				usr_action = int(input("0: ignore, 1: " + root0.path + sub_path + " is master, 2: " + root1.path + sub_path + " is master "))
			except ValueError:
				usr_action = -1
			
			if usr_action == 0:
				break
			elif usr_action == 1:
				analyse_action(sub_path, root0, root1)
				break
			elif usr_action == 2:
				analyse_action(sub_path, root1, root0)
				break
			
			print("Wrong input. Please insert a correct input")
	
	for change in changes:
		if pdata.get_data(change) != root0.get_data(change):
			print("File: " + change + " update from root0 to root1")
			analyse_action(change, root0, root1)
		elif pdata.get_data(change) != root1.get_data(change):
			print("File: " + change + " update from root1 to root0")
			analyse_action(change, root1, root0)
		else:
			print("Error with file: " + change)

	do_action(copy, remove)

except utils.ExitError:
	pass
except KeyboardInterrupt:
	print()
	logging.critical("Exit programm while KeyboardInterrupt (ctrl + c)")
except Exception as e:
	logging.critical("Unknown error", e)
	
logging.info("Exit program")