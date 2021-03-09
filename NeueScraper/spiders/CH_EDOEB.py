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

	URLs=["/edoeb/de/home/datenschutz/dokumentation/empfehlungen.html", "/edoeb/de/home/datenschutz/dokumentation/empfehlungen/aeltere-empfehlungen/empfehlungen-von-2004-2009.html", "/edoeb/de/home/datenschutz/dokumentation/empfehlungen/aeltere-empfehlungen/empfehlungen-von-1993-2003.html"]
	HOST="https://www.edoeb.admin.ch"
	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+url,callback=self.parse_trefferliste, errback=self.errback_httpbin) for url in self.URLs]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		urteile=response.xpath("//div[@class='mod mod-download']/p")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['Gericht'])
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./a/@href").get()
				meta=entscheid.xpath("./a/@title").get()
				metas=meta.split(" - ",1)
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
