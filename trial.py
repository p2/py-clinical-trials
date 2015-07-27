#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#	Representing a ClinicalTrials.gov trial
#
#	2012-12-13	Created by Pascal Pfiffner
#	2014-07-29	Migrated to Python 3 and JSONDocument
#

import datetime
import logging
import re
import markdown

if __package__:
	from .jsondocument import jsondocument
else:
	from jsondocument import jsondocument
from geo import km_distance_between


class Trial(jsondocument.JSONDocument):
	""" Describes a trial found on ClinicalTrials.gov.
	"""
	
	def __init__(self, nct=None, json_dict=None):
		super().__init__(nct, 'trial', json_dict)
		self.process_title()
		self.process_interventions()
		self.process_phases()
		self.process_locations()
		self.parse_eligibility()
	
	def as_json(self):
		js_dict = super().as_json()
		if 'locations' in js_dict:
			del js_dict['locations']
		
		return js_dict
	
	
	# MARK: Properties
	
	@property
	def nct(self):
		return self.id
	
	def process_title(self):
		""" Construct the best title possible.
		"""
		if not self.title:
			title = self.brief_title
			if not title:
				title = self.official_title
			acronym = self.acronym
			if acronym:
				if title:
					title = "%s: %s" % (acronym, title)
				else:
					title = acronym
			self.title = title
	
	@property
	def entered(self):
		""" How many years ago was the trial entered into ClinicalTrials.gov.
		"""
		now = datetime.datetime.now()
		first = self.date('firstreceived_date')
		return round((now - first[1]).days / 365.25 * 10) / 10 if first[1] else None
	
	@property
	def last_updated(self):
		""" How many years ago was the trial last updated.
		"""
		now = datetime.datetime.now()
		last = self.date('lastchanged_date')
		return round((now - last[1]).days / 365.25 * 10) / 10 if last[1] else None
	
	def process_interventions(self):
		""" Assigns a set of intervention types to the `interventions` property
		"""
		if self.interventions is None:
			types = set()
			if self.intervention is not None:
				for intervent in self.intervention:
					inter_type = intervent.get('intervention_type')
					if inter_type:
						types.add(inter_type)
			
			if 0 == len(types):
				types.add('Observational')
			
			self.interventions = list(types)
	
	def process_phases(self):
		""" Assigns a set of phases in drug trials to the `phases` property.
		Non-drug trials might still declare trial phases, we don't filter those.
		"""
		if self.phases is None:
			my_phases = self.phase
			if my_phases and 'N/A' != my_phases:
				phases = set(my_phases.split('/'))
			else:
				phases = set(['N/A'])
			self.phases = list(phases)
	
	def process_locations(self):
		if self.locations is None and self.location is not None:
			locs = []
			for loc in self.location:		# note the missing "s"
				locs.append(TrialLocation(self, loc))
			self.locations = locs
	
	def parse_eligibility(self):
		""" Takes CTG's plain text criteria, does some preprocessing and pipes
		it through Markdown. Preprocessing is needed because of leading
		whitespace.
		Assigns the result to the receiver's `parsed_eligibility` property.
		"""
		if self.parsed_eligibility is None:
			elig = self.eligibility
			if elig is not None and 'criteria' in elig:
				txt = elig['criteria'].get('textblock')
				if txt:
					txt = re.sub(r'^ +', r' ', txt, flags=re.MULTILINE)
					txt = txt.replace('>', '&gt;')
					txt = txt.replace('<', '&lt;')
					txt = markdown.markdown(txt)
					txt = re.sub(r'(</?li>)\s*</?p>', r'\1', txt)	# unwrap <li><p></p></li>
					elig['html'] = txt
				del elig['criteria']
			self.parsed_eligibility = elig
	
	
	# MARK: Utilities
	
	def date(self, dt):
		""" Returns a tuple of the string date and the parsed Date object for
		the requested JSON object. """
		dateval = None
		parsed = None
		
		if dt is not None:
			date_dict = getattr(self, dt)
			if date_dict is not None and type(date_dict) is dict:
				dateval = date_dict.get('value')
				
				# got it, parse
				if dateval:
					dateregex = re.compile('(\w+)\s+((\d+),\s+)?(\d+)')
					searched = dateregex.search(dateval)
					match = searched.groups() if searched is not None else []
					
					# convert it to ISO-8601. If day is missing use 28 to not crash the parser for February
					dt = "%s-%s-%s" % (match[3], str(match[0])[0:3], str('00' + match[2])[-2:] if match[2] else 28)
					parsed = datetime.datetime.strptime(dt, "%Y-%m-%d")
		
		return (dateval, parsed)
	
	
	# MARK: API
	
	def for_api(self):
		""" The JSON to return for a JSON API call.
		"""
		js = {}
		api = self.as_json()
		
		for key in [
				'_id', 'title',
				'brief_summary', 'keyword',
				'source',
				'interventions', 'phases',
				'condition', 'primary_outcome', 'secondary_outcome',
				'arm_group',
			]:
			val = api.get(key)
			if val:
				js[key] = val
		
		if self.parsed_eligibility:
			js['eligibility'] = self.parsed_eligibility
		if self.locations is not None:
			js['locations'] = [l.for_api() for l in self.locations]
		
		return js
	
	
	# MARK: Trial Locations
	
	def locations_closest_to(self, lat, lng, limit=0, open_only=True):
		""" Returns a list of tuples, containing the trial location and their
		distance to the provided latitude and longitude.
		If limit is > 0 then only the closest x locations are being returned.
		If open_only is True, only (not yet) recruiting locations are
		considered.
		"""
		closest = []
		
		# get all distances (must be instantiated, are not being cached)
		if self.location is not None:
			for loc_json in self.location:
				loc = TrialLocation(self, loc_json)
				
				if not open_only or loc.is_open:
					closest.append((loc, loc.km_distance_from(lat, lng)))
		
		# sort and truncate
		closest.sort(key=lambda tup: tup[1])
		
		if limit > 0 and len(closest) > limit:
			closest = closest[0:limit]
		
		return closest
	
	
	# MARK: Keywords
	
	def cleanup_keywords(self, keywords):
		""" Cleanup keywords. """
		better = []
		re_split = re.compile(r';\s+')		# would be nice to also split on comma, but some ppl use it
											# intentionally in tags (like "arthritis, rheumatoid")
		re_sub = re.compile(r'[,\.]+\s*$')
		for keyword in keywords:
			for kw in re_split.split(keyword):
				if kw and len(kw) > 0:
					kw = re_sub.sub('', kw)
					better.append(kw)
		
		return better


