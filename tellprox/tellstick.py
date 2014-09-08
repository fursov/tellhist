from bottle import *
from tellcore.constants import *
from msensor import *
from tasensor import *
import bottle_helpers as bh
import tellcore.telldus as td
import MySQLdb
import MySQLdb.cursors

def map_response(cmdresp, id = '', method = ''):
	if (cmdresp == TELLSTICK_SUCCESS):
		resp = { "status" : "success" }
		if not id == '':
			resp['id'] = id
		return resp
	elif isinstance(cmdresp, int):
		id = str(id)
		if (cmdresp == TELLSTICK_ERROR_DEVICE_NOT_FOUND):
			msg = "Device " + "\"" + id + "\" not found!"
		elif (cmdresp == TELLSTICK_ERROR_BROKEN_PIPE):
			msg = "Broken pipe"
		elif (cmdresp == TELLSTICK_ERROR_COMMUNICATING_SERVICE):
			msg = "Communicating service"
		elif (cmdresp == TELLSTICK_ERROR_COMMUNICATION):
			msg = "Communication"
		elif (cmdresp == TELLSTICK_ERROR_CONNECTING_SERVICE):
			msg = "Cannot connect to service"
		elif (cmdresp == TELLSTICK_ERROR_METHOD_NOT_SUPPORTED):
			msg = "Device \"" + id + "\" does not support method \"" + str(method) + "\""
		elif (cmdresp == TELLSTICK_ERROR_NOT_FOUND):
			msg = "Not found"
		elif (cmdresp == TELLSTICK_ERROR_PERMISSION_DENIED):
			msg = "Permission denied"
		elif (cmdresp == TELLSTICK_ERROR_SYNTAX):
			msg = "Syntax error"
		else: msg = "Unknown response"
	else: msg = str(cmdresp)
	return { "error" : msg }

def dec_response(f):
	def call_f(*args):
		resp = f(*args)
		if type(resp) is list:
			return map_response(*resp)
		return map_response(resp)
	return call_f

