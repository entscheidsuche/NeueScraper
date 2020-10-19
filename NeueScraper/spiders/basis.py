# -*- coding: utf-8 -*-
import scrapy
import logging
from io import StringIO
import csv
import json
import inspect
import os
import json

logger = logging.getLogger(__name__)

class BasisSpider(scrapy.Spider):
	name = 'Gerichtsdaten'
	kantone_de = {'CH':'Eidgenossenschaft','AG':'Aargau','AI':'Appenzell Innerrhoden','AR':'Appenzell Ausserrhoden','BE':'Bern','BL':'Basel-Land','BS':'Basel-Stadt','FR':'Freiburg','GE':'Genf','GL':'Glarus','GR':'Graubünden','JU':'Jura','LU':'Luzern','NE':'Neuenburg','NW':'Nidwalden','OW':'Obwalden','SG':'St.Gallen','SH':'Schaffhausen','SO':'Solothurn','SZ':'Schwyz','TG':'Thurgau','TI':'Tessin','UR':'Uri','VD':'Waadtland','VS':'Wallis','ZG':'Zug','ZH':'Zürich'}
	kantone_fr = {'CH':'Conféderation','AG':'Argovie','AI':'Appenzell Rhodes-Intérieures','AR':'Appenzell Rhodes-Extérieures','BE':'Berne','BL':'Bâle-Campagne','BS':'Bâle-Ville','FR':'Fribourg','GE':'Genève','GL':'Glaris','GR':'Grisons','JU':'Jura','LU':'Lucerne','NE':'Neuchâtel','NW':'Nidwald','OW':'Obwald','SG':'Saint-Gall','SH':'Schaffhouse','SO':'Soleure','SZ':'Schwytz','TG':'Thurgovie','TI':'Tessin','UR':'Uri','VD':'Vaud','VS':'Valais','ZG':'Zoug','ZH':'Zurich'}
	kantone_it = {'CH':'Confederazione','AG':'Argovia','AI':'Appenzello Interno','AR':'Appenzello Interno','BE':'Berna','BL':'Basilea Campagna','BS':'Basilea Città','FR':'Friburgo','GE':'Ginevra','GL':'Glarona','GR':'Grigioni','JU':'Giura','LU':'Lucerna','NE':'Neuchâtel','NW':'Nidvaldo','OW':'Obvaldo','SG':'San Gallo','SH':'Sciaffusa','SO':'Soletta','SZ':'Svitto','TG':'Turgovia','TI':'Ticino','UR':'Uri','VD':'Vaud','VS':'Vallese','ZG':'Zugo','ZH':'Zurigo'}
	gerichte = {}
	kanton= {}
	CSV_URL='https://docs.google.com/spreadsheets/d/e/2PACX-1vR2sZY8Op7cLChL6Hu0aDZmbOrmX_UPtyxz86W-oeyuCemBs0poqxC-EU33i-JhH9PQ7SMqYOnIw5ou/pub?gid=1220663602&single=true&output=csv'
	kammerfallback=None;

	def __init__(self):
		super().__init__()

	def basis_request(self):
		""" Generates scrapy frist request
		"""
		return [scrapy.Request(url=self.CSV_URL, callback=self.parse_gerichtsliste, errback=self.errback_httpbin)]

	def start_requests(self):
		# lese erst einmal die Spiderdaten und danach werden die Spider in der request_gen geladen.
		yield scrapy.Request(url=self.CSV_URL, callback=self.parse_gerichtsliste, errback=self.errback_httpbin)

	def parse_gerichtsliste(self, response):
		logger.info("parse_gerichtsliste response.status "+str(response.status))
		logger.info("parse_gerichtsliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_gerichtsliste Rohergebnis: "+response.body_as_unicode())
		virtualFile = StringIO(response.body_as_unicode())
		reader = csv.DictReader(virtualFile)
		for row in reader:
			logger.info('Zeile: '+json.dumps(row))
			if 'Spider' in row:
				spider=row['Spider']
				if spider is not None and spider:
					logger.info('gerichtsliste für spider '+spider+' eingelesen.')
					if spider in self.gerichte:
						self.gerichte[spider].append(row)
					else:
						self.gerichte[spider]=[row]
		if self.name in self.gerichte:
			if 'Signatur' in self.gerichte[self.name][0]:
				signatur=self.gerichte[self.name][0]['Signatur']
				self.kanton_kurz=signatur[:2]
				if self.kanton_kurz in self.kantone_de:
					self.kanton['de']=self.kantone_de[self.kanton_kurz]
					self.kanton['fr']=self.kantone_fr[self.kanton_kurz]
					self.kanton['it']=self.kantone_it[self.kanton_kurz]
				else:
					logger.error('Unbekannter Kantonskürzel in Signatur: '+signatur)
			else:
				logger.error('Unvollständige Konfigurationszeile: '+json.dumps(self.gerichte[self.name][0]))
		else:
			logger.error('Aktueller Spider '+self.name+' nicht in Konfigurationsexcel-Sheet gefunden.')
		self.ebenen=1
		if len(self.gerichte[self.name])==1: #Es gibt nur einen Konfigurationseintrag für diesen Spider
			self.mehrfachspider=False
			logger.info("Einfacher Fall: Eindeutiger Eintrag")
		else:
			self.mehrfachspider=True
			logger.info("Es wird kompliziert: Mehrdeutig")
		# Ist die zweite Stufe fix oder variabel?
		if not self.mehrfachspider or (
			'Stufe 2 DE' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 DE']==i['Stufe 2 DE'] for i in self.gerichte[self.name]) and
			'Stufe 2 FR' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 FR']==i['Stufe 2 FR'] for i in self.gerichte[self.name]) and
			'Stufe 2 IT' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 IT']==i['Stufe 2 IT'] for i in self.gerichte[self.name])):
			self.zweite_ebene_fix=True
			logger.info("aber 2. Ebene ist fix")
			
			if 'Stufe 2 IT' in self.gerichte[self.name][0]:
				self.stufe2_it=self.gerichte[self.name][0]['Stufe 2 IT']
				self.stufe2=self.stufe2_it
			if 'Stufe 2 FR' in self.gerichte[self.name][0]:
				self.stufe2_fr=self.gerichte[self.name][0]['Stufe 2 FR']
				self.stufe2=self.stufe2_fr
			if 'Stufe 2 DE' in self.gerichte[self.name][0]:
				self.stufe2_de=self.gerichte[self.name][0]['Stufe 2 DE']
				self.stufe2=self.stufe2_de
			if self.stufe2:
				self.ebenen=2
			if not self.mehrfachspider:
				if 'Stufe 3 IT' in self.gerichte[self.name][0]:
					self.stufe3_it=self.gerichte[self.name][0]['Stufe 3 IT']
					self.stufe3=self.stufe3_it
					self.ebenen=3
				if 'Stufe 3 FR' in self.gerichte[self.name][0]:
					self.stufe3_fr=self.gerichte[self.name][0]['Stufe 3 FR']
					self.stufe3=self.stufe3_fr
					self.ebenen=3
				if 'Stufe 3 DE' in self.gerichte[self.name][0]:
					self.stufe3_de=self.gerichte[self.name][0]['Stufe 3 DE']
					self.stufe3=self.stufe3_de
					self.ebenen=3
		else: #Zweite Ebene ist variabel
			self.zweite_ebene_fix=False
			logger.info("Mehrfachspider, dessen 2. Ebene variabel ist")
			for g in self.gerichte[self.name]:
				if 'Stufe 3 DE' in g or 'Stufe 3 FR' in g or 'Stufe 3 IT' in g:
					self.ebenen=3
		# Wenn nur die 3. Ebene variabel ist, Standarderkennung vorbereiten (nur mit Strings)
		if self.mehrfachspider and self.zweite_ebene_fix:
			self.ebenen=3 #wenn mehrere Einträge und die 2. Ebene identisch ist, muss es eine 3. Ebene geben, die zu Unterschieden führt
			self.kammerwahl = {}
			for i in range(len(self.gerichte[self.name])):
				if self.gerichte[self.name][i]['Signatur'][-4:]=="_999":
					self.kammerfallback=i
				elif 'Matching' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Matching']!="":
					matching=self.gerichte[self.name][i]['Matching'].split("|")
					for m in matching:
						if m in self.kammerwahl:
							logger.error("Doppeltes Matching! Matchkey '"+m+"' bereits für "+str(self.kammerwahl[m])+"["+self.gerichte[self-name][self.kammerwahl[m]]['Signatur']+"] belegt und nun nochmal für "+str(i)+"["+self.gerichte[self-name][i]['Signatur']+"]!")
						else:
							self.kammerwahl[m]=i
				else:
					if 'Stufe 3 IT' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 3 IT']!='':
						self.kammerwahl[self.gerichte[self.name][i]['Stufe 3 IT']]=i
					if 'Stufe 3 FR' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 3 FR']!='':
						self.kammerwahl[self.gerichte[self.name][i]['Stufe 3 FR']]=i
					if 'Stufe 3 DE' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 3 DE']!='':
						self.kammerwahl[self.gerichte[self.name][i]['Stufe 3 DE']]=i
			logger.info("kammerwahl ist "+json.dumps(self.kammerwahl))
		
		if self.kammerfallback is None and self.mehrfachspider: #Wenn kein Default spider angegeben, baue selbst einen aus dem Eintrag 0
			#kein Kammerfallback gesetzt aber Mehrfachspider. Generiere daher Kammerfallback
			row=self.gerichte[self.name][0]
			row['Signatur']=row['Signatur'].rpartition("_")[0]+"_999"
			row['Matching']=''
			row['Stufe 3 DE']='Sonstige Kammer'
			row['Stufe 3 FR']='Autre chambre'
			row['Stufe 3 IT']='Altro camera'
			if(not self.zweite_ebene_fix):
				row['Stufe 2 DE']='Sonstiges Gericht'
				row['Stufe 2 FR']='Autre tribunal'
				row['Stufe 2 IT']='Altro tribunale'
			self.kammerfallback=len(self.gerichte[self.name])
			logger.info("Generiertes Kammerfallback "+str(self.kammerfallback)+": "+json.dumps(row))
			self.gerichte[self.name].append(row)
		
		self.scrapy_job=os.environ['SCRAPY_JOB']
		logger.info("SCRAPY_JOB: "+self.scrapy_job)
		logger.info("Gerichtsliste verarbeitet")
		for request in self.request_gen:
			yield request
		logger.info("Übrige Requests abgesendet")
	
		


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