class TrialLocation(object):
	""" An object representing a trial location.
	"""
	
	def __init__(self, trial, json_loc=None):
		self.trial = trial
		self.status_color = 'red'
		self.geo = None
		
		if json_loc is not None:
			self.status = json_loc.get('status')
			if self.status:
				if re.search(r'not\s+[\w\s]*\s+recruiting', self.status, flags=re.IGNORECASE):
					self.status_color = 'orange'
				elif re.search(r'recruiting', self.status, flags=re.IGNORECASE):
					self.status_color = 'green'
			self.contact = json_loc.get('contact')
			self.contact_backup = json_loc.get('contact_backup')
			self.facility = json_loc.get('facility')
			self.pi = json_loc.get('investigator')
	
	
	# MARK: Properties
	
	@property
	def best_contact(self):
		""" Tries to find the best contact data for this location, starting
		with "contact", then "contact_backup", then the trial's
		"overall_contact". """
		loc_contact = self.contact
		
		if loc_contact is None \
			or (loc_contact.get('email') is None and loc_contact.get('phone') is None):
			loc_contact = self.contact_backup
		
		if loc_contact is None \
			or (loc_contact.get('email') is None and loc_contact.get('phone') is None):
			loc_contact = self.trial.overall_contact
		
		if loc_contact is None \
			or (loc_contact.get('email') is None and loc_contact.get('phone') is None):
			loc_contact = self.trial.overall_contact_backup
		
		return trial_contact_parts(loc_contact)
	
	@property
	def is_open(self):
		""" Checks the receiver's status and determines whether this location is
		(or will be) recruiting patients.
		
		:returns: A bool indicating whether this location is or will be recruiting
		"""
		return 'Recruiting' == self.status \
			or 'Not yet recruiting' == self.status \
			or 'Enrolling by invitation' == self.status
	
	
	# MARK: Location
	
	def km_distance_from(self, lat, lng):
		""" Calculates the distance in kilometers between the location and the
		given lat/long pair using the Haversine formula. """
		if self.geo is None:
			return None
		
		lat2 = self.geo.get('latitude') if self.geo else 0
		lng2 = self.geo.get('longitude') if self.geo else 0
		
		return km_distance_between(lat, lng, lat2, lng2)
	
	
	# MARK: Serialization
	
	def for_api(self):
		return {
			'status': self.status,
			'status_color': self.status_color,
			'facility': self.facility,
			'investigator': self.pi,
			'contact': self.best_contact,
			'geodata': self.geo,
		}


def trial_contact_parts(contact):
	""" Returns a dict with 'name', 'email' and 'phone', composed from the
	given contact dictionary. """
	if not contact:
		return {'name': 'No contact'}
	
	# name and degree
	nameparts = []
	if 'first_name' in contact and contact['first_name']:
		nameparts.append(contact['first_name'])
	if 'middle_name' in contact and contact['middle_name']:
		nameparts.append(contact['middle_name'])
	if 'last_name' in contact and contact['last_name']:
		nameparts.append(contact['last_name'])
	name = ' '.join(nameparts) if len(nameparts) > 0 else 'Unknown contact'
	
	if 'degrees' in contact and contact['degrees']:
		name = '%s, %s' % (name, contact['degrees'])
	
	parts = {'name': name}
	
	# email
	if 'email' in contact and contact['email']:
		parts['email'] = contact['email']
	
	# phone
	if 'phone' in contact and contact['phone']:
		fon = contact['phone']
		if 'phone_ext' in contact and contact['phone_ext']:
			fon = '%s (%s)' % (fon, contact['phone_ext'])
		
		parts['phone'] = fon
	
	return parts
	
