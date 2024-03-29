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
import copy

from NeueScraper.pipelines import MyFilesPipeline
from NeueScraper.pipelines import PipelineHelper

logger = logging.getLogger(__name__)

class BasisSpider(scrapy.Spider):
	elementchars=re.compile("[^-a-zA-Z0-9_]")
	elementre=re.compile("^[a-zA-Z][-a-zA-Z0-9_]+$")
	reDatumEinfach=re.compile("(?P<Tag>\d\d?)\s*\.\s*(?P<Monat>\d\d?)\s*\.\s*(?P<Jahr>(?:19|20)\d\d)")
	MONATEfr = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
	MONATEde = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember']
	MONATEdeKurz = [m[:3] for m in MONATEde]
	MONATEenKurz = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
	reDatumFR=re.compile(r"(?P<Tag>\d\d?)(?:er)?\s+(?P<Monat>(?:"+"|".join(MONATEfr)+r"))\s+(?P<Jahr>(?:19|20)\d\d)")
	reDatumDE=re.compile(r"(?P<Tag>\d\d?)\.\s*(?P<Monat>(?:"+"|".join(MONATEde)+r"))\s+(?P<Jahr>(?:19|20)\d\d)")
	reDatumDEkurz=re.compile(r"(?P<Monat>"+"|".join(MONATEdeKurz)+")\s(?P<Tag>\d\d?),\s*(?P<Jahr>(?:19|20)\d\d)")
	reDatumENkurz=re.compile(r"(?P<Monat>"+"|".join(MONATEenKurz)+")\s(?P<Tag>\d\d?),\s*(?P<Jahr>(?:19|20)\d\d)")
	reDatumNurJahr=re.compile(r"(?:19|20)\d\d")	
	reDatumOk=re.compile("(?:19|20)\d\d-\d\d-\d\d")
	reSplitter=re.compile(r"[a-zA-Z0-9']+")
	reKurzpfad=re.compile(r"^[^/]+/(?P<kurz>[^\.]+)\.(?:pdf|html|json)$")

	#name = 'Gerichtsdaten'
	kantone = { 'de': {'CH':'Eidgenossenschaft','AG':'Aargau','AI':'Appenzell Innerrhoden','AR':'Appenzell Ausserrhoden','BE':'Bern','BL':'Basel-Land','BS':'Basel-Stadt','FR':'Freiburg','GE':'Genf','GL':'Glarus','GR':'Graubünden','JU':'Jura','LU':'Luzern','NE':'Neuenburg','NW':'Nidwalden','OW':'Obwalden','SG':'St.Gallen','SH':'Schaffhausen','SO':'Solothurn','SZ':'Schwyz','TG':'Thurgau','TI':'Tessin','UR':'Uri','VD':'Waadt','VS':'Wallis','ZG':'Zug','ZH':'Zürich'},
		'fr': {'CH':'Conféderation','AG':'Argovie','AI':'Appenzell Rhodes-Intérieures','AR':'Appenzell Rhodes-Extérieures','BE':'Berne','BL':'Bâle-Campagne','BS':'Bâle-Ville','FR':'Fribourg','GE':'Genève','GL':'Glaris','GR':'Grisons','JU':'Jura','LU':'Lucerne','NE':'Neuchâtel','NW':'Nidwald','OW':'Obwald','SG':'Saint-Gall','SH':'Schaffhouse','SO':'Soleure','SZ':'Schwytz','TG':'Thurgovie','TI':'Tessin','UR':'Uri','VD':'Vaud','VS':'Valais','ZG':'Zoug','ZH':'Zurich'},
		'it': {'CH':'Confederazione','AG':'Argovia','AI':'Appenzello Interno','AR':'Appenzello Interno','BE':'Berna','BL':'Basilea Campagna','BS':'Basilea Città','FR':'Friburgo','GE':'Ginevra','GL':'Glarona','GR':'Grigioni','JU':'Giura','LU':'Lucerna','NE':'Neuchâtel','NW':'Nidvaldo','OW':'Obvaldo','SG':'San Gallo','SH':'Sciaffusa','SO':'Soletta','SZ':'Svitto','TG':'Turgovia','TI':'Ticino','UR':'Uri','VD':'Vaud','VS':'Vallese','ZG':'Zugo','ZH':'Zurigo'}}
	kantonssprachen= {'CH':'','AG':'de','AI':'de','AR':'de','BE':'','BL':'de','BS':'de','FR':'','GE':'fr','GL':'de','GR':'','JU':'fr','LU':'de','NE':'fr','NW':'de','OW':'de','SG':'de','SH':'de','SO':'de','SZ':'de','TG':'de','TI':'it','UR':'de','VD':'fr','VS':'','ZG':'de','ZH':'de'}
	gerichte = {}
	kanton= {}
	translation = { 'publiziert': {'de': 'publiziert', 'fr': 'publié', 'it': 'pubblicato'}}
	CSV_URL='https://docs.google.com/spreadsheets/d/e/2PACX-1vR2sZY8Op7cLChL6Hu0aDZmbOrmX_UPtyxz86W-oeyuCemBs0poqxC-EU33i-JhH9PQ7SMqYOnIw5ou/pub?output=csv'
	# CSV_URL='https://docs.google.com/spreadsheets/d/e/2PACX-1vR2sZY8Op7cLChL6Hu0aDZmbOrmX_UPtyxz86W-oeyuCemBs0poqxC-EU33i-JhH9PQ7SMqYOnIw5ou/pub?gid=1220663602&single=true&output=csv'
	#JOBS_HOST='http://entscheidsuche.ch.s3.amazonaws.com/'
	#JOBS_URL=JOBS_HOST+'?list-type=2&prefix=scraper%2F'
	JOBS_HOST='https://entscheidsuche.ch'
	JOBS_URL=JOBS_HOST+'/docs/Jobs/'
	BLOCKLISTE='https://entscheidsuche.ch/docs/Blockliste.json'
	blockliste={}
	numliste={}
	
	kammerfallback=None
	files_written ={}
	previous_run={}
	previous_job=None
	ab=None
	neu=None
	# Für alle Dokumente, für die wir keine Daten herbekommen können
	ERSATZDATUM='2021-01-01'

	def __init__(self):
		super().__init__()

	def start_requests(self):
		# lese erst einmal die Spiderdaten und danach werden die Spider in der request_gen geladen.
		yield scrapy.Request(url=self.CSV_URL, callback=self.parse_gerichtsliste, errback=self.errback_httpbin)

	def parse_gerichtsliste(self, response):
		logger.debug("parse_gerichtsliste response.status "+str(response.status))
		logger.info("parse_gerichtsliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_gerichtsliste Rohergebnis: "+response.body_as_unicode())

		self.scrapy_job=os.environ['SCRAPY_JOB']
		logger.debug("SCRAPY_JOB: "+self.scrapy_job)

		item= { 'Entscheidquellen': response.body_as_unicode() }
		yield(item)

		virtualFile = StringIO(response.body_as_unicode())
		reader = csv.DictReader(virtualFile)
		for row in reader:
			if 'Spider' in row:
				spider=row['Spider']
				if spider is not None and spider:
					logger.debug('Zeile mit Eintrag für Spider '+spider+': '+json.dumps(row))
					if spider in self.gerichte:
						self.gerichte[spider].append(row)
					else:
						self.gerichte[spider]=[row]
						
		#XML und ein vereinfachtes JSON daraus machen
		root_e=etree.Element('Spiderliste')
		kantone={}
		json_kantone={}
		for spidername in self.gerichte:
			spidereintrag=self.gerichte[spidername]
			logger.debug("Spider "+spidername+" hat "+str(len(spidereintrag))+ " Spidereinträge")
			for signaturreihe in spidereintrag:
				signatur=signaturreihe['Signatur']
				if not signaturreihe['Test'].lower=='test':
					teile=signatur.split('_')
					kantonskurz=teile[0]			
					gerichtssignatur=teile[0]+"_"+teile[1]	
					if kantonskurz in self.kantone['de']:
						if kantonskurz in kantone:
							json_kanton=json_kantone[kantonskurz]				
							kanton_e=kantone[kantonskurz]
						else:
							json_kanton={'de': self.kantone['de'][kantonskurz], 'fr': self.kantone['fr'][kantonskurz], 'it': self.kantone['it'][kantonskurz], 'gerichte': {}}
							json_kantone[kantonskurz]=json_kanton
							kanton_e=etree.SubElement(root_e,'Kanton')
							kanton_e.set('Name',self.kantone['de'][kantonskurz])
							kanton_e.set('Kurz',kantonskurz.lower())
							kantone[kantonskurz]=kanton_e
						result=kanton_e.findall("./Spider[@Name='"+spidername+"']")
						if result:
							spider_e=result[0]
						else:
							spider_e=etree.SubElement(kanton_e,'Spider')
							spider_e.set('Name', spidername)
						signatur_e=etree.SubElement(spider_e,'Eintrag')
						signatur_e.set('Name', signatur)
						# JSON-Eintrag weitermachen
						if not gerichtssignatur in json_kanton['gerichte']:
							logger.info("Gerichtsname "+gerichtssignatur+" abgleichen: "+json.dumps(signaturreihe))
							gerichtsname_de=signaturreihe['Stufe 2 de']
							gerichtsname_fr=signaturreihe['Stufe 2 fr']
							gerichtsname_it=signaturreihe['Stufe 2 it']
							if gerichtsname_de=="":
								if gerichtsname_fr:
									gerichtsname_de=gerichtsname_fr
								else:
									gerichtsname_de=gerichtsname_it
								signaturreihe['Stufe 2 de']=gerichtsname_de
							if gerichtsname_fr=="":
								if gerichtsname_de:
									gerichtsname_fr=gerichtsname_de
								else:
									gerichtsname_fr=gerichtsname_it
								signaturreihe['Stufe 2 fr']=gerichtsname_fr
							if gerichtsname_it=="":
								if gerichtsname_de:
									gerichtsname_it=gerichtsname_de
								else:
									gerichtsname_it=gerichtsname_fr
								signaturreihe['Stufe 2 it']=gerichtsname_it
							json_gericht={'de': gerichtsname_de, 'fr': gerichtsname_fr, 'it': gerichtsname_it, 'kammern': {}}
							json_kanton['gerichte'][gerichtssignatur]=json_gericht
							logger.info("Gerichtsname "+gerichtssignatur+" abgeglichen: "+json.dumps(signaturreihe))
						else:
							json_gericht=json_kanton['gerichte'][gerichtssignatur]
						if not signatur in json_gericht:
							kammername_de=signaturreihe['Stufe 3 de']
							kammername_fr=signaturreihe['Stufe 3 fr']
							kammername_it=signaturreihe['Stufe 3 it']
							if kammername_de=="":
								if kammername_fr:
									kammername_de=kammername_fr
								else:
									kammername_de=kammername_it
								signaturreihe['Stufe 3 de']=kammername_de
							if kammername_fr=="":
								if kammername_de:
									kammername_fr=kammername_de
								else:
									kammername_fr=kammername_it
								signaturreihe['Stufe 3 fr']=kammername_fr
							if kammername_it=="":
								if kammername_de:
									kammername_it=kammername_de
								else:
									kammername_it=kammername_fr
								signaturreihe['Stufe 3 it']=kammername_it
							# Sind Kammernamen überhaupt gesetzt?
							if kammername_de:
								json_kammer={'spider': spidername, 'de': kammername_de, 'fr': kammername_fr, 'it': kammername_it}
							else:
								json_kammer={'spider': spidername}
							json_gericht['kammern'][signatur]=json_kammer
					for spalte in signaturreihe:
						wert=signaturreihe[spalte]
						if(wert):
							spaltenname=self.elementchars.sub('_',spalte)
							if not self.elementre.match(spaltenname):
								spaltenname='X_'+spaltenname
							spalte_e=etree.SubElement(signatur_e,spaltenname)
							spalte_e.text=wert
							
		xml_content = '<?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="/Spider.xsl"?>\n'
		xml_content = xml_content+str(etree.tostring(root_e, pretty_print=True),"ascii")
		item= { 'Spiderliste': xml_content }
		yield(item)
		
		# JSON um default-Werte ergänzen:
		for k in json_kantone:
			if not k+"_XX" in json_kantone[k]['gerichte']:
				erstes_gericht=next(iter(json_kantone[k]['gerichte']))
				erste_kammer=next(iter(json_kantone[k]['gerichte'][erstes_gericht]['kammern']))
				json_kantone[k]['gerichte'][k+"_XX"]={'de': "unbekanntes Gericht", 'fr': "tribunal inconnu", "it": "corte sconosciuta",
					'kammern':{ k+"_XX_001": { 'spider': json_kantone[k]['gerichte'][erstes_gericht]['kammern'][erste_kammer]['spider']}}}
			for g in json_kantone[k]['gerichte']:
				# Nur dann Fallback-Kammer reinnehmen, wenn es mehr als eine Kammer gibt.
				if not g+"_999" in json_kantone[k]['gerichte'][g]['kammern'] and len(json_kantone[k]['gerichte'][g]['kammern'])>1:
					erste_kammer=next(iter(json_kantone[k]['gerichte'][g]['kammern']))				
					json_kantone[k]['gerichte'][g]['kammern'][g+'_999']={'de': "andere", 'fr': "autres", "it": "altro", 'spider': json_kantone[k]['gerichte'][g]['kammern'][erste_kammer]['spider']}
		

		# json_content=json.dumps(json_kantone, sort_keys=True)
		json_content=json.dumps(json_kantone)
		item= { 'Facetten': json_content}
		yield(item)

		htaccess="Options +Indexes\n"
		htaccess+="Header set Access-Control-Allow-Origin *\n"
		htaccess+="RewriteEngine On\n"
		htaccess+="RewriteBase /\n"
		htaccess+='RewriteRule "^Facetten.json" "/docs/facetten.php" [L]\n'		
		htaccess+='RewriteRule "^Index/([^/]+)/last$" "/docs/lese_index.php?spider=$1" [L]\n'
		htaccess+='RewriteRule "^Jobs/([^/]+)/last$" "/docs/lese_job.php?spider=$1" [L]\n'
		
		for c in json_kantone:
			for g in json_kantone[c]['gerichte']:
				for k in json_kantone[c]['gerichte'][g]['kammern']:
					s=json_kantone[c]['gerichte'][g]['kammern'][k]['spider']
					htaccess+=f'RewriteRule "^({k}_.*)$" "/docs/{s}/$1" [L]\n'
					htaccess+='RewriteCond %{HTTP_REFERER} !^.*entscheidsuche.ch.* [NC]\n'
					# htaccess+=f'RewriteRule "^{s}/(.+\.(html|pdf))$" "/doc.php?spider={s}&doc=$1" [L]\n'
					
		item= { 'htaccess': htaccess}
		yield(item)

		#Redirects für die Website schreiben
						
		if self.name in self.gerichte:
			if 'Signatur' in self.gerichte[self.name][0]:
				signatur=self.gerichte[self.name][0]['Signatur']
				self.kanton_kurz=signatur[:2]
				if self.kanton_kurz in self.kantone['de']:
					self.kanton['de']=self.kantone['de'][self.kanton_kurz]
					self.kanton['fr']=self.kantone['fr'][self.kanton_kurz]
					self.kanton['it']=self.kantone['it'][self.kanton_kurz]
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
			'Stufe 2 de' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 de']==i['Stufe 2 de'] for i in self.gerichte[self.name]) and
			'Stufe 2 fr' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 fr']==i['Stufe 2 fr'] for i in self.gerichte[self.name]) and
			'Stufe 2 it' in self.gerichte[self.name][0] and all(self.gerichte[self.name][0]['Stufe 2 it']==i['Stufe 2 it'] for i in self.gerichte[self.name])):
			self.zweite_ebene_fix=True
			logger.debug("aber 2. Ebene ist fix")
			
			self.stufe2=''
			if 'Stufe 2 it' in self.gerichte[self.name][0]:
				self.stufe2=self.gerichte[self.name][0]['Stufe 2 it']
			if 'Stufe 2 fr' in self.gerichte[self.name][0]:
				self.stufe2=self.gerichte[self.name][0]['Stufe 2 fr']
			if 'Stufe 2 de' in self.gerichte[self.name][0]:
				self.stufe2=self.gerichte[self.name][0]['Stufe 2 de']
			if self.stufe2:
				self.ebenen=2
			else:
				logger.error("2. Ebene leer bei "+self.name)
			self.stufe3=''
			if not self.mehrfachspider:
				if 'Stufe 3 it' in self.gerichte[self.name][0]:
					self.stufe3=self.gerichte[self.name][0]['Stufe 3 it']
				if 'Stufe 3 fr' in self.gerichte[self.name][0]:
					self.stufe3=self.gerichte[self.name][0]['Stufe 3 fr']
				if 'Stufe 3 de' in self.gerichte[self.name][0]:
					self.stufe3=self.gerichte[self.name][0]['Stufe 3 de']
				if self.stufe3:
					self.ebenen=3
		else: #Zweite Ebene ist variabel
			self.zweite_ebene_fix=False
			logger.debug("Mehrfachspider, dessen 2. Ebene variabel ist")
			for g in self.gerichte[self.name]:
				if 'Stufe 3 de' in g or 'Stufe 3 fr' in g or 'Stufe 3 it' in g:
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
			self.GNmatch={}
			for i in range(len(self.gerichte[self.name])):
				if self.gerichte[self.name][i]['Signatur'][-4:-1]=="_99":
					self.kammerfallback=i
				elif 'Matching' in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Matching']!="":
					matching=self.gerichte[self.name][i]['Matching'].split("|")
					logger.info("Matchings: "+json.dumps(matching))
					for m in matching:
						logger.info("Bearbeite Matching: "+m)
						if m in self.kammerwahl:
							logger.error("Doppeltes Matching! Matchkey '"+m+"' bereits für "+str(self.kammerwahl[m])+"["+self.gerichte[self.name][self.kammerwahl[m]]['Signatur']+"] belegt und nun nochmal für "+str(i)+"["+self.gerichte[self.name][i]['Signatur']+"]!")
						else:
							self.kammerwahl[m]=i
				else:
					for lang in {"de", "fr", "it"}:
						gericht="";
						if not self.zweite_ebene_fix: #Falls Gerichtsebene nicht fix, Gericht mit in das Matching einbeziehen
							if 'Stufe 2 '+lang in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 2 '+lang]!='':
								gericht= "@"+self.gerichte[self.name][i]['Stufe 2 '+lang]
						if 'Stufe 3 '+lang in self.gerichte[self.name][i] and self.gerichte[self.name][i]['Stufe 3 '+lang]!='':
							self.kammerwahl[self.gerichte[self.name][i]['Stufe 3 '+lang]+gericht]=i
						elif gericht!='':
							self.kammerwahl[gericht]=i
				gnMatch=self.gerichte[self.name][i]['GN-Match']
				if gnMatch:
					for teil in gnMatch.split("|"):
						# Schon vorhanden, Geschäftsnummernmatch muss nicht eindeutig sein.
						if teil in self.GNmatch:
							self.GNmatch[teil].append(i)
						else:
							self.GNmatch[teil]=[i]

			logger.info("GNmatch ist "+json.dumps(self.GNmatch))							
			logger.info("kammerwahl ist "+json.dumps(self.kammerwahl))
		
		if self.kammerfallback is None and self.mehrfachspider: #Wenn kein Default spider angegeben, baue selbst einen aus dem Eintrag 0
			#kein Kammerfallback gesetzt aber Mehrfachspider. Generiere daher Kammerfallback
			row=copy.deepcopy(self.gerichte[self.name][0])
			row['Signatur']=row['Signatur'].rpartition("_")[0]+"_999"
			row['Matching']=''
			row['Stufe 3 de']='Sonstige Kammer'
			row['Stufe 3 fr']='Autre chambre'
			row['Stufe 3 it']='Altro camera'
			if(not self.zweite_ebene_fix):
				row['Stufe 2 de']='Sonstiges Gericht'
				row['Stufe 2 fr']='Autre tribunal'
				row['Stufe 2 it']='Altro tribunale'
			self.kammerfallback=len(self.gerichte[self.name])
			logger.info("Generiertes Kammerfallback "+str(self.kammerfallback)+": "+json.dumps(row))
			self.gerichte[self.name].append(row)
		
		logger.debug("Gerichtsliste verarbeitet")
		
		if self.neu=="neu":
			logger.debug("Neuer Job, hole nun die Blockliste.")
			yield scrapy.Request(url=self.BLOCKLISTE, callback=self.parse_blockliste, errback=self.errback_httpbin)
		
		else:
			logger.debug("hole nun die Jobliste.")
	
			# Nun einlesen, was an Dateien vom letzten Spidern vorhanden ist
			#jobs_url=self.JOBS_URL+self.name+"%2FJob_"
			jobs_url=self.JOBS_URL+self.name+"/last"
			logger.info("Jobs-URL: "+jobs_url)
			yield scrapy.Request(url=jobs_url, callback=self.parse_dateiliste, errback=self.errback_httpbin, meta={'handle_httpstatus_list': [404]})
		
	def parse_jobliste_S3(self, response):
		logger.debug("parse_jobliste_S3 response.status "+str(response.status))
		logger.info("parse_jobliste_S3 Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_jobliste_S3 Rohergebnis: "+response.body_as_unicode())
		jobs=response.xpath("//*[local-name()='Contents']/*[local-name()='Key']/text()").getall()
		if jobs:
			jobs.sort(reverse=True)
			yield scrapy.Request(url=self.JOBS_HOST+jobs[0], callback=self.parse_dateiliste, errback=self.errback_httpbin)
		else:
			logger.info("Kein vorheriger Job gefunden. Erster Lauf von: "+self.name)
			yield scrapy.Request(url=self.BLOCKLISTE, callback=self.parse_blockliste, errback=self.errback_httpbin)

	def parse_dateiliste(self, response):
		logger.info("parse_dateiliste response.status "+str(response.status))
		logger.info("parse_dateiliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_dateiliste Rohergebnis: "+response.body_as_unicode()[:10000])
		previous_run=json.loads(response.body_as_unicode())
		if 'job' in previous_run and previous_run['job'] != 'nojob':
			self.previous_run=previous_run
			# Wird nur eine Teilabfrage gemacht, die Daten der vorherigen Abfrage übernehmen und mit der Quelle kennzeichnen
			self.previous_job=self.previous_run["job"]
			for pfad in self.previous_run["dateien"]:
				eintrag=self.previous_run["dateien"][pfad]
				checksum=eintrag['checksum']
				status=eintrag["status"]
				quelle=eintrag["quelle"] if "quelle" in eintrag else self.previous_job
				last_change=eintrag["last_change"] if "last_change" in eintrag else self.previous_job
				self.files_written[pfad]={'checksum': checksum, 'status': status, 'quelle': quelle, 'last_change': last_change}
		else:
			logger.info("Kein vorheriger Job gefunden. Erster Lauf von: "+self.name)
		yield scrapy.Request(url=self.BLOCKLISTE, callback=self.parse_blockliste, errback=self.errback_httpbin)


	def parse_blockliste(self, response):
		logger.info("parse_blockliste response.status "+str(response.status))
		logger.info("parse_blockliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_blockliste Rohergebnis: "+response.body_as_unicode()[:10000])
		blockliste=json.loads(response.body_as_unicode())
		if self.name in blockliste:
			self.blockliste=blockliste[self.name]
			logger.info("Blocklisteneinträge gefunden: "+json.dumps(blockliste[self.name]))
		else:
			logger.info("keine Blocklisteneinträge für "+self.name)
		logger.info(" "+str(len(self.request_gen))+" Requests.")
		
		#Die Blockliste gleich auf die bisherigen Dateien anwenden
		for pfad in self.files_written:
			kurzpfad=self.reKurzpfad.search(pfad)
			if kurzpfad:
				if kurzpfad['kurz'] in self.blockliste:
					if self.files_written[pfad]['status']=="nicht_mehr_da":
						logger.info("Pfad "+pfad+" in Blockliste und als 'nicht_mehr_da' gekennzeichnet.")
					else:
						logger.warning("Pfad "+pfad+" in Blockliste und war bislang als "+self.files_written[pfad]['status']+" gekennzeichnet und wird nun als 'nicht_mehr_da' gekennzeichnet.")
						self.files_written[pfad]['status']="nicht_mehr_da"
			else:
				logger.error("Fehler bei Kurzpfaderkennung von: "+pfad)
		
		for req in self.request_gen:
			logger.info("Starte nun Request "+req.url+" mit Header "+PipelineHelper.mydumps(req.headers)+" und Body "+PipelineHelper.mydumps(req.body))
			yield req


	def detect(self,vgericht,vkammer,num):
		logger.info(num+": vgericht='"+vgericht+"', vkammer='"+vkammer+"', num='"+num+"'")
		if self.mehrfachspider:
			kammermatches={}
			for m in self.kammerwahl:
				i=self.kammerwahl[m]
				tests=m.split("@")
				# Wenn enweder die erste Ebene matched und die zweite nicht dagegens steht oder die zweite Ebene matched und die erste nicht dagegen steht, dann ist es ein match
				if ((self.zweite_ebene_fix or (not vgericht) or len(tests)==1) and tests[0] and tests[0] in vkammer) or (len(tests)>1 and vgericht and tests[1] in vgericht and ((not vkammer) or not(tests[0]) or tests[0] in vkammer)):
					logger.info("Match für "+str(i)+": "+m+" Eintrag "+self.gerichte[self.name][i]['Signatur'] )
					kammermatches[i]=len(m)
						
			# Falls Geschäftsnummernmatch vorhanden, zähle das wie ein 100Zeichen-Match bei der Kammer.
			if len(kammermatches)!=1:
				if len(self.GNmatch)>0:
					GN_matches=[]
					sps=self.reSplitter.findall(num)
					logger.info("Splitter: "+json.dumps(sps))
					for sp in range(len(sps)):
						matchstring=str(sp+1)+"#"+sps[sp]
						logger.info("Matchstring: "+matchstring)
						if matchstring in self.GNmatch:
							info=""
							for k in self.GNmatch[matchstring]:
								info+=str(k)+"("+self.gerichte[self.name][k]['Signatur']+") "
							logger.info("Geschäftsnummermatch für "+matchstring+": "+info)				
							for i in self.GNmatch[matchstring]:
								if i in kammermatches:
									kammermatches[i]+=100
								else:
									kammermatches[i]=100
				# Falls mehrere Matches, nehme den mit dem höchsten Score
				if len(kammermatches)>1:
					sortiert = sorted(kammermatches.items(), key=lambda x: x[1], reverse=True)
					if sortiert[0][1]==sortiert[1][1]:
						logger.warning(num+" mit "+vkammer+"@"+vgericht+" hat doppelten match. Einmal mit Nummer "+str(sortiert[0][0])+" ["+self.gerichte[self.name][sortiert[0][0]]['Signatur']+"] und dann noch mit "+str(sortiert[1][0])+" ["+self.gerichte[self.name][sortiert[1][0]]['Signatur']+"] mit identischem Score ("+str(sortiert[0][1])+") -> Kammerfallback")
						kammermatch=self.kammerfallback
					else:
						logger.info(num+" mit "+vkammer+"@"+vgericht+" hat doppelten match. Match mit Nummer "+str(sortiert[0][1])+" ["+self.gerichte[self.name][sortiert[0][0]]['Signatur']+"] ist besser (Score "+str(sortiert[0][0])+") als Match mit Nummer "+str(sortiert[1][0])+" ["+self.gerichte[self.name][sortiert[1][0]]['Signatur']+"] (Score "+str(sortiert[1][1])+")")
						kammermatch=sortiert[0][0]
				elif len(kammermatches)==0:
					kammermatch=self.kammerfallback
					logger.warning(num+" mit "+vkammer+"@"+vgericht+" hat keine Matches und führt zu Kammerfallback")
				else:
					kammermatch=list(kammermatches.items())[0][0]
					logger.info("Eindeutiger Geschäftsnummernmatch "+str(kammermatch)+" ["+self.gerichte[self.name][kammermatch]['Signatur']+"]")			
			else:
				kammermatch=list(kammermatches.items())[0][0]
				logger.info("Eindeutiger Kammermatch "+str(kammermatch)+" ["+self.gerichte[self.name][kammermatch]['Signatur']+"]")					
		else:
			kammermatch=0
		metamatch=self.gerichte[self.name][kammermatch]
		signatur=metamatch['Signatur']
		logger.info("Kammermatch: "+str(kammermatch)+" Signatur: "+signatur)
		gericht=''
		if metamatch['Stufe 2 de']:
			gericht=metamatch['Stufe 2 de']
		elif metamatch['Stufe 2 fr']:
			gericht=metamatch['Stufe 2 fr']
		elif metamatch['Stufe 2 it']:
			gericht=metamatch['Stufe 2 it']
		kammer=''
		if metamatch['Stufe 3 de']:
			kammer=metamatch['Stufe 3 de']
		elif metamatch['Stufe 3 fr']:
			kammer=metamatch['Stufe 3 fr']
		elif metamatch['Stufe 3 it']:
			kammer=metamatch['Stufe 3 it']
		return signatur,gericht,kammer	
		
	def detect_by_signatur(self,signatur):
		eintrag=self.gerichte[self.name]
		for e in eintrag:
			if e['Signatur']==signatur:
				metamatch=e
				gericht=''
				if e['Stufe 2 de']:
					gericht=e['Stufe 2 de']
				elif e['Stufe 2 fr']:
					gericht=e['Stufe 2 fr']
				elif e['Stufe 2 it']:
					gericht=e['Stufe 2 it']
				kammer=''
				if e['Stufe 3 de']:
					kammer=e['Stufe 3 de']
				elif e['Stufe 3 fr']:
					kammer=e['Stufe 3 fr']
				elif e['Stufe 3 it']:
					kammer=e['Stufe 3 it']
				
				return gericht, kammer
		logger.error("Signatur "+signatur+" nicht in "+str(len(eintrag))+" Einträge gefunden: "+",".join([e['Signatur'] for e in eintrag]))
		# Hier kommt nichts zurück, daher der Fehler.		

	def norm_datum(self,datum,error=None, warning=None, info=None):
		match=self.reDatumOk.match(datum)
		if match:
			neudat=match.group(0)
		else:
			dat=self.reDatumEinfach.search(datum)
			if dat:
				logger.info("Datumsmatch für "+datum)
				neudat="{}-{:0>2}-{:0>2}".format(dat.group('Jahr'),dat.group('Monat'),dat.group('Tag'))
				logger.debug("Konvertiere "+datum+" in "+neudat)
			else:
				datfr=self.reDatumFR.search(datum)
				if datfr:
					monat=datfr.group('Monat')
					monatzahl=self.MONATEfr.index(monat)+1
					neudat="{}-{:0>2}-{:0>2}".format(datfr.group('Jahr'),monatzahl,datfr.group('Tag'))
					logger.debug("Konvertiere "+datum+" in "+neudat)
				else:
					datde=self.reDatumDE.search(datum)
					if datde:
						monat=datde.group('Monat')
						monatzahl=self.MONATEde.index(monat)+1
						neudat="{}-{:0>2}-{:0>2}".format(datde.group('Jahr'),monatzahl,datde.group('Tag'))
						logger.debug("Konvertiere "+datum+" in "+neudat)
					else:
						datde=self.reDatumDEkurz.search(datum)
						if datde:
							monat=datde.group('Monat')
							monatzahl=self.MONATEdeKurz.index(monat)+1
							neudat="{}-{:0>2}-{:0>2}".format(datde.group('Jahr'),monatzahl,datde.group('Tag'))
							logger.debug("Konvertiere "+datum+" in "+neudat)
						else:
							datde=self.reDatumENkurz.search(datum)
							if datde:
								monat=datde.group('Monat')
								monatzahl=self.MONATEenKurz.index(monat)+1
								neudat="{}-{:0>2}-{:0>2}".format(datde.group('Jahr'),monatzahl,datde.group('Tag'))
								logger.debug("Konvertiere "+datum+" in "+neudat)
							else:
								nurJahr=self.reDatumNurJahr.search(datum)
								if nurJahr:
									logger.warning("Jahreszahl statt vollständiges Datum: "+datum)
									neudat=nurJahr.group(0)
								else:
									if error:
										logger.error(error + " unbekanntes Datumsformat: "+datum)
									elif warning:
										logger.warning(warning + "unbekanntes Datumsformat: "+datum)
									elif info:
										logger.info(info + "unbekanntes Datumsformat: "+datum)
									else:
										logger.error("unbekanntes Datumsformat: "+datum)
									neudat="nodate"
		datum=neudat
		return datum

	def check_blockliste(self, item):
		pfad=PipelineHelper.file_path(item, self).split("/",1)[1]
		logger.debug("Teste "+pfad+" auf Blockliste")
		if pfad in self.blockliste:
			logger.error("Dokument geblockt: "+pfad)
			return False
		else:
			return True

	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
		

		
	