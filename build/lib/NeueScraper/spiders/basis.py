# -*- coding: utf-8 -*-
import scrapy
import logging
from io import StringIO
import csv
import json
import inspect
import os
import json
import re
from lxml import etree

from NeueScraper.pipelines import MyFilesPipeline
from NeueScraper.pipelines import PipelineHelper

elementchars=re.compile("[^-a-zA-Z0-9_]")
elementre=re.compile("^[a-zA-Z][-a-zA-Z0-9_]+$")

logger = logging.getLogger(__name__)

class BasisSpider(scrapy.Spider):
	name = 'Gerichtsdaten'
	kantone_de = {'CH':'Eidgenossenschaft','AG':'Aargau','AI':'Appenzell Innerrhoden','AR':'Appenzell Ausserrhoden','BE':'Bern','BL':'Basel-Land','BS':'Basel-Stadt','FR':'Freiburg','GE':'Genf','GL':'Glarus','GR':'Graubünden','JU':'Jura','LU':'Luzern','NE':'Neuenburg','NW':'Nidwalden','OW':'Obwalden','SG':'St.Gallen','SH':'Schaffhausen','SO':'Solothurn','SZ':'Schwyz','TG':'Thurgau','TI':'Tessin','UR':'Uri','VD':'Waadtland','VS':'Wallis','ZG':'Zug','ZH':'Zürich'}
	kantone_fr = {'CH':'Conféderation','AG':'Argovie','AI':'Appenzell Rhodes-Intérieures','AR':'Appenzell Rhodes-Extérieures','BE':'Berne','BL':'Bâle-Campagne','BS':'Bâle-Ville','FR':'Fribourg','GE':'Genève','GL':'Glaris','GR':'Grisons','JU':'Jura','LU':'Lucerne','NE':'Neuchâtel','NW':'Nidwald','OW':'Obwald','SG':'Saint-Gall','SH':'Schaffhouse','SO':'Soleure','SZ':'Schwytz','TG':'Thurgovie','TI':'Tessin','UR':'Uri','VD':'Vaud','VS':'Valais','ZG':'Zoug','ZH':'Zurich'}
	kantone_it = {'CH':'Confederazione','AG':'Argovia','AI':'Appenzello Interno','AR':'Appenzello Interno','BE':'Berna','BL':'Basilea Campagna','BS':'Basilea Città','FR':'Friburgo','GE':'Ginevra','GL':'Glarona','GR':'Grigioni','JU':'Giura','LU':'Lucerna','NE':'Neuchâtel','NW':'Nidvaldo','OW':'Obvaldo','SG':'San Gallo','SH':'Sciaffusa','SO':'Soletta','SZ':'Svitto','TG':'Turgovia','TI':'Ticino','UR':'Uri','VD':'Vaud','VS':'Vallese','ZG':'Zugo','ZH':'Zurigo'}
	gerichte = {}
	kanton= {}
	CSV_URL='https://docs.google.com/spreadsheets/d/e/2PACX-1vR2sZY8Op7cLChL6Hu0aDZmbOrmX_UPtyxz86W-oeyuCemBs0poqxC-EU33i-JhH9PQ7SMqYOnIw5ou/pub?gid=1220663602&single=true&output=csv'
	JOBS_HOST='http://entscheidsuche.ch.s3.amazonaws.com/'
	JOBS_URL=JOBS_HOST+'?list-type=2&prefix=scraper%2F'
	kammerfallback=None
	files_written ={}
	previous_run={}
	ab=None

	def __init__(self):
		super().__init__()

	def start_requests(self):
		# lese erst einmal die Spiderdaten und danach werden die Spider in der request_gen geladen.
		yield scrapy.Request(url=self.CSV_URL, callback=self.parse_gerichtsliste, errback=self.errback_httpbin)

	def parse_gerichtsliste(self, response):
		logger.info("parse_gerichtsliste response.status "+str(response.status))
		logger.info("parse_gerichtsliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_gerichtsliste Rohergebnis: "+response.body_as_unicode())

		self.scrapy_job=os.environ['SCRAPY_JOB']
		logger.info("SCRAPY_JOB: "+self.scrapy_job)

		item= { 'Entscheidquellen': response.body_as_unicode() }
		yield(item)

		virtualFile = StringIO(response.body_as_unicode())
		reader = csv.DictReader(virtualFile)
		for row in reader:
			if 'Spider' in row:
				spider=row['Spider']
				if spider is not None and spider:
					logger.info('Zeile mit Eintrag für Spider '+spider+': '+json.dumps(row))
					if spider in self.gerichte:
						self.gerichte[spider].append(row)
					else:
						self.gerichte[spider]=[row]
						
		#XML daraus machen
		root_e=etree.Element('Spiderliste')
		kantone={}
		for spidername in self.gerichte:
			spidereintrag=self.gerichte[spidername]
			kantonskurz=spidereintrag[0]['Signatur'][:2]
			if kantonskurz in self.kantone_de:
				if kantonskurz in kantone:
					kanton_e=kantone[kantonskurz]
				else:
					kanton_e=etree.SubElement(root_e,'Kanton')
					kanton_e.set('Name',self.kantone_de[kantonskurz])
					kanton_e.set('Kurz',kantonskurz.lower())
					kantone[kantonskurz]=kanton_e					
				spider_e=etree.SubElement(kanton_e,'Spider')
				spider_e.set('Name', spidername)
				for signaturreihe in spidereintrag:
					signatur_e=etree.SubElement(spider_e,'Eintrag')
					signatur_e.set('Name', signaturreihe['Signatur'])
					for spalte in signaturreihe:
						wert=signaturreihe[spalte]
						if(wert):
							spaltenname=elementchars.sub('_',spalte)
							if not elementre.match(spaltenname):
								spaltenname='X_'+spaltenname
							spalte_e=etree.SubElement(signatur_e,spaltenname)
							spalte_e.text=wert
		xml_content = '<?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="/Spider.xsl"?>\n'
		xml_content = xml_content+str(etree.tostring(root_e, pretty_print=True),"ascii")
		item= { 'Spiderliste': xml_content }
		yield(item)
		#CSV auf S3 ablegen, da Google eine CORS-Exception gibt
						
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
		if self.name not in self.gerichte:
			logger.error('Spider '+self.name+' nicht im Excel Sheet gefunden.')
		if len(self.gerichte[self.name])==1: #Es gibt nur einen Konfigurationseintrag für diesen Spider
			self.mehrfachspider=False
			logger.debug("Einfacher Fall: Eindeutiger Eintrag")
		else:
			self.mehrfachspider=True
			logger.debug("Es wird kompliziert: Mehrdeutig")
		# Ist die zweite Stufe fix oder variabel?
		if not self.mehrfachspider or (
			'Stufe 2 DE' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 DE']==i['Stufe 2 DE'] for i in self.gerichte[self.name]) and
			'Stufe 2 FR' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 FR']==i['Stufe 2 FR'] for i in self.gerichte[self.name]) and
			'Stufe 2 IT' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 IT']==i['Stufe 2 IT'] for i in self.gerichte[self.name])):
			self.zweite_ebene_fix=True
			logger.debug("aber 2. Ebene ist fix")
			
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
			logger.debug("Mehrfachspider, dessen 2. Ebene variabel ist")
			for g in self.gerichte[self.name]:
				if 'Stufe 3 DE' in g or 'Stufe 3 FR' in g or 'Stufe 3 IT' in g:
					self.ebenen=3
		# Wenn die 2. und/oder 3. Ebene variabel ist, Standarderkennung vorbereiten (nur mit Strings)
		# In Kammerwahl steht dabei Kammer@Gericht wobei Kammer ein Begriff ist, der in der Kammer gefunden werden muss und Gericht im Gerichtsstring
		# In Matching kann dabei sowohl nur die Kammer stehen als auch nur ein Wort des Gerichts (@Gericht)
		if self.mehrfachspider:
			if self.ebenen==3:
				if self.zweite_ebene_fix:
					self.compare="kammer"
				else:
					self.compare="kombiniert"
			else:
				self.compare="gericht"
				
			self.kammerwahl = {}
			for i in range(len(self.gerichte[self.name])):
				if self.gerichte[self.name][i]['Signatur'][-4:]=="_999":
					self.kammerfallback=i
				elif 'Matching' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Matching']!="":
					matching=self.gerichte[self.name][i]['Matching'].split("|")
					for m in matching:
						if m in self.kammerwahl:
							logger.error("Doppeltes Matching! Matchkey '"+m+"' bereits für "+str(self.kammerwahl[m])+"["+self.gerichte[self.name][self.kammerwahl[m]]['Signatur']+"] belegt und nun nochmal für "+str(i)+"["+self.gerichte[self-name][i]['Signatur']+"]!")
						else:
							self.kammerwahl[m]=i
				else:
					for lang in {"DE", "FR", "IT"}:
						gericht="";
						if not self.zweite_ebene_fix: #Falls Gerichtsebene nicht fix, Gericht mit in das Matching einbeziehen
							if 'Stufe 2 '+lang in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 2 '+lang]!='':
								gericht= "@"+self.gerichte[self.name][i]['Stufe 2 '+lang]
						if 'Stufe 2 '+lang in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 3 '+lang]!='':
							self.kammerwahl[self.gerichte[self.name][i]['Stufe 3 '+lang]+gericht]=i	
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
		
		logger.info("Gerichtsliste verarbeitet, hole nun die Jobliste.")
		
		# Nun einlesen, was an Dateien vom letzten Spidern vorhanden ist
		jobs_url=self.JOBS_URL+self.name+"%2FJob_"
		logger.info("Jobs-URL: "+jobs_url)
		yield scrapy.Request(url=jobs_url, callback=self.parse_jobliste, errback=self.errback_httpbin)
		
	def parse_jobliste(self, response):
		logger.info("parse_jobliste response.status "+str(response.status))
		logger.info("parse_jobliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_jobliste Rohergebnis: "+response.body_as_unicode())
		jobs=response.xpath("//*[local-name()='Contents']/*[local-name()='Key']/text()").getall()
		if jobs:
			jobs.sort(reverse=True)
			yield scrapy.Request(url=self.JOBS_HOST+jobs[0], callback=self.parse_dateiliste, errback=self.errback_httpbin)
		else:
			logger.info("Kein vorheriger Job gefunden. Erster Lauf von: "+self.name)
			logger.info("Starte nun "+str(len(self.request_gen))+" Requests.")	
			for req in self.request_gen:
				yield req


	def parse_dateiliste(self, response):
		logger.info("parse_dateiliste response.status "+str(response.status))
		logger.info("parse_dateiliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_dateiliste Rohergebnis: "+response.body_as_unicode())
		self.previous_run=json.loads(response.body_as_unicode())
		# Wird nur eine Teilabfrage gemacht, die Daten der vorherigen Abfrage übernehmen und mit der Quelle kennzeichnen
		previous_job=self.previous_run["job"]
		for pfad in self.previous_run["dateien"]:
			eintrag=self.previous_run["dateien"][pfad]
			checksum=eintrag['checksum']
			status=eintrag["status"]
			quelle=eintrag["quelle"] if "quelle" in eintrag else previous_job
			self.files_written[pfad]={'checksum': checksum, 'status': status, 'quelle': quelle}
		logger.info("Starte nun "+str(len(self.request_gen))+" Requests.")	
		for req in self.request_gen:
			yield req

	def detect(self,vgericht,vkammer,num):
		if self.mehrfachspider:
			kammermatch=-1
			for m in self.kammerwahl:
				i=self.kammerwahl[m]
				tests=m.split("@")
				if self.zweite_ebene_fix or (not vgericht) or len(tests)==1 or tests[1] in vgericht: # Entweder keine Gerichtsangabe oder Match ok
					if (not vkammer) or not(tests[0]) or tests[0] in vkammer: 
						logger.debug("Match für "+str(i)+": "+m+" Eintrag "+self.gerichte[self.name][i]['Signatur'] )
						if kammermatch==-1:
							kammermatch=i
						else:
							logger.error(num+" mit "+vkammer+" hat doppelten match. Einmal mit Nummer "+str(kammermatch)+" ["+self.gerichte[self.name][kammermatch]['Signatur']+"] und dann noch mit "+str(i)+" ["+self.gerichte[self.name][i]['Signatur']+"]")
							kammermatch=-1
							break
			if kammermatch==-1:
				if self.kammerfallback is not None:
					kammermatch=self.kammerfallback
					logger.warning(num+" mit "+vkammer+" führt zu Kammerfallback")
		else:
			kammermatch=0
		signatur=self.gerichte[self.name][kammermatch]['Signatur']
		gericht=''
		if self.gerichte[self.name][kammermatch]['Stufe 2 DE']:
			gericht=self.gerichte[self.name][kammermatch]['Stufe 2 DE']
		elif self.gerichte[self.name][kammermatch]['Stufe 2 FR']:
			gericht=self.gerichte[self.name][kammermatch]['Stufe 2 FR']
		elif self.gerichte[self.name][kammermatch]['Stufe 2 FR']:
			gericht=self.gerichte[self.name][kammermatch]['Stufe 2 IT']
		kammer=''
		if self.gerichte[self.name][kammermatch]['Stufe 3 DE']:
			kammer=self.gerichte[self.name][kammermatch]['Stufe 3 DE']
		elif self.gerichte[self.name][kammermatch]['Stufe 3 FR']:
			kammer=self.gerichte[self.name][kammermatch]['Stufe 3 FR']
		elif self.gerichte[self.name][kammermatch]['Stufe 3 FR']:
			kammer=self.gerichte[self.name][kammermatch]['Stufe 3 IT']
		return signatur,gericht,kammer	
		


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
