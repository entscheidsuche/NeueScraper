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


class AG_Weitere(BasisSpider):
	name = 'AG_Weitere'

	HOST='https://www.ag.ch'
	URLS=['/de/verwaltung/dvi/grundbuch-vermessung/grundbuch/rechtliche-grundlagen/entscheide']
	
	reMeta=re.compile(r"(?P<Typ>[^ ]+) de(?:s|r)\s+(?P<Gericht>.+)\s+vom\s+(?P<Datum>\d+\.\s+(?:"+"|".join(BasisSpider.MONATEde)+")\s+\d\d\d\d)")
	reMetaTable=re.compile(r"(?P<Titel>^[^\(]+)\s+\((?P<K1>[^\(]+)\)\s+\((?P<K2>[^\(]+)\)")
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = self.generate_request()

	def generate_request(self):
		return [scrapy.Request(url=self.HOST+u, callback=self.parse_page, errback=self.errback_httpbin, meta={'pfad':""}) for u in self.URLS]

	# Unklar ob es sich um eine Menüseite oder eine Trefferliste handelt
	def parse_page(self, response):
		logger.info("parse_page response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_page Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+antwort[:40000])
		
		pfad=response.meta['pfad']
		entscheidtabelle=response.xpath("//table[@summary and @class='table js-table-sortable js-table-filterable table--filterable']")
		if entscheidtabelle:
			rechtsgebiet=PH.NC(entscheidtabelle.xpath("./@summary").get(),error="Kein Summary in Entscheidtabelle gefunden")
			entscheide=entscheidtabelle.xpath("//tbody/tr")
			logger.info(str(len(entscheide))+" Entscheide gefunden.")
			if not entscheide:
				logger.warning("Keine Entscheide im Bereich: "+titel)
			else:
				logger.info(str(len(entscheide))+" Entscheide gefunden.")
				for e in entscheide:
					itext=e.get()
					logger.info("Verarbeite Entscheid "+itext)
					item={}
					item['PDFUrls']=[self.HOST+PH.NC(e.xpath(".//a[@class='link ']/@href").get(),error="Url für PDF des Entscheids nicht gefunden in "+itext)]
					item['EDatum']=PH.NC(self.norm_datum(e.xpath(".//td[@data-table-columntitle='Datum']/text()").get()))
					meta=PH.NC(e.xpath(".//a[@class='link ']//span[@class='link__text']/text()").get())
					metas=self.reMeta.search(meta)
					if metas:
						item['Entscheidart']=metas.group('Typ')
						item['VGericht']=metas.group('Gericht').replace('\ufeff','')
						#item['EDatum']=self.norm_datum(metas.group('Datum'))
					else:
						item['VGericht']=""
					klammern=self.reMetaTable.search(meta)
					if klammern:
						item['Num']=klammern.group('K1')	
						item['Titel']=klammern.group('Titel')
					else:
						item['Num']=""
						item['Titel']=meta
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], "", item['Num'])

					yield item
		else:
			logger.error("keine Entscheidtabelle gefunden")
