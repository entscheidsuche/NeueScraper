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


class UR_Gerichte(BasisSpider):
	name = 'UR_Gerichte'

	SUCH_URL='/rechtsprechung'
	HOST ="https://www.ur.ch"

	reURL=re.compile(r'^<a href="(?P<URL>[^"]+)">(?P<Num>\s*\d+/\d+ \d+)\s+(?P<Titel>[^\s(<][^(<]*[^<])?(?:</a>)?$')
	
	def get_next_request(self):
		request=scrapy.Request(url=self.HOST+self.SUCH_URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		return request
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])

		daten=response.xpath("//table[@class='table icms-dt rs_preserve']/@data-entities").get()
		if daten is None:
			logger.error("Liste der Urteile nicht gefunden in: "+antwort)
		else:
			strukt=json.loads(daten)
			for entscheid in strukt['data']:
				item={}
				item['EDatum']=entscheid['datum-sort']
				meta=entscheid['name']
				metamatch=self.reURL.search(meta)
				if metamatch:
					url=self.HOST+metamatch['URL']
					item['Num']=metamatch['Num']
					item['Titel']=metamatch['Titel']
					if entscheid['herausgeber']:
						item['Titel']+=" ("+entscheid['herausgeber']+")"
					request=scrapy.Request(url=url,callback=self.parse_details, errback=self.errback_httpbin, meta={'item': item})
					yield request
					
	def parse_details(self, response):
		logger.debug("parse_details response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_details Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_details Rohergebnis: "+antwort[:30000])

		item=response.meta['item']
		item['Abstract']=PH.NC(response.xpath("//div[@class='content-outer']//div[@class='icms-wysiwyg']/text()").get(),warning="keinen Abstract gefunden für "+item['Num']+" in "+antwort)
		pdf=PH.NC(response.xpath("//a[@class='icms-btn icms-btn-primary icms-btn-block']/@href").get(),warning="keine URL für ein PDF gefunden, wird ignoriert: "+antwort)
		if pdf:
			item['PDFUrls']=[self.HOST+pdf]
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			yield item

			