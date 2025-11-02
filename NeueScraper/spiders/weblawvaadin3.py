# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
import uuid
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class WeblawVaadinSpider(BasisSpider):
	
	custom_settings = {
        'COOKIES_ENABLED': True,
        "COOKIES_DEBUG":   True,
        "DOWNLOAD_DELAY": 1.0,
		"ZYTE_API_PRESERVE_DELAY": True
    }

	TREFFERLISTE_URL='/api/.netlify/functions/searchQueryService'
		
	reNum=re.compile(r' href="[^"]+">(?P<Num>[^<]+)</a>')
	reTreffer=re.compile(r'Resultat\s+(?P<von>\d+)-(?P<bis>\d+)\s+von\s+(?P<gesamt>\d+)')
	reKlammer=re.compile(r"^(?:<a[^>]+>)?\s*(?P<vor>[^\s(<][^(<]*[^\s(<])\s*(?:\((?P<in>[^)]+)\)\s*)?(?:</a>)?$")

	def generate_requests(self):
		self.userID="_" + uuid.uuid4().hex[:8]
		self.SUCHFORM['userID']=self.userID
		von=datetime.date.fromisoformat(self.ab)
		heute=datetime.date.today()
		requests=[]
		orgurl=self.HOST
		url=self.getProxyUrl(orgurl)
		jar_id=0
		while von<heute:
			jar_id+=1
			bis=von+datetime.timedelta(days=self.INTERVALL-1)
			vonstring=von.isoformat()
			bisstring=bis.isoformat()
			request=scrapy.Request(url=url, headers=self.HEADER1, callback=self.parse_suchform, errback=self.errback_httpbin, meta={'noproxyurl': orgurl, 'cookiejar': jar_id, 'von': vonstring, "bis": bisstring,  "dont_redirect": True, "handle_httpstatus_list": [301,302,303,307,308], 'dont_cache': True}, dont_filter=True)
			von=von+datetime.timedelta(days=self.INTERVALL)
			requests.append(request)
		return requests
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab==None:
			self.ab=self.STARTDATE
		else:
			self.ab=ab
		
	def start_requests(self):
		# vor Super-Call Settings lesen / Defaults setzen
		self.cfg = self.crawler.settings.get('MY_GLOBAL', 'default')
		self.request_gen = self.generate_requests()
		for req in super().start_requests():
			req.meta.setdefault('cfg', self.cfg)
			yield req

	def parse_suchform(self, response):
		#Nur für Cookie holen:
		jar_id=response.meta['cookiejar']
		logger.info("parse_suchform response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_suchform Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_suchform Rohergebnis: "+antwort[:30000])
		vonstring=response.meta['von']
		bisstring=response.meta['bis']
		noproxyurl=response.meta['noproxyurl']
		if 300 <= response.status < 400:
			orgurl = response.headers.get("Location", b"").decode("latin1")
			self.logger.info(f"{response.status}: Umleitung von {noproxyurl} nach {orgurl} für Zeitraum {vonstring} - {bisstring}")
			url=self.getProxyUrl(orgurl)
			request=scrapy.Request(url=url, headers=self.HEADER1, callback=self.parse_suchform, errback=self.errback_httpbin, meta={'noproxyurl': orgurl, 'cookiejar': jar_id, 'von': vonstring, "bis": bisstring, "dont_redirect": True, "handle_httpstatus_list": [301,302,303,307,308], 'dont_cache': True}, dont_filter=True)	
		else:		
			url=self.getProxyUrl(self.HOST+self.TREFFERLISTE_URL)
			suchform=copy.deepcopy(self.SUCHFORM)
			suchform['metadataDateMap']['publicationDate']['from']=vonstring+"T00:00:00.000Z"
			suchform['metadataDateMap']['publicationDate']['to']=bisstring+"T23:59:59.999Z"
			request=scrapy.Request(url=url, headers=self.HEADER2, body=json.dumps(suchform), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id, 'von': vonstring, 'bis': bisstring, 'suchform': suchform, 'from':0})

		yield request
		

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort)
		jar_id=response.meta['cookiejar']
		suchform=response.meta['suchform']
		vonstring=response.meta['von']
		bisstring=response.meta['bis']
		vonTreffer=response.meta['from']
		
		struk=json.loads(antwort)
		# Statt über die Hierarchie könnte man auch über types gehen alle Einträge haben type 1
		treffer=struk['totalNumberOfDocuments']
		if treffer==0:
			logger.warning(f"Kein Treffer für Zeitraum {vonstring} - {bisstring}")
		elif treffer>100:
			requests=[]
			logger.info(f"Mehr als 100 Treffer: {treffer} für Zeitraum {vonstring} - {bisstring}")
			von=datetime.date.fromisoformat(vonstring)
			bis=datetime.date.fromisoformat(bisstring)
			halbeTage=(bis-von).days/2
			bishalbe=von+datetime.timedelta(days=halbeTage-1)
			vonhalbe=von+datetime.timedelta(days=halbeTage)
			bishalbestring=bishalbe.isoformat()
			vonhalbestring=vonhalbe.isoformat()
			logger.warning(f"Mehr als 100 Treffer: {treffer} für Zeitraum {vonstring} - {bisstring} aufgeteilt in {vonstring} - {bishalbestring} und {vonhalbestring} - {bisstring}.")
			suchform=self.SUCHFORM
			suchform['metadataDateMap']['publicationDate']['from']=vonstring+"T00:00:00.000Z"
			suchform['metadataDateMap']['publicationDate']['to']=bishalbestring+"T23:59:59.999Z"
			url=self.getProxyUrl(self.HOST+self.TREFFERLISTE_URL)
			request=scrapy.Request(url=url, headers=self.HEADER2, body=json.dumps(suchform), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id, 'von': vonstring, 'bis': bishalbestring, 'suchform': suchform, 'from':0})		
			requests.append(request)
			suchform=self.SUCHFORM
			suchform['metadataDateMap']['publicationDate']['from']=vonhalbestring+"T00:00:00.000Z"
			suchform['metadataDateMap']['publicationDate']['to']=bisstring+"T23:59:59.999Z"
			request=scrapy.Request(url=url, headers=self.HEADER2, body=json.dumps(suchform), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id, 'von': vonhalbestring, 'bis': bisstring, 'suchform': suchform, 'from':0})		
			requests.append(request)
			for r in requests:
				yield r
		else:
			if vonTreffer==0:
				logger.info(f"{treffer} Treffer für Zeitraum {vonstring} - {bisstring}")
			
			docs=struk['documents']
			logger.info(str(len(docs))+" Dokumente gefunden")
			for i in docs:
				meta1=i['metadataKeywordTextMap']
				meta2=i['metadataDateMap']
				item={}
				text=json.dumps(i)
				item['PDFUrls']=[PH.NC(meta1['originalUrl'][0],error="keine PDF-URL in "+text)]
				item['PDFUrls'][0]=item['PDFUrls'][0].replace(' ','%20')
				item['ProxyUrls']=[self.getProxyUrl(item["PDFUrls"][0])]
				item['Num']=PH.NC(meta1['title'][0].split(" ",1)[1],error="keine Num in "+text)
				item['VGericht']=PH.NC(meta1['argvpBehoerde'][0],error="kein Gericht in "+text)
				item['EDat']=PH.NC(self.norm_datum(meta2['decisionDate'][:10]),warning="kein Entscheiddatum in "+text)
				item['PDat']=PH.NC(self.norm_datum(meta2['publicationDate'][:10]),warning="kein Publikationsdatum in "+text)
				item['Abstract']=PH.NC(i['content'],warning="kein Abstract in "+text)
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
				item['CookieJar']=jar_id
				yield item
			if struk['hasMoreResults']==True:
				vonTreffer=vonTreffer+10
				if vonTreffer==10:
					logger.info("mehr Treffer, lade zweite Seite")
				else:
					logger.info(f"mehr Treffer, ab Treffer {vonTreffer} von {treffer}")
				suchform['from']=vonTreffer
				url=self.getProxyUrl(self.HOST+self.TREFFERLISTE_URL)
				request=scrapy.Request(url=url, body=json.dumps(suchform), headers=self.HEADER2, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id, 'von': vonstring, 'bis': bisstring, 'from':vonTreffer, 'suchform': suchform})
				yield request
			else:
				logger.info(f"Alle {treffer} des Zeitraums {vonstring} - {bisstring} abgearbeitet. Fertig")

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']
		PH.write_html(antwort, item, self)
		yield(item)
	
		
	def lese_hierarchie(self, struk,obj,hierarchie):
		logger.debug("Hole "+hierarchie+" von "+str(obj))
		trail=str(obj)
		for p in hierarchie.split("-"):
			if obj in struk[0]['hierarchy'] and len(struk[0]['hierarchy'][obj])>int(p):
				obj=struk[0]['hierarchy'][obj][int(p)]
				trail+="["+p+"]->"+str(obj)
			else:
				if obj in struk[0]['hierarchy']:
					logger.warning("Fehler beim Hierarchietrail "+trail+" beim Pfad "+hierarchie+".  Objekt "+str(obj)+" hat nur "+str(len(struk[0]['hierarchy'][obj]))+" Elemente so dass "+str(obj)+"["+p+"] ins Leere geht.")
				else:
					logger.error("Hierarchiefehler: "+hierarchie+" (bislang "+trail+") deutet auf "+str(obj)+", welches nicht in der Hierarchie enthalten ist.")
				break
		return obj
	