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


class NW_Gerichte(BasisSpider):
	name = 'NW_Gerichte'

	SUCH_URL='/rechtsprechung'
	HOST ="https://www.nw.ch"

	reURL=re.compile(r'<a (?:.+\s+)*href="(?P<URL>[^"]+)"')
	
	def get_next_request(self):
		request=scrapy.Request(url=self.HOST+self.SUCH_URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		return request
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])

		daten=response.xpath("//table[@class='table icms-dt rs_preserve']/@data-entities").get()
		if daten is None:
			logger.error("Liste der Urteile nicht gefunden in: "+antwort)
		else:
			strukt=json.loads(daten)
			for entscheid in strukt['data']:
				logger.infor("Bearbeite Entscheid: "+json.dumps(entscheid))
				item={}
				item['EDatum']=self.norm_datum(entscheid['datum-sort'])
				item['Titel']=entscheid['name']
				pdf=self.HOST+entscheid['_downloadBtn']
				pdf_match=self.reURL.search(pdf)
				if pdf_match:
					item['PDFUrls']=[self.HOST+pdf_match.group('URL')]
					item['Num']=pdf_match.group('URL').split("/")[-1]
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
					logger.info("Entscheid: "+json.dumps(item))
					yield item
				else:
					logger.error("keine URL gefunden in: "+json.dumps(entscheid))
