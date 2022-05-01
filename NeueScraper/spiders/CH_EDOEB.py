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


class CH_EDOEB(BasisSpider):
	name = 'CH_EDOEB'

	URLs=["/edoeb/de/home/oeffentlichkeitsprinzip.html", "/edoeb/fr/home/principe-de-la-transparence.html", "/edoeb/it/home/principio-di-trasparenza.html",  "/edoeb/de/home/oeffentlichkeitsprinzip/empfehlungen/aeltere-empfehlungen/empfehlungen-2013.html", "/edoeb/fr/home/principe-de-la-transparence/empfehlungen/aeltere-empfehlungen/recommandations-2013.html", "/edoeb/it/home/principe-de-la-transparence/empfehlungen/aeltere-empfehlungen/recommandations-2013.html"]
	HOST="https://www.edoeb.admin.ch"
	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+url,callback=self.parse_contentliste, errback=self.errback_httpbin) for url in self.URLs]

	def parse_contentliste(self, response):
		logger.info("parse_contentliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_contentliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_contentliste Rohergebnis: "+antwort[:80000])
		listen=response.xpath("//div[h3/a[@title='Empfehlungen' or @title='Recommandations' or @title='Raccomandazioni']]/ul/li/a/@href")	
		if len(listen)==0:
			listen=response.xpath("//ul[li/@class='list-emphasis']/li/a[contains(.,'20')]/@href")
		if len(listen)==0:
			logger.warning("Keine Entscheidlisten gefunden in "+ response.url	)
		else:
			for url in listen:
				request=scrapy.Request(url=self.HOST+url.get(), callback=self.parse_trefferliste, errback=self.errback_httpbin)
				yield request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		urteile=response.xpath("//div[@class='mod mod-download']/p")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.url")
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./a/@href").get()
				meta=entscheid.xpath("./a/@title").get()
				metas=meta.split(": ",1)
				item['PDFUrls']=[self.HOST+url]
				edatum=self.norm_datum(metas[0], warning="Kein Datum identifiziert")
				if edatum!="nodate":
					item['EDatum']=edatum
				if len(metas)>1:
					item['Titel']=metas[1]
					item['Num']=metas[1]
				else:
					item['Num']='unbekannt'
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				yield item
