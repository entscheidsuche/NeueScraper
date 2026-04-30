# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import datetime
import random
import time
import json
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
from datetime import date
from datetime import timedelta
import copy

logger = logging.getLogger(__name__)

class CH_BSTG(BasisSpider):
	name = 'CH_BSTG'
	HOST='https://bstger.weblaw.ch'
	SESSION="/api/auth/session"
	URL="/api/getDocuments?withAggregations=true"

	PDFURL="/api/getDocumentFile/"
	MAX=100
	tage=64
	AB="2004-01-01"
	STARTJAHR=2004
	HEADER={'Content-Type': 'application/json', 'Accept': '*/*', 'Origin': 'https://bstger.weblaw.ch', 'Referer': 'https://bstger.weblaw.ch/?sort-field=relevance&sort-direction=relevance'}
	COOKIEJAR=0
	custom_settings = {
        "COOKIES_ENABLED": True
    }
    
	# JSON={"sortOrder":"desc","sortField":"publicationDate","size":60,"guiLanguage":"de","userID":"_9ynrsjyup","sessionDuration":1638755448,"origin":"Dashboard","aggs":{"fields":["rulingType","tipoSentenza","year","court","language","lex-ch-bund-srList","ch-jurivocList","jud-ch-bund-bgeList","jud-ch-bund-bguList","jud-ch-bund-bvgeList","jud-ch-bund-bvgerList","jud-ch-bund-tpfList","jud-ch-bund-bstgerList","lex-ch-bund-asList","lex-ch-bund-bblList","lex-ch-bund-abList","jud-ch-ag-agveList"],"size":10}}
	# JSON={"from": 0, "guiLanguage":"de","userID":"_qkhhh52","aggs":{"fields":["jud-ch-bund-bvgeList","bgeStatus","rulingType","tipoSentenza","year","jud-ch-ag-agveList","lex-ch-bund-bblList","bgeDossierList","language","jud-ch-bund-bguList","jud-ch-bund-bvgerList","bstgerDossierList","sortRulingDate","court","ch-jurivocList","lex-ch-bund-srList","jud-ch-bund-bstgerList","lex-ch-bund-abList","jud-ch-bund-tpfList","lex-ch-bund-asList","tpfDossierList","jud-ch-bund-bgeList","sortPublicationDate","filterDate","publicationDate","rulingDate","author"],"size":"10"}}
	JSON1={"guiLanguage":"de","metadataDateMap":{"rulingDate":{"from":"1900-01-01","to":"2030-12-31"}},"userID":"_vqykh2x","from":0,"aggs":{"fields":["jud-ch-bund-bvgeList","bgeStatus","rulingType","tipoSentenza","lex-ch-bund-bblList","bgeDossierList","language","jud-ch-bund-bguList","jud-ch-bund-bvgerList","sortRulingDate","court","ch-jurivocList","lex-ch-bund-srList","jud-ch-bund-bstgerList","jud-ch-bund-tpfList","lex-ch-bund-asList","jud-ch-bund-bgeList","sortPublicationDate","filterDate","publicationDate","rulingDate","bstgerDossierList","year","tpfDossierList","author","lex-ch-bund-abList"],"size":"10"}}
	JSON2={"guiLanguage":"de","metadataDateMap":{"rulingDate":{"from":None,"to":None}},"metadataKeywordsMap":{"year":"2010"},"userID":"_mcuwjr6","from":0,"sortField":"sortRulingDate","sortDirection":"asc","aggs":{"fields":["jud-ch-bund-bvgeList","bgeStatus","rulingType","tipoSentenza","year","lex-ch-bund-bblList","bgeDossierList","bstgerDossierList","language","jud-ch-bund-bguList","jud-ch-bund-bvgerList","sortRulingDate","court","ch-jurivocList","lex-ch-bund-srList","jud-ch-bund-bstgerList","jud-ch-bund-tpfList","lex-ch-bund-abList","tpfDossierList","lex-ch-bund-asList","jud-ch-bund-bgeList","sortPublicationDate","filterDate","publicationDate","rulingDate","author"],"size":"10"}}

	def get_initial_requests(self, abdatum):
		userID1='_'
		random.seed()
		while len(userID1)<8:
			userID1+="0123456789abcdefghijklmnopqrstuvwxyz"[random.randint(0,35)]
		userID2='_'
		random.seed()
		while len(userID2)<8:
			userID2+="0123456789abcdefghijklmnopqrstuvwxyz"[random.randint(0,35)]
		# epoch=str(int(time.mktime(time.localtime())))
		abdate=date.fromisoformat(abdatum)
		bisdate=abdate+timedelta(self.tage)
		bisdatum=(bisdate+timedelta(1)).strftime("%Y-%m-%d")
		jahrgang=self.STARTJAHR
		#publicationDate wäre nicht granular genug, da an einem Tag mal mehr als 1000 Entscheide veröffentlicht wurden.
		self.JSON1['metadataDateMap']={'rulingDate' : { 'from': abdate.strftime("%Y-%m-%d"), 'to': bisdate.strftime("%Y-%m-%d")}}
		self.JSON1['userID']=userID1
		self.JSON2['metadataKeywordsMap']={"year":str(jahrgang)}
		self.JSON2['userID']=userID2
		# self.JSON['sessionDuration']=epoch
		# Blättern mit Post, Erstrequest mit Get
		self.COOKIEJAR+=1
		request1=scrapy.Request(url=self.HOST+self.SESSION, headers=self.HEADER, callback=self.parse_cookie, errback=self.errback_httpbin, meta={'from': 0, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID1, 'data': self.JSON1, 'cookiejar': self.COOKIEJAR}, dont_filter=True)
		self.COOKIEJAR+=1
		request2=scrapy.Request(url=self.HOST+self.SESSION, headers=self.HEADER, callback=self.parse_cookie, errback=self.errback_httpbin, meta={'from': 0, 'jahrgang': jahrgang, 'userID': userID2, 'data': self.JSON2, 'cookiejar': self.COOKIEJAR}, dont_filter=True)
		# return scrapy.http.JsonRequest(url=self.getProxyUrl(self.HOST+self.URL), headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		# return scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		return [request1,request2]


	def get_next_request(self, abdatum, meta, fromwert=0):
		abdate=date.fromisoformat(abdatum)
		bisdate=abdate+timedelta(self.tage)
		bisdatum=(bisdate+timedelta(1)).strftime("%Y-%m-%d")
		#publicationDate wäre nicht granular genug, da an einem Tag mal mehr als 1000 Entscheide veröffentlicht wurden.
		data=copy.deepcopy(self.JSON1)
		data['metadataDateMap']={'rulingDate' : { 'from': abdate.strftime("%Y-%m-%d"), 'to': bisdate.strftime("%Y-%m-%d")}}
		logger.info(f'Datumsbereich: {abdate.strftime("%Y-%m-%d")} bis {bisdate.strftime("%Y-%m-%d")}')
		# self.JSON['sessionDuration']=epoch
		# Blättern mit Post, Erstrequest mit Get
		if fromwert>0:
			data['from']=fromwert
			
		request=scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=data, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': meta['userID'], 'data': data, 'cookiejar': meta['cookiejar']})

		# return scrapy.http.JsonRequest(url=self.getProxyUrl(self.HOST+self.URL), headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		# return scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		return request

	def get_next_request_baende(self, jahrgang, meta, fromwert=0):
		data=copy.deepcopy(self.JSON2)
		data['metadataKeywordsMap']={"year":str(jahrgang)}
		logger.info(f'Jahrgang: {jahrgang}')
		if fromwert>0:
			data['from']=fromwert
			
		request=scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=data, callback=self.parse_trefferliste_baende, errback=self.errback_httpbin, meta={'from': fromwert, 'jahrgang': jahrgang, 'userID': meta['userID'], 'data': data, 'cookiejar': meta['cookiejar']})

		# return scrapy.http.JsonRequest(url=self.getProxyUrl(self.HOST+self.URL), headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		# return scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=self.JSON, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'from': fromwert, 'abdatum': abdatum, 'bisdatum':bisdatum, 'userID': userID})
		return request
		
	def request_generator(self, ab):
		return self.get_initial_requests(ab)
		
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab=ab
		if not ab:
			self.ab=self.AB	
		self.neu=neu

	def parse_cookie(self, response):
		logger.info("parse_cookie response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_cookie Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_cookie Rohergebnis: "+antwort[0:50000])
		logger.info("headers: %r", response.headers)
		logger.info("neuer Request mit "+json.dumps(response.meta['data']))
		
		if "jahrgang" in response.meta:
			request=scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=response.meta['data'], callback=self.parse_trefferliste_baende, errback=self.errback_httpbin, meta=response.meta)
		else:
			request=scrapy.http.JsonRequest(url=self.HOST+self.URL, headers=self.HEADER, data=response.meta['data'], callback=self.parse_trefferliste, errback=self.errback_httpbin, meta=response.meta)
		return request


		
	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[0:50000])
		
		struktur=json.loads(antwort)
		if struktur['status']=="success":
			struktur=struktur['data']
			treffer=struktur['totalNumberOfDocuments']
			logger.info(str(treffer)+" Entscheide insgesamt. Hier ab Entscheid "+str(response.meta['from']))
			abdatum=response.meta['abdatum']
			bisdatum=response.meta['bisdatum']
			userID=response.meta['userID']
			if treffer>100:
				self.tage=self.tage/2
				request=self.get_next_request(abdatum,response.meta)
				logger.info("Zeitraum "+abdatum+" bis "+bisdatum+" war zu gross. Reduziere Zeitraum auf "+str(self.tage)+" Tage. Hole Entscheide ab: "+abdatum)
				yield request

			else:		
				entscheide=struktur['documents']
				yield from self.bearbeite_trefferliste(entscheide,userID)

				neufrom=response.meta['from']+len(entscheide)
				logger.info(f"bislang {neufrom} Treffer von {treffer} gelesen.")
				if neufrom < treffer:
					if struktur['hasMoreResults']==False:
						logger.error('weitere Trefferanzeige nach '+str(neufrom)+' Treffern nicht möglich (treffer: '+str(treffer)+')')
					else:
						request=self.get_next_request(abdatum, response.meta, neufrom)
						logger.info("Hole Entscheide ab: "+str(neufrom))
						yield request
				else:
					if neufrom > treffer:
						logger.error("Mehr Entscheide geladen ("+str(neufrom)+") als Treffer ("+str(treffer)+").")
					else:
						logger.info(f"ist noch nicht {bisdatum}?")
						if date.fromisoformat(bisdatum) < date.today():
							request=self.get_next_request(bisdatum,response.meta)
							logger.info("Neuer Zeitraum ab "+bisdatum+" und "+str(self.tage)+" Tage.")
							yield request
		else:
			logger.error(f"Fehler: {json.dumps(struktur)}")		
			
	def parse_trefferliste_baende(self, response):
		logger.info("parse_trefferliste_baende response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste_baende Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste_baende Rohergebnis: "+antwort[0:50000])
		
		struktur=json.loads(antwort)
		if struktur['status']=="success":
			struktur=struktur['data']
			treffer=struktur['totalNumberOfDocuments']
			logger.info(str(treffer)+" Entscheide insgesamt. Hier ab Entscheid "+str(response.meta['from']))
			jahrgang=response.meta['jahrgang']
			userID=response.meta['userID']
			if treffer>100:
				logger.error(f"Mehr als 100 Treffer für Jahrgang {jahrgang}. Entscheide gehen verloren.")
			entscheide=struktur['documents']
			yield from self.bearbeite_trefferliste(entscheide,userID)

			neufrom=response.meta['from']+len(entscheide)
			logger.info(f"bislang {neufrom} Treffer von {treffer} gelesen.")
			if neufrom < treffer:
				if struktur['hasMoreResults']==False:
					logger.error('weitere Trefferanzeige nach '+str(neufrom)+' Treffern nicht möglich (treffer: '+str(treffer)+')')
				else:
					request=self.get_next_request_baende(jahrgang, response.meta, neufrom)
					logger.info("Hole Entscheide ab: "+str(neufrom))
					yield request
			else:
				if neufrom > treffer:
					logger.error("Mehr Entscheide geladen ("+str(neufrom)+") als Treffer ("+str(treffer)+").")
				else:
					logger.info(f"Entscheide nach {jahrgang}?")
					if jahrgang < date.today().year:
						request=self.get_next_request_baende(jahrgang+1,response.meta)
						logger.info("Neuer Jahrgang {jahrgang+1}")
						yield request
		else:
			logger.error(f"Fehler: {json.dumps(struktur)}")					

	def bearbeite_trefferliste(self,entscheide,userID):
		logger.info(str(len(entscheide))+" Entscheide in dieser Liste.")
		for entscheid in entscheide:
			item={}
			item['Leitsatz']=PH.NC(entscheid['content'], error="keine Titelzeile in "+json.dumps(entscheid))
			if 'tipoSentenza' in entscheid['metadataKeywordTextMap']:
				item['Weiterzug']=PH.NC(entscheid['metadataKeywordTextMap']['tipoSentenza'][0], warning="keine Weiterzugsinfo in "+json.dumps(entscheid))			
			num=PH.NC(entscheid['metadataKeywordTextMap']['title'][0], error="keine Geschäftsnummer in "+json.dumps(entscheid))
			nums=num.split(", ")
			item['Num']=nums[0]
			item['Nums']=nums
			item['DocID']=PH.NC(entscheid['leid'], error="keine leid gefunden in "+json.dumps(entscheid))
			#item['PDFUrls']=[self.HOST+PH.NC(entscheid['metadataKeywordTextMap']['originalUrl'][0], error="keine URL in "+json.dumps(entscheid))]
			item['PDFUrls']=[self.HOST+self.PDFURL+item['DocID']+"?locale=de&userID="+userID]
			#item['ProxyUrls']=[self.getProxyUrl(self.HOST+self.PDFURL+item['DocID']+"?locale=de&userID="+userID)]
			fileName=PH.NC(entscheid['metadataKeywordTextMap']['fileName'][0],error="Kein Filename für "+json.dumps(entscheid))
			item['PDFPosts']=[json.dumps({'documentTitle':fileName})]
			if 'rulingDate' in entscheid['metadataDateMap']:
				item['EDatum']=self.norm_datum(PH.NC(entscheid['metadataDateMap']['rulingDate'], error="kein Entscheiddatum in "+json.dumps(entscheid))[:10])
			elif 'year' in entscheid['metadataKeywordTextMap']:
				item['EDatum']=self.norm_datum(PH.NC(entscheid['metadataKeywordTextMap']['year'][0], warning="kein Entscheiddatum und auch kein Jahr in "+json.dumps(entscheid))[:10])
			else:
				logger.warning("kein Entscheiddatum in "+item['Num'])
			if 'publicationDate' in entscheid['metadataDateMap']:
				item['PDatum']=self.norm_datum(PH.NC(entscheid['metadataDateMap']['publicationDate'], warning="kein Publikationsdatum in "+json.dumps(entscheid))[:10])
			else:
				if 'year' in entscheid['metadataKeywordTextMap']:
					item['PDatum']=self.norm_datum(PH.NC(entscheid['metadataKeywordTextMap']['year'][0], warning="kein Publikationsdatum und auch kein Jahr in "+json.dumps(entscheid))[:10])
				else:
					logger.warning("kein Entscheiddatum in "+item['Num'])
			item['VGericht']=''
			item['VKammer']=''
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
			item['Kanton']=self.kanton_kurz
			if 'PDatum' in item or 'EDatum' in item:
				yield item
			else:
				logger.error('Entscheid ohne Datum (weder EDatum, PDatum noch year) '+item['Num'])
		