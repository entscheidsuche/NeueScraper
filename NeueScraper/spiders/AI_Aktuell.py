# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class AI_Aktuell(BasisSpider):
	name = 'AI_Aktuell'

	URL='https://www.ai.ch/gerichte/rechtsprechung'

	def request_generator(self):
		request = scrapy.Request(url=self.URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		return [request]
	
	def __init__(self, neu=None):
		super().__init__()
		# Hier stehen immer nur die neuen Entscheide. Daher nie gesamt holen und austauschen.
		self.ab="gesetzt"
		self.request_gen = self.request_generator()


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
	
		kantonsgericht=response.xpath("//table[@summary='Kantonsgericht']/tbody/tr[td/a]")
		bezirksgericht=response.xpath("//table[@summary='Bezirksgericht']/tbody/tr[td/a]")
		
		logger.info("Gefunden: Kantonsgericht {} Entscheide und Bezirksgericht {} Entscheide".format(len(kantonsgericht),len(bezirksgericht)))
		
		items=self.parse_item(kantonsgericht,"Kantonsgericht")
		items=items+self.parse_item(bezirksgericht,"Bezirksgericht")
			
		for item in items:
			yield item			
			
	
	def parse_item(self, entscheid_xmls, gericht):
		items=[]		
		for entscheid in entscheid_xmls:
			item={}
			logger.info("Verarbeite nun: "+entscheid.get())
			pdfurl=entscheid.xpath("./td/a/@href").get()
			# Hier erfolgt ein Redirect, den bei PDFs Scrapy nicht automatisch nachverfolgt.
			item['PDFUrls']=[pdfurl+"/@@download/file/"+pdfurl.split("/")[-1]]
			item['VGericht']=gericht
			item['Num']=entscheid.xpath("./td/a/descendant-or-self::*/text()").get()
			item['Titel']=entscheid.xpath("./td[2]/text()").get()
			pdatum_roh=entscheid.xpath("./td[3]/text()").get()
			item['PDatum']=self.norm_datum(pdatum_roh)
			logger.info("Bislang gefunden: "+json.dumps(item))
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
			items.append(item)
		return items
