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


class AI_Bericht(BasisSpider):
	name = 'AI_Bericht'

	URL='https://www.ai.ch/themen/staat-und-recht/veroeffentlichungen/verwaltungs-und-gerichtsentscheide'
	reJahr=re.compile(r'(?:19|20)\d\d$')
	
	def request_generator(self):
		request = scrapy.Request(url=self.URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		return [request]
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = self.request_generator()


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
	
		berichte=response.xpath("//table[@class='listing nosort']/tbody/tr/td[@class='column-sortable_title']/span/a")
		
		logger.info("Gefunden: {} Dokumente".format(len(berichte)))

		for entscheid in berichte:
			item={}
			logger.info("Verarbeite nun: "+entscheid.get())
			pdfurl=entscheid.xpath("./@href").get()
			# Hier erfolgt ein Redirect, den bei PDFs Scrapy nicht automatisch nachverfolgt.
			item['PDFUrls']=[pdfurl[:-len(pdfurl.split("/")[-1])-1]+"/@@download/file/"+pdfurl.split("/")[-2]]

			item['VGericht']=self.stufe2
			item['Num']=entscheid.xpath("./text()").get()
			pdatum=self.reJahr.search(item['Num'])
			if pdatum:
				item['PDatum']=pdatum.group(0)
			else:
				logger.warning("Für {} kein Datum gefunden.".format(entscheid.get()))
				item['PDatum']='2020'
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect("","",item['Num'])
			logger.info("Bislang gefunden: "+json.dumps(item))
			yield item
