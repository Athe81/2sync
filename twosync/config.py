import logging
import os.path
from twosync.utils import get_hash, get_str_hash, log_and_raise
from collections import namedtuple

_filter = namedtuple('_filter', 'full, preglob, postglob, values')

class Config(object):
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
		
		self._keys 			= ['root']
		self._parse_keys 	= ['ignore not file', 'ignore file', 'ignore not path', 'ignore path']
		self._config 		= dict()
		self._configname 	= configname
		self._path_config 	= os.path.expanduser("~/.twosync/" + self._configname)
		self._path_hash 	= os.path.expanduser("~/.twosync/.hash_" + self._configname)
		self._path_data 	= os.path.expanduser("~/.twosync/.data_" + self._configname)

		for key in (self._keys + self._parse_keys):
			self._config[key] = []
		
		self._config_changed()
		self._parse()
		
	def _config_changed(self):
		"""
		Writes True or False to 'self._config_changed' depending if the config has changed

		The comparison are done over a sha1 checksum, which saved on the HD
		"""

		logging.info("Check if config-file has changed")

		self._hexdigest = get_hash(self._path_config)
		
		saved_hash = ''
		try:
			with open(self._path_hash, 'r') as f:
				saved_hash = f.read()
				saved_hash[:-1]
		except FileNotFoundError:
			logging.info("No hash key for config-file: '" + self._path_config + "'")
		
		if self._hexdigest == saved_hash:
			logging.info("config-file has not changed")
			self._config_changed = False
		else:
			logging.info("config-file has changed")
			self._config_changed = True
	
	def _save_config_hash(self):
		with open(self._path_hash, 'w') as f:
			f.write(self._hexdigest)
	
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
		return _filter(value, pre, post, value.split("*"))
	
	def _parse(self):
		"""
		Parse the config-file an test if the config-file match the specifications
		"""
		
		logging.info("Parse config-file: '" + self._path_config + "'")

		# Open config file and parse content.
		for line in open(self._path_config, 'r'):
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
				log_and_raise("Invalid key: '" + key + "' in config-file: '" + self._path_config + "'")
			if key in self._parse_keys:
				value = self._parse_exp(value)
			# save value to key
			config = self._config[key]
			config.append(value)
			
		# Check if 2 roots exist
		if len(self._config['root']) != 2:
			log_and_raise("Config-file: '" + self._path_config + "' need 2 root keys", e)

		# Check if not both roots are ssh
		if self._config['root'][0].startswith('ssh://') and self._config['root'][1].startswith('ssh://'):
			log_and_raise("Only one root can be an ssh path", e)

		# root path need a final /
		# if not self._config['root'][0].endswith('/'):
		# 	self._config['root'][0] += '/'
		# if not self._config['root'][1].endswith('/'):
		# 	self._config['root'][1] += '/'

		# root path need a final /
		if self._config['root'][0].endswith('/'):
			self._config['root'][0] = self._config['root'][0][:-1]
		if self._config['root'][1].endswith('/'):
			self._config['root'][1] = self._config['root'][1][:-1]

	def _test(self, parsed_filters, sub_path):
		for filters in parsed_filters:
			logging.info("Test '" + sub_path + "' with filter: '" + filters.full + "'")
			stat = 1
			str_pos = 0
			sum_filters = len(filters.values)
			for pos in range(sum_filters):
				# zero *, sub_path = filter
				if sum_filters == 1 and filters.preglob == 0 and filters.postglob == 0 and sub_path == filters.values[0]:
					logging.debug("'" + sub_path + "' matched filter: '" + str(filters.full) + "'")
					return True
				# no pre *, first pos, filter != sub_path
				if filters.preglob == 0 and pos == 0 and filters.values[pos] != sub_path[:len(filters.values[pos])]:
					stat = 0
					break
				# no post *, last pos, filter != sub_path
				if filters.postglob == 0 and pos == sum_filters-1 and filters.values[pos] != sub_path[len(filters.values[pos])*-1:]:
					stat = 0
					break
				# one filter, no pre or post *
				if sum_filters == 1 and (filters.preglob == 0 or filters.postglob == 0):
					logging.debug("'" + sub_path + "' matched filter: '" + str(filters.full) + "'")
					return True
				str_pos2 = sub_path[str_pos:].find(filters.values[pos])
				if str_pos2 == -1:
					stat = 0
					break
				str_pos += len(filters.values[pos])
			if stat == 1:
				logging.debug("'" + sub_path + "' matched filter: '" + str(filters.full) + "'")
				return True
			logging.debug("'" + sub_path + "' doesn't matched filter: '" + str(filters.full) + "'")
		return False

	def test_file(self, sub_path):
		"""
		Test if a file should be synced or not

		Returns True if the file should synced.
		Returns False if the file should ignored.

		sub_path = relative path to file from root path
		"""
		if self._test(self.config_dict['ignore not file'], sub_path):
			return True
		if self._test(self.config_dict['ignore file'], sub_path):
			return False
		return True

	def test_dir(self, sub_path):
		"""
		Test if a directory should be synced or not

		Returns True if the directory should synced.
		Returns False if the directory should ignored.

		sub_path = relative path to directory from root path
		"""
		if self._test(self.config_dict['ignore not path'], sub_path):
			return True
		if self._test(self.config_dict['ignore path'], sub_path):
			return False
		return True

	@property
	def config_dict(self):
		"""
		Returns the dictionary with the parsed config
		"""
		return self._config
	
	@property
	def roots(self):
		"""
		Returns a list with the roots 
		"""
		return self._config['root']
	
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