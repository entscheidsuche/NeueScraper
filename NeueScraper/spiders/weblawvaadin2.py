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
        "COOKIES_DEBUG":   True
    }

	TREFFERLISTE_URL='/le/UIDL/?v-uiId=0'
	TREFFERLISTE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","resize",["793","1429","1429","793"]],["'
	TREFFERLISTE_p2=b'","com.vaadin.shared.ui.button.ButtonServerRpc","click",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"10", "clientX":"728", "relativeY":"17", "clientY":"47", "button":"LEFT", "type":"1"}]]]'
	NEXTPAGE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","scroll",["535","0"]],["'
	NEXTPAGE_p2=b'","com.vaadin.shared.ui.orderedlayout.AbstractOrderedLayoutServerRpc","layoutClick",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"66", "clientX":"284", "relativeY":"13", "clientY":"716", "button":"LEFT", "type":"8"},null]]]'
		
	reNum=re.compile(r' href="[^"]+">(?P<Num>[^<]+)</a>')
	reTreffer=re.compile(r'Resultat\s+(?P<von>\d+)-(?P<bis>\d+)\s+von\s+(?P<gesamt>\d+)')
	reKlammer=re.compile(r"^(?:<a[^>]+>)?\s*(?P<vor>[^\s(<][^(<]*[^\s(<])\s*(?:\((?P<in>[^)]+)\)\s*)?(?:</a>)?$")
	
	def generate_request(self):
		self.userID="_" + uuid.uuid4().hex[:8]
		self.SUCHFORM['userID']=self.userID
		request=scrapy.Request(url=self.HOST+"/dashboard", callback=self.parse_suchform, errback=self.errback_httpbin)
		return request
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.generate_request()]

	def parse_suchform(self, response):
		#Nur für Cookie holen:
		logger.info("parse_suchform response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_suchform Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_suchform Rohergebnis: "+antwort[:30000])
		request=scrapy.Request(url=self.HOST+"/searchQueryService", headers=self.HEADER, body=json.dumps(self.SUCHFORM), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin)
		yield request
		

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort)
		
		struk=json.loads(antwort)
		# Statt über die Hierarchie könnte man auch über types gehen alle Einträge haben type 1
		treffer=struk.totalNumberOfDocuments
		docs=struk['documents']
		logger.info(str(len(docs))+" Dokumente gefunden")
		for i in docs:
			meta1=i['metadataKeywordTextMap']
			meta2=i['metadataDateMap']
			item={}
			text=json.dumps(i)
			item['PDFUrls']=PH.NC([meta1['originalUrl']],error="keine PDF-URL in "+text)
			item['Num']=PH.NC(meta1['title'].split(" ",1)[1],error="keine Num in "+text)
			item['VGericht']=PH.NC(meta1['argvpBehoerde'],error="kein Gericht in "+text)
			item['EDat']=PH.NC(self.norm_datum(meta2['decisionDate'][:10]),warning="kein Entscheiddatum in "+text)
			item['PDat']=PH.NC(self.norm_datum(meta2['publicationDate'][:10]),warning="kein Publikationsdatum in "+text)
			item['Abstract']=PH.NC(i['content'],warning="kein Abstract in "+text)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
			yield item
		if struk['hasMoreResults']==True:
			if "from" in self.SUCHFORM:
				self.SUCHFORM['from']=self.SUCHFORM['from']+10
				logger.info("mehr Treffer, lade zweite Seite")
			else:
				self.SUCHFORM['from']=10
				logger.info("mehr Treffer, ab Treffer "+str(self.SUCHFORM['from'])+" von "+str(treffer))
			request=scrapy.Request(url=self.HOST+"/searchQueryService", body=json.dumps(self.SUCHFORM), headers=self.HEADER, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin)
			yield request
		else:
			logger.info("Fertig")

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
	