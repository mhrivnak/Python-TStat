#!/usr/bin/env python

#Copyright (c) 2011, Paul Jennings <pjennings-tstat@pjennings.net>
#All rights reserved.

#Redistribution and use in source and binary forms, with or without 
#modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice, 
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * The names of its contributors may not be used to endorse or promote
#      products derived from this software without specific prior written
#      permission.

#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
#IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
#CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
#SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS 
#INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
#CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
#ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF 
#THE POSSIBILITY OF SUCH DAMAGE.

# TStat.py
# Python interface for Radio Thermostat wifi-enabled thermostats.

# Usage:
# t = TStat('1.2.3.4')         # Where 1.2.3.4 is your thermostat's IP address
# t.getCurrentTemp()           # Returns current temperature as a float
# t.setHeatPoint(68.0)         # Sets target temperature for heating to 68.0
# ...
#
#
# A simple cache based on retrieved URL and time of retrieval is included.
# If you call TStat.getFanMode(), /tstat will be retrieved and the value 
# for fmode will be return.  If you then call t.getTState(), a cached 
# value will already exist and tstate will be returned from that.  
#
# You can change the time for cache expiration by calling 
# t.setCacheExpiry(timeInSeconds).  

import datetime
import httplib
import json
import logging

from API import *

class CacheEntry:
	def __init__(self, location, data):
		self.location = location
		self.data = data
		self.time = datetime.datetime.now()

	def age(self):
		return datetime.datetime.now()-self.time

class TStat:
	def __init__(self, address, cacheExpiry=5, api=None, logger=None):
		self.address = address
		self.setCacheExpiry(cacheExpiry)
		self.cache = {}
		if logger is None:
			logging.basicConfig(level=logging.DEBUG)
			self.logger = logging.getLogger('TStat')
		else:
			self.logger = logger
		if api is None:
			self.api = API()
			self.api = getAPI(self.getModel())
		else:
			self.api = api

	def setCacheExpiry(self, newExpiry):
		self.cacheExpiry = datetime.timedelta(seconds=newExpiry)

	def _getConn(self):
		"""Used internally to get a connection to the tstat."""
		return httplib.HTTPConnection(self.address)

	def _post(self, location, params):
		"""Used internally to modify tstat settings (e.g. cloud mode)."""
		params = urllib.urlencode(params)
		headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
		conn = self._getConn()
		conn.request("POST", location, params, headers)
		return conn.getresponse()

	def _get(self, key, raw=False):
		"""Used internally to retrieve data from the tstat and process it with JSON if necessary."""

		l = self.logger
		l.debug("Requested: %s" % key)

		# Check for valid request
		if not self.api.has_key(key):
			#TODO: Error processing
			l.debug("%s does not exist in API" % key)
			return

		# Retrieve the mapping from api key to thermostat URL
		entry = self.api[key]
		l.debug("Got API entry: %s" % entry)

		# First check cache
		newest = None
		for getter in entry.getters:
			location = getter[0]
			jsonKey = getter[1]
			if self.cache.has_key(location):
				cacheEntry = self.cache[location]
				l.debug("Found cache entry: %s" % cacheEntry)
				if cacheEntry.age() < self.cacheExpiry:
					l.debug("Entry is valid")
					try:
						if cacheEntry.age() < self.cache[newest[0]].age():
							l.debug("Entry is now newest entry")
							newest = getter
					except TypeError:
						l.debug("Entry is first valid entry")
						newest = getter
				else:
					l.debug("Entry is invalid (expired)")

		response = None
		if newest is not None:
			# At least one valid entry was found in the cache
			l.debug("Using cached entry")
			response = self.cache[newest[0]].data[newest[1]]
		else:
			# Either data was not cached or cache was expired
			getter = entry.getters[0]
			# TODO: Change back to access actual tstat
			conn = self._getConn()
			conn.request("GET", getter[0])
			#TODO: Error checking
			response = json.loads(conn.getresponse().read())
			l.debug("Got response: %s" % response)
			self.cache[getter[0]] = CacheEntry(getter[0], response)

		# Allow mappings to subdictionaries in json data
		# e.g. 'today/heat_runtime' from '/tstat/datalog'
		for key in getter[1].split("/"):
			response = response[key]

		#response = response[getter[1]]

		if raw or entry.valueMap is None:
			# User requested raw data or there is no value mapping
			return response

		# User requested processing
		l.debug("Mapping response")
		try:
			l.debug("%s --> %s" % (response, entry.valueMap[response]))
			return entry.valueMap[response]
		except:
			l.debug("Didn't find '%s' in %s" % (response, entry.valueMap))
		return response

	def getCurrentTemp(self, raw=False):
		"""Returns current temperature measurement."""
		return self._get('temp', raw)

	def getTstatMode(self, raw=False):
		"""Returns current thermostat mode."""
		return self._get('tmode', raw)

	def getFanMode(self, raw=False):
		"""Returns current fan mode."""
		return self._get('fmode', raw)

	def getOverride(self, raw=False):
		"""Returns current override setting?"""
		return self._get('override', raw)

	def getHoldState(self, raw=False):
		"""Returns current hold state."""
		return self._get('hold', raw)

	def getHeatPoint(self, raw=False):
		"""Returns current set point for heat."""
		return self._get('t_heat', raw)

	def getCoolPoint(self, raw=False):
		"""Returns current set point for cooling."""
		return self._get('t_cool', raw)

	def getSetPoints(self, raw=False):
		"""Returns both heating and cooling set points."""
		return (self.getHeatPoint(), self.getCoolPoint())

	def getModel(self, raw=False):
		"""Returns the model of the thermostat."""
		return self._get('model', raw)

	def getTState(self, raw=False):
		"""Returns current thermostat state."""
		return self._get('tstate', raw)

	def getFanState(self, raw=False):
		"""Returns current fan state."""
		return self._get('fstate', raw)

	def getTime(self, raw=False):
		"""Returns current time."""
		# TODO: time processing
		pass

	def getHeatUsageToday(self, raw=False):
		"""Returns heat usage for today."""
		return self._get('today_heat_runtime')

	def getHeatUsageYesterday(self, raw=False):
		"""Returns heat usage for yesterday."""
		return self._get('yesterday_heat_runtime')

	def getCoolUsageToday(self, raw=False):
		"""Returns cool usage for today."""
		return self._get('today_cool_runtime')

	def getCoolUsageYesterday(self, raw=False):
		"""Returns cool usage for yesterday."""
		return self._get('yesterday_cool_runtime')

	def isOK(self):
		"""Returns true if thermostat reports that it is OK."""
		pass

	def getErrStatus(self):
		"""Returns current error code or 0 if everything is OK."""
		pass

	def getEventLog(self):
		"""Returns events?"""
		pass

	def setCloudMode(self, state=True):
		"""Sets cloud mode to state."""
		command = "on"
		if not state:
			command = "off"
		return self._post("/cloud/mode", {'command': command})
