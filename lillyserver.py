#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests

import trialserver
import trial
import jsondocument


class LillyV2Server(trialserver.TrialServer):
	""" Trial server as provided by LillyCOI's v2 API on
	https://developer.lillycoi.com/.
	"""
	
	def __init__(self, key_secret):
		if key_secret is None:
			raise Exception("You must provide the base64-encoded {key}:{secret} combination")
		
		super().__init__("https://data.lillycoi.com/")
		self.batch_size = 50
		self.headers = {
			'Authorization': 'Basic {}'.format(key_secret)
		}
		self.trial_headers = self.search_headers = {'Accept': 'application/json'}
	
	
	def search_prepare_parts(self, path, params):
		if params is None:
			raise Exception("Must provide search parameters")
		
		par = []
		prms = params.copy()
		
		# process special search parameters
		if prms.get('countries') is not None:
			i = 1
			for ctry in prms['countries']:
				par.append("country{}={}".format(i, ctry.replace(' ', '+')))
				i += 1
			del prms['countries']
		
		if prms.get('recruiting', False):
			par.insert(0, "overall_status=Open+Studies")
			# par.insert(0, "overall_status=Open+Studies&no_unk=true")	# valid, but currently throws a 400
			del prms['recruiting']
		
		# create URL
		for key, val in prms.items():
			par.append("{}={}".format(key, val.replace(' ', '+')))
		
		path = "{}?size={}&{}".format(path, self.batch_size, '&'.join(par))
		return path, None
	
	def search_process_response(self, response, trial_class=None):
		trial_class = trial_class if trial_class is not None else LillyTrial
		
		ret = response.json()
		trials = []
		meta = {
			'total': ret.get('total_count') or 0,
		}
		results = ret.get('results') or []
		for result in results:
			id_info = result.get('id_info') or {}
			trial = trial_class(id_info.get('nct_id'), result)
			trials.append(trial)
		
		more = None
		more_link = ret.get('_links', {}).get('next', {}).get('href')
		if more_link is not None:
			more = self.base_request('GET', None, more_link)
		
		return trials, meta, more


class LillyTrial(trial.Trial):
	""" Extend the CTG base trial by what Lilly's API is providing.
	
	Provides a cache for downloaded and codified target profiles.
	"""
	
	def __init__(self, nct=None, json_dict=None):
		super().__init__(nct, json_dict)
		self.score = json_dict.get('_meta', {}).get('score') if json_dict is not None else None
		self.profile = None
		self.check_cache()
	
	
	# MARK: Target Profiles
	
	def check_cache(self):
		if self.profile is None:
			self.profile = LillyTargetProfile.retrieve(self)
	
	def retrieve_profile(self, server):
		if self.profile is not None:
			return
		
		if self._links is not None:
			profiles = self._links.get('target-profile')
			if profiles is not None and len(profiles) > 0:
				href = profiles[0].get('href')
				
				# got one, download
				if href is not None:
					try:
						self.profile = LillyTargetProfile.load_from(href, server)
					except Exception as e:
						pass


class LillyTargetProfile(jsondocument.JSONDocument):
	""" Represent a target profile.
	"""
	def __init__(self, trial, json):
		super().__init__('tp-{}'.format(trial.nct), 'target-profile', json)
		self.trial = trial
	
	@classmethod
	def load_from(cls, href, server):
		res = server.get(href)
		res.raise_for_status()
		js = res.json()
		
		LillyTargetProfileCache().store(trial, js)
		
		return cls(self, js)
	
	@classmethod
	def retrieve(cls, trial):
		js = LillyTargetProfileCache().retrieve(trial)
		return cls(trial, js)


class LillyTargetProfileCache(object):
	""" Handles caching target profiles.
	"""
	def __init__(self, directory):
		if not os.path.exists(directory):
			raise Exception('Cache directory "{}" does not exist, please create it'.format(directory))
		
		self.cache_dir = directory
		self.can_write = False
		self.timeout = None				# number, in seconds
		
	def cache_filename(self, trial):
		if trial.nct is None or self.cache_dir is None:
			return None
		return os.path.join(self.cache_dir, trial.nct + '.json')
	
	def retrieve(self, trial):
		ppth = self.cache_filename(trial)
		if ppth is None or not os.path.exists(ppth):
			return None
		
		# remove if older than timeout
		if self.timeout is not None:
			mtime = os.path.getmtime(ppth)
			if time.time() - mtime > self.timeout:
				os.remove(ppth)
				return None
		
		with open(ppth, 'r', encoding='UTF-8') as handle:
			return json.load(handle)
	
	def store(self, trial, js):
		if not self.can_write:
			return
		
		ppth = self.cache_filename(trial)
		if ppth is not None:
			with open(ppth, 'w', encoding='UTF-8') as handle:
				handle.write(js)
	
