#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os.path
sys.path.insert(0, os.path.dirname(__file__))

import json
import time
import requests

import trialserver
import trial
from jsondocument import jsondocument


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
			del prms['recruiting']
		
		# create URL
		for key, val in prms.items():
			par.append("{}={}".format(key, val.replace(' ', '+')))
		
		path = "{}?size={}&{}".format(path, self.batch_size, '&'.join(par))
		return path, None
	
	def search_process_response(self, response):
		ret = response.json()
		trials = []
		meta = {
			'total': ret.get('total_count') or 0,
		}
		results = ret.get('results') or []
		for result in results:
			id_info = result.get('id_info') or {}
			trial = LillyTrial(id_info.get('nct_id'), result)
			trial.retrieve_profile(self)
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
	
	def __init__(self, nct=None, json=None):
		super().__init__(nct, json)
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
	def __init__(self, cache_dir='target-profile-cache'):
		self.cache_dir = cache_dir
	
	def cache_filename(self, trial):
		if trial.nct is None or self.cache_dir is None:
			return None
		if not os.path.exists(self.cache_dir):
			try:
				os.mkdir(self.cache_dir)
			except Exception as e:
				pass
		return os.path.join(self.cache_dir, trial.nct + '-profile.json')
	
	def retrieve(self, trial):
		ppth = self.cache_filename(trial)
		if ppth is None or not os.path.exists(ppth):
			return None
		
		# remove if older than a day
		mtime = os.path.getmtime(ppth)
		if time.time() - mtime > 86400:
			os.remove(ppth)
			return None
		
		with open(ppth, 'r', encoding='UTF-8') as handle:
			return json.load(handle)
	
	def store(self, trial, js):
		ppth = self.cache_filename(trial)
		if ppth is not None:
			with open(ppth, 'w', encoding='UTF-8') as handle:
				handle.write(js)
	
