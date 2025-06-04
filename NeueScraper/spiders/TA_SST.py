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


class TA_SST(BasisSpider):
	name = 'TA_SST'

	URL="/rechsprechung"
	HOST="https://www.sportstribunal.ch"
	
	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Upgrade-Insecure-Requests': '1',
		'Sec-Fetch-Dest': 'document',
		'Sec-Fetch-Mode': 'navigate',
		'Sec-Fetch-Site': 'none',
		'Sec-Fetch-User': '?1',
		'Pragma': 'no-cache',
		'Cache-Control': 'no-cache'
	}
	
	reMeta=re.compile(r'(?P<az>[A-Z]+ 20[0-9][0-9][^ ]+) - [^0-9]+(?P<datum>.+)')

	
	def request_generator(self):
		requests=[scrapy.Request(url=self.HOST+self.URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)]			
		return requests
	
	def __init__(self, ab=None, neu=None):
		self.ab=ab
		self.neu=neu
		super().__init__()
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" für URL "+response.url)
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])

		urteile=response.xpath("//a[@class='file pdf' and following::h2[normalize-space(.)='Richtlinien zur Anonymisierung']]")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden.")
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./@href").get()
				
				metastring=entscheid.xpath("string(.)").get()
				meta=self.reMeta.search(metastring)

				logger.info("Gefunden: "+url+" mit "+metastring)
				logger.info("AZ: "+meta.group('az')+", Datum: "+meta.group('datum'))
				item['PDFUrls']=[url]
				item['Num']=meta.group('az')
				item['EDatum']=PH.NC(self.norm_datum(meta.group("datum")),error="Datum nicht parsable: "+meta.group("datum"))
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				yield(item)
				
