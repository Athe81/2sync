import os
import shutil
import logging
import argparse
from twosync import config, data, utils

def analyse_action(sub_path, src_root, dst_root, file_folder):
	def mark_for_copy(sub_path, src_root, dst_root, file_folder):
		copy.append((sub_path, src_root, dst_root, file_folder))
		
	def mark_for_remove(sub_path, dst_root, file_folder):
		remove.append((sub_path, dst_root, file_folder))
		
	if os.path.exists(src_root + sub_path):
		mark_for_copy(sub_path, src_root, dst_root, file_folder)
	else:
		mark_for_remove(sub_path, dst_root, file_folder)

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
				pdata.add_folder(sub_path, root0.get_folder(sub_path).stat)
			else:
				pdata.add_folder(sub_path, root1.get_folder(sub_path).stat)
			
	for x in copy:
		(sub_path, src_root, dst_root, file_folder) = x
		if file_folder == 'file':
			print('Copy: ' + src_root + sub_path + ' to ' + dst_root + sub_path)
			shutil.copy(src_root + sub_path, dst_root + sub_path)
			shutil.copystat(src_root + sub_path, dst_root + sub_path)
			# Update files
			if root0.path == src_root:
				pdata.add_file(sub_path, root0.get_file(sub_path).stat, root0.get_file(sub_path).moddate, root0.get_file(sub_path).size)
			else:
				pdata.add_file(sub_path, root1.get_file(sub_path).stat, root1.get_file(sub_path).moddate, root1.get_file(sub_path).size)
	
	remove = list(remove)
	remove.sort(reverse=True)
	for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in remove if x == 'file']:
		(dst_root, sub_path) = x
		print('Remove file: ' + dst_root + sub_path)
		os.remove(dst_root + sub_path)
		# Update files
		pdata.remove_file(sub_path)
		
	for x in [(dst_root, sub_path) for (sub_path, dst_root, x) in remove if x == 'folder']:
		(dst_root, sub_path) = x
		print('Remove folder: ' + dst_root + sub_path)
		os.rmdir(dst_root + sub_path)
		# Update folders
		pdata.remove_folder(sub_path)

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
	file_conflicts = set()
	folder_conflicts = set()
	copy = []
	remove = []
	changed_files, changed_folders, file_conflicts, folder_conflicts = utils.find_changes(pdata, root0, root1)

	# Solve conflicts
	if len(file_conflicts) != 0 or len(folder_conflicts) != 0:
		print("Please solve conflicts:")
	
	# TODO: Find out, what changed and just update the changes
	_file_conflicts = set()
	for sub_path in file_conflicts:
		for root in (root0, root1):
			if sub_path in root.files.keys():
				print("File: " + root.path + sub_path + ", Stat: " + root.files[sub_path].stat + ", Moddate: " + str(root.files[sub_path].moddate) + ", Size: " + str(root.files[sub_path].size))
			else:
				print("File: " + root.path + sub_path + " deleted")
		while True:
			try:
				action = int(input("0: ignore, 1: " + root0.path + sub_path + " is master, 2: " + root1.path + sub_path + " is master "))
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
		for root in (root0, root1):
			if sub_path in root.folders.keys():
				print("Folder: " + root.path + sub_path + ", Stat: " + root.folders[sub_path].stat)
			else:
				print("Folder: " + root.path + sub_path + " deleted")
		while True:
			try:
				action = int(input("0: ignore, 1: " + root0.path + sub_path + " is master, 2: " + root1.path + sub_path + " is master "))
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
	
	for (f, r) in changed_files:
		if r == 0:
			analyse_action(f, root0.path, root1.path, 'file')
		else:
			analyse_action(f, root1.path, root0.path, 'file')
		
	for (f, r) in changed_folders:
		if r == 0:
			analyse_action(f, root0.path, root1.path, 'folder')
		else:
			analyse_action(f, root1.path, root0.path, 'folder')

	do_action(copy, remove)

except ExitError:
	pass
except KeyboardInterrupt:
	print()
	logging.critical("Exit programm while KeyboardInterrupt (ctrl + c)")
except Exception as e:
	logging.critical("Unknown error", e)
	
logging.info("Exit program")