# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
import random
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class AR_Gerichte(BasisSpider):
	name = 'AR_Gerichte'
	
	custom_settings = {
        'COOKIES_ENABLED': True
    }

	SUCHFORM='/le/?v-browserDetails=1&theme=le3themeAR&v-sh=900&v-sw=1440&v-cw=1439&v-ch=793&v-curdate=1609113076640&v-tzo=-60&v-dstd=60&v-rtzo=-60&v-dston=false&v-vw=1439&v-vh=0&v-loc=https://rechtsprechung.ar.ch/le/&v-wn=le-3449-0.{}&v-1609113076640='
	TREFFERLISTE_URL='/le/UIDL/?v-uiId=0'
	TREFFERLISTE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","resize",["793","1429","1429","793"]],["'
	TREFFERLISTE_p2=b'","com.vaadin.shared.ui.button.ButtonServerRpc","click",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"10", "clientX":"728", "relativeY":"17", "clientY":"47", "button":"LEFT", "type":"1"}]]]'
	NEXTPAGE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","scroll",["535","0"]],["'
	NEXTPAGE_p2=b'","com.vaadin.shared.ui.orderedlayout.AbstractOrderedLayoutServerRpc","layoutClick",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"66", "clientX":"284", "relativeY":"13", "clientY":"716", "button":"LEFT", "type":"8"},null]]]'
	HOST ="https://rechtsprechung.ar.ch"
	HEADER = {
		"Content-Type": "text/plain;charset=utf-8",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0",
		"Referer": "https://rechtsprechung.ar.ch/le/",
		"Origin": "https://rechtsprechung.ar.ch"}
		
	reNum=re.compile(r' href="[^"]+">(?P<Num>[^<]+)</a>')
	reTreffer=re.compile(r'Resultat\s+(?P<von>\d+)-(?P<bis>\d+)\s+von\s+(?P<gesamt>\d+)')
	
	def generate_request(self):
		request=scrapy.Request(url=self.HOST+self.SUCHFORM.format(str(random.randint(1000000000000000,9999999999999999))), method="POST", callback=self.parse_suchform, errback=self.errback_httpbin)
		return request
	
	def __init__(self, ab=None):
		super().__init__()
		self.request_gen = [self.generate_request()]

	def parse_suchform(self, response):
		logger.info("parse_suchform response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_suchform Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_suchform Rohergebnis: "+antwort[:30000])
		struktur=json.loads(antwort)
		antwort_uidl=struktur['uidl']
		struktur_uidl=json.loads(antwort_uidl)
		logger.debug("uidl: "+json.dumps(struktur_uidl))
		self.vaadin_key=struktur_uidl["Vaadin-Security-Key"]
		logger.info("Vaadin-Key: "+self.vaadin_key)
		state=struktur_uidl["state"]
		logger.debug("state: "+json.dumps(state))
		self.searchbutton=[i for i in state if "clickShortcutKeyCode" in state[i]][0]
		logger.info("searchbutton: "+str(self.searchbutton))
		self.contentid=[i for i in state if 'spacing' in state[i] and state[i]['spacing']==True and 'width' in state[i] and state[i]['width']=="100.0%"][0]
		logger.info("contentid: "+str(self.contentid))
		request=scrapy.Request(url=self.HOST+self.TREFFERLISTE_URL, headers=self.HEADER , method="POST", body=self.vaadin_key.encode('utf-8')+self.TREFFERLISTE_p1+str(self.searchbutton).encode("utf-8")+self.TREFFERLISTE_p2, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		logger.info(b"Request: "+request.body)
		yield request
		

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort)
		
		struk=json.loads(antwort[8:])
		# Statt über die Hierarchie könnte man auch über types gehen alle Einträge haben type 1
		members=struk[0]['hierarchy'][str(self.contentid)]
		treffer=struk[0]['state'][struk[0]['hierarchy'][members[-1]][-2]]['text']
		logger.info("Treffer: "+treffer)
		tm=self.reTreffer.search(treffer)
		if tm is None:
			logger.error("Treffer nicht erkannt: "+treffer)
		else:
			vonTreffer=tm.group("von")
			bisTreffer=tm.group("bis")
			gesamtTreffer=tm.group("gesamt")
			for entscheid in range(1,len(members)-1):
				item={}
				teile=struk[0]['hierarchy'][members[entscheid]]
				logger.info("teile: "+json.dumps(teile))
				textid=struk[0]['hierarchy'][teile[0]][0]
				logger.info("textid: "+textid)
				text=struk[0]['state'][textid]['text']
				logger.info("text: "+text)
				item['Formal_org']=text
				pdatum=struk[0]['state'][struk[0]['hierarchy'][struk[0]['hierarchy'][struk[0]['hierarchy'][teile[2]][0]][0]][1]]['text']
				logger.info("pdatum: "+pdatum)
				edatum=struk[0]['state'][struk[0]['hierarchy'][struk[0]['hierarchy'][struk[0]['hierarchy'][teile[2]][2]][0]][1]]['text']
				logger.info("edatum: "+edatum)
				if self.reDatum.search(edatum):
					item['EDatum']=self.norm_datum(edatum)
				if self.reDatum.search(pdatum):
					item['P	Datum']=self.norm_datum(pdatum)
				link=struk[0]['state'][teile[1]]['text']
				logger.info("link: "+link)
				num=self.reNum.search(link)
				if num:
					item['Num']=num.group('Num')
					pdfid=struk[0]['hierarchy'][struk[0]['hierarchy'][teile[3]][1]][0]
					logger.info("pdfid: "+pdfid)
					pdf=struk[0]['state'][pdfid]['resources']['href']['uRL']
					logger.info("pdf: "+pdf)
					item['PDFUrls']=[self.HOST+pdf]
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(text,item['Num'],item['Num'])
					yield item
				else:
					logger.error("Keine Geschäftsnummer gefunden in: "+link)
			if int(bisTreffer)<int(gesamtTreffer):
				weiterkey=struk[0]['hierarchy'][members[-1]][0]
				request=scrapy.Request(url=self.HOST+self.TREFFERLISTE_URL, headers=self.HEADER , method="POST", body=self.vaadin_key.encode('utf-8')+self.NEXTPAGE_p1+weiterkey.encode("utf-8")+self.NEXTPAGE_p2, callback=self.parse_trefferliste, errback=self.errback_httpbin)
				logger.info("Hole jetzt die Treffer nach "+bisTreffer)
				logger.info(request.body)
				yield request
			else:
				logger.info("Fertig nach "+gesamtTreffer)
		
			
			
			
			
		
		
		
		