class TellstickAPI(object):
	""" Mimick Telldus Live """
	config = None
	core = td.TelldusCore()
	sensors = {}
	jobs = {}

	def __init__(self, api, config, version):
		self.config = config
		self.version = version
		
		self.load_devices()
		self.load_sensors()
		self.jobs['1'] = {
			"id":"335108",
			"deviceId":"2",
			"method":"16",
			"methodValue":"217",
			"nextRunTime":0,
			"type":"time",
			"hour":"6",
			"minute":"25",
			"offset":0,
			"randomInterval":0,
			"retries":3,
			"retryInterval":5,
			"reps":1,
			"active":"0",
			"weekdays":"1,2,3,4,5"
		}
		
		id = { 'name': 'id', 'type': 'int', 'description': 'The id of the device' }
		
		api.add_route('devices', {
			'list': {
				'fn'    : self.devices_list,
				'inputs': { 'name': 'supportedMethods', 'type': 'int', 'description': '' }
			}
		})
		api.add_route('device', {
			'add': {
				'fn': self.device_add,
				'inputs': [
					{ 'name': 'clientId', 'type': 'int',    'description': 'The id of the client' },
					{ 'name': 'name',     'type': 'string', 'description': '' },
					{ 'name': 'protocol', 'type': 'string', 'description': '' },
					{ 'name': 'model',    'type': 'string', 'description': '' }
				]
			},
			'info': {
				'fn': self.device_info,
				'inputs': [id, { 'name': 'supportedMethods', 'type': 'int', 'description': '' }]
			},
			'setparameter': {
				'fn': self.device_set_parameter,
				'inputs': [id,
					{ 'name': 'parameter', 'type': 'string', 'description': '' },
					{ 'name': 'value',     'type': 'string', 'description': '' }
				]
			},
			'setname': {
				'fn': self.device_set_attr,
				'description': 'Renames a device',
				'inputs': [id, { 'name': 'name', 'type': 'string', 'description': '' }]
			},
			'setmodel': {
				'fn': self.device_set_attr,
				'description': 'Set device model',
				'inputs': [id, { 'name': 'model', 'type': 'string', 'description': '' }]
			},
			'setprotocol': {
				'fn': self.device_set_attr,
				'description': 'Set device protocol',
				'inputs': [id, { 'name': 'protocol', 'type': 'string', 'description': '' }]
			},
			'command': {
				'fn': self.device_command,
				'inputs': [
					id,
					{ 'name': 'value',  'type': 'int', 'description': '' },
					{ 'name': 'method', 'type': 'int', 'description': '' }
				]
			},
			'remove': {
				'fn': self.device_remove, 'inputs': id
			},
			'dim': {
				'fn': self.device_command,
				'inputs': [ id,{ 'name': 'level', 'type': 'int', 'description': '' } ]
			},
			'bell': {
				'fn': self.device_command, 'inputs': id
			},
			'down': {
				'fn': self.device_command, 'inputs': id
			},
			'learn': {
				'fn': self.device_command, 'inputs': id
			},
			'stop': {
				'fn': self.device_command, 'inputs': id
			},
			'turnon': {
				'fn': self.device_command, 'inputs': id
			},
			'turnoff': {
				'fn': self.device_command, 'inputs': id
			},
			'up': {
				'fn': self.device_command, 'inputs': id
			},
			'toggle': {
				'fn': self.device_command, 'inputs': id
			},
			'execute': {
				'fn': self.device_command, 'inputs': id
			}
		})
		
		api.add_route('clients', {
			'list': {
				'fn'    : self.clients_list,
				'inputs': { 'name': 'extras', 'type': 'string', 'description': 'Returns a list of all clients associated with the current user' }
			}
		})
		
		api.add_route('client', {
			'info': {
				'fn'    : self.client_info,
				'inputs': { 'name' : 'id', 'type': 'int', 'description': 'The id of the client' }
			}
		})
		
		api.add_route('sensors', {
			'list': {
				'fn'    : self.sensors_list,
				'inputs': { 'name': 'includeignored', 'type': 'int', 'description': 'Set to 1 to include ignored sensors' }
			}
		})
		
		api.add_route('sensor', {
			'info': {
				'fn'    : self.sensor_info,
				'inputs': { 'name': 'id', 'type': 'int', 'description': '' }
			},
                        'history': {
                                'fn'    : self.sensor_history,
                                'inputs': { 'name': 'id', 'type': 'int', 'description': '' }
                        },
			'setignore': {
				'fn'    : self.sensor_setignore,
				'inputs': [
					{ 'name': 'id',     'type': 'int', 'description': '' },
					{ 'name': 'ignore', 'type': 'int', 'description': '' }
				]
			},
			'setname': {
				'fn'    : self.sensor_setname,
				'inputs': [
					{ 'name': 'id',   'type': 'int',    'description': '' },
					{ 'name': 'name', 'type': 'string', 'description': '' }
				]
			}
		})
		
		api.add_route('group', {
			'remove': {
				'fn': self.device_remove, 'inputs': id
			}
		})

	def devices_list(self, func, supportedMethods):
		"""Returns a list of all clients associated with the current user."""
		# TODO is this necessary?
		self.load_devices()
		return {
			'device': [
				self.device_to_dict(device, supportedMethods, False)
					for device in self.devices.values()
			]
		}

	@dec_response
	def device_add(self, func, clientid, name, protocol, model):
		"""Adds a device"""
		if (self.config['editable'] is False):     return "Client is not editable"
		if (clientid != self.config['client_id']): return "Client \"" + str(clientid) + "\" not found!"
		try:
			resp = self.core.add_device(name, protocol, model)
			if type(resp) is td.Device:
				return [TELLSTICK_SUCCESS, resp.id]
		except Exception as e:
			return e

	def device_info(self, func, id, supportedMethods):
		"""Information about a device"""
		device = self.get_device(id)
		if not device: return map_response(TELLSTICK_ERROR_DEVICE_NOT_FOUND, id)
		return self.device_to_dict(device, supportedMethods, True)

	@dec_response
	def device_set_parameter(self, func, id, parameter, value):
		"""Set device parameter"""
		device = self.get_device(id)
		if not device: return [TELLSTICK_ERROR_DEVICE_NOT_FOUND, id]
		
		try:
			device.set_parameter(parameter, value)
		except Exception as e:
			return e
		return TELLSTICK_SUCCESS
	
	@dec_response
	def device_set_attr(self, func, id, value):
		device = self.get_device(id)
		if not device: return [TELLSTICK_ERROR_DEVICE_NOT_FOUND, id]

		attr = func[3:].lower()
		if device.__setattr__(attr, value):
			return TELLSTICK_SUCCESS
		return TELLSTICK_ERROR_NOT_FOUND
	
	def get_device(self, id):
		self.load_devices()
		if (self.devices.has_key(id)):
			return self.devices[id]
		return None

	@dec_response
	def device_remove(self, func, id):
		device = self.get_device(id)
		if not device: return [TELLSTICK_ERROR_DEVICE_NOT_FOUND, id]

		try:
			device.remove()
		except Exception as e:
			return e

		return TELLSTICK_SUCCESS
	
	@dec_response
	def device_command(self, func, id, value = 0, method = 0):
		device = self.get_device(id)
		if not device: return [TELLSTICK_ERROR_DEVICE_NOT_FOUND, id]
		
		lastCommand = device.last_sent_command(TELLSTICK_TURNON + TELLSTICK_TURNOFF)

		try:
			for i in range(self.config['retries']):
				result = self.run_command(device, func, value, method, lastCommand)
				if not result:
					return result
		except Exception as e:
			return e

		return TELLSTICK_SUCCESS
	
	def run_command(self, device, func, value, method, lastCommand):
		if   (method == TELLSTICK_BELL		or func == 'bell')    : device.bell()
		elif (method == TELLSTICK_DIM		or func == 'dim')     : device.dim(value)
		elif (method == TELLSTICK_DOWN		or func == 'down')    : device.down()
		elif (method == TELLSTICK_LEARN		or func == 'learn')   : device.learn()
		elif (method == TELLSTICK_STOP		or func == 'stop')    : device.stop()
		elif (method == TELLSTICK_TURNON	or func == 'turnon')  : device.turn_on()
		elif (method == TELLSTICK_TURNOFF	or func == 'turnoff') : device.turn_off()
		elif (method == TELLSTICK_UP		or func == 'up')      : device.up()
		elif (method == TELLSTICK_TOGGLE	or func == 'toggle')  :
			# TODO or last command was a dim with value > 0?
			if lastCommand == TELLSTICK_TURNON:
				device.turn_off()
			else:
				device.turn_on()
		elif (method == TELLSTICK_EXECUTE	or func == 'execute') : device.execute()
		else: return "Device " + str(id) + " does not support method " + str(method)
		return True

	def clients_list(self, func, extras):
		return { 'client': [self.get_client_info()] }

	def client_info(self, func, id):		
		if (id != self.config['client_id']):
			return { "error" : "Client \"" + str(id) + "\" not found!" }
		return self.get_client_info()

	def sensors_list(self, func, includeIgnored):		
		self.load_sensors()
		includeIgnored = True if includeIgnored == 1 else False
		return { 'sensor': [
			self.sensor_to_dict(sensor, False)
				for id, sensor in self.sensors.iteritems()
				if includeIgnored or int(sensor.ignore) == 0
		]}
	
	def get_sensor(self, id):
		self.load_sensors()
		# The ID should be an integer, but we store them in the dictionary as
		# strings, so treat as such
		id = str(id)
		if (self.sensors.has_key(id)):
			return self.sensors[id]
		return None
	
	def sensor_info(self, func, id):
		sensor = self.get_sensor(id)
		if not sensor: return map_response("Sensor " + "\"" + str(id) + "\" not found!")
		return self.sensor_to_dict(sensor, True)
	
        def sensor_history(self, func, id):
                #sensor = self.get_sensor(id)
                #if not sensor: return map_response("Sensor " + "\"" + str(id) + "\" not found!")
                #return self.sensor_to_dict(sensor, True)
		db = MySQLdb.connect(db = 'ha', user = 'ha', passwd = 'ha', cursorclass = MySQLdb.cursors.DictCursor)
		cursor = db.cursor()
		query = "SELECT `temperature`, `humidity`, `timestamp` FROM `sensordata` WHERE `sensor_id`='" + str(id) + "' ORDER BY `timestamp` ASC"
		numOfEntries = cursor.execute(query)
		allEntries = cursor.fetchall()
		outDict = {}
		outDict['id'] = id
		outDict['data'] = allEntries
		return outDict
			

	@dec_response
	def sensor_setignore(self, func, id, ignore):
		sensor = self.get_sensor(id)
		if not sensor: return "Sensor " + "\"" + str(id) + "\" not found!"
		sensor.ignore = 1 if ignore == 1 else 0
		return TELLSTICK_SUCCESS
	
	@dec_response
	def sensor_setname(self, func, id, name):
		sensor = self.get_sensor(id)
		if not sensor: return "Sensor " + "\"" + str(id) + "\" not found!"
		sensor.name = name
		return TELLSTICK_SUCCESS
	
	def load_devices(self):
		""" Read in all devices using tellcore-py library and convert into
			id keyed dictionary """
		self.devices = { device.id: device for device in self.core.devices() }
	
	def load_sensors(self):
		""" Read in all sensors using tellcore-py library and convert into
			id keyed dictionary """
		
		sensors = self.core.sensors()
		if (self.config['debug']):
			sensors.append(MSensor('prot1', 'model1', 9998, TELLSTICK_TEMPERATURE))
			sensors.append(MSensor('prot2', 'model2', 9999, TELLSTICK_TEMPERATURE + TELLSTICK_HUMIDITY))
		
		self.sensors = {
			str(rawsensor.id) : TASensor(self.config, rawsensor)
				for rawsensor in sensors
		}

	def editable(self):
		return 1 if self.config['editable'] else 0
	
	def client(self):
		return self.config['client_id'] or 1
	
	def clientName(self):
		return self.config['client_name'] or ''

	def device_type_to_string(self, type):
		if (type == TELLSTICK_TYPE_DEVICE):
			return 'device'
		elif (type == TELLSTICK_TYPE_GROUP):
			return 'group'
		else:
			return 'scene'

	""" Converts a device into a dictionary ready for outputting to json/xml
		info is used to indicate whether it is used to output for info as per spec
	"""
	def device_to_dict(self, device, methods_supported, info):
		methods_supported = methods_supported or 0
		
		# We support toggle ourselves, so add it to the supported list
		deviceMethods = device.methods(methods_supported)
		if methods_supported & TELLSTICK_TOGGLE == TELLSTICK_TOGGLE:
			deviceMethods |= TELLSTICK_TOGGLE
		
		dict = {
			'id'        : device.id,
			'name'      : device.name,
			'state'     : device.last_sent_command(methods_supported),
			'statevalue': device.last_sent_value(),
			'methods'   : deviceMethods,
			'type'      : self.device_type_to_string(device.type),
			'online'    : 1,
			'editable'  : self.editable()
		}

		if info:
			dict['protocol'] = device.protocol
			dict['model']    = device.model
			dict['parameter'] = device.parameters()
		else:
			dict['client'] = self.client()
			dict['clientName'] = self.clientName()
			dict = bh.set_attribute(dict)
			
		return dict
	


	def sensor_to_dict(self, sensor, info):
		# Set default value in case we get back nothing
		lastUpdated = -1
		
		# Populate sensor data using calls to core library
		sensor_data = []
		for type in [
			{'name': 'temp',     'key': TELLSTICK_TEMPERATURE },
			{'name': 'humidity', 'key': TELLSTICK_HUMIDITY }
		]:
			if sensor.raw.datatypes & type['key'] != 0:
				svalue = sensor.raw.value(type['key'])
				lastUpdated = svalue.timestamp
				sensor_data.append({'name': type['name'], 'value': svalue.value})
		
		base_dict = {
			'id'         : sensor.raw.id,
			'name'       : sensor.name,
			'lastUpdated': lastUpdated,
			'ignored'    : int(sensor.ignore),
			'online'     : 1,
			'editable'   : self.editable(),
			'client'     : self.client()
		}
		
		if info:
			extra_dict = {
				'data'          : sensor_data,
				'protocol'      : sensor.raw.protocol,
				'sensorId'      : sensor.raw.id,
				'timezoneoffset': 7200
			}
			base_dict = dict(base_dict.items() + extra_dict.items())
		else:
			base_dict['clientName'] = self.clientName()
		return base_dict

	def get_client_info(self):
		return {
			'id'      : self.config['client_id'] or 1,
			'uuid'    : '00000000-0000-0000-0000-000000000000',
			'name'    : self.config['client_name'] or '',
			'online'  : '1',
			'editable': 1 if self.config['editable'] else 0,
			'version' : self.version,
			'type'    : 'TellProx'
		}
