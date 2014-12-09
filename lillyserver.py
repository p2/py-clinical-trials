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
		self.trial_endpoint = 'GET /trial/nct/{id}'
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
		self.target_profile = None
	
	
	# MARK: Target Profiles
	
	def retrieve_profile(self, server):
		if self.target_profile is not None:
			return
		
		if self._links is not None:
			profiles = self._links.get('target-profile')
			if profiles is not None and len(profiles) > 0:
				href = profiles[0].get('href')
				
				# got one, download
				if href is not None:
					try:
						self.target_profile = LillyTargetProfile.load_from(href, server)
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
		
		return cls(self, res.json())
	
