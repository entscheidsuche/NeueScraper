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

	SUCH_URL='/rechtsprechung?search_publikation_filter[searchText]='
	HOST ="https://www.ur.ch"

	reURL=re.compile(r'^<a (?:[a-z]+="[^"]+"\s+)*href="(?P<URL>[^"]+)"(?:\s+[a-z]+="[^"]+")*>(?:<span class="sr-only">)?(?P<Num>\d+(?:_[A-Z]+|/\d+)\s+(?:[A-Z]+\s+)?(?:\d+\s+)?[^\.;]*)(?:\.|;)?\s+(?P<Titel>[^<]+)?(?:</span>Download)?(?:</a>)?$')
	reOhneURL=re.compile(r'^(?P<Num>\d+(?:_[A-Z]+|/\d+)\s+(?:[A-Z]+\s+)?(?:\d+\s+)?[^\.;]*)(?:\.|;)?\s+(?P<Titel>.+)$')
	reNurURL=re.compile(r'^<a href="(?P<URL>[^"]+)"')
	
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
			logger.info("Liste der Urteile gefunden.")
			strukt=json.loads(daten)['data']
			logger.debug(str(len(strukt))+" Entscheide gefunden in: "+daten)
			logger.info(str(len(strukt))+" Entscheide gefunden")
			for entscheid in strukt:
				item={}
				item['EDatum']=PH.NC(self.norm_datum(entscheid['datum-sort']), error="kein EDATUM")
				meta=entscheid['name']
				if "_downloadBtn" in entscheid and entscheid['_downloadBtn']:
					linkstring=entscheid['_downloadBtn']
					logger.info("Entscheid "+meta+" mit Linkstring: "+linkstring)
					linkmatch=self.reURL.search(linkstring)
					if linkmatch:
						url=linkmatch['URL']
						metamatch=linkmatch
					else:
						linkmatch=self.reNurURL.search(linkstring)
						if linkmatch:
							url=linkmatch['URL']
						else:
							logger.error("URL nicht erkannt in: "+linkstring)
						metamatch=self.reOhneURL.search(meta)
						if not(metamatch):
							logger.error("kein Metamatch bei vorhandenem Linkstring für "+meta+" ("+meta.encode('utf-8').hex()+")")
				else:
					logger.info("Entscheid "+meta+" ohne Linkstring")
					metamatch=self.reURL.search(meta)
					if metamatch:
						url=metamatch['URL']
					else:
						logger.error("Entscheid "+meta+" weder mit linkstring noch passendem Pattern.")
				if metamatch:
					item['Num']=metamatch['Num']
					item['Titel']=metamatch['Titel']
					if entscheid['herausgeber']:
						item['Titel']+=" ("+entscheid['herausgeber']+")"
					url=url.strip()
#					if url[-4:].lower()=='.pdf':
					item['PDFUrls']=[self.HOST+url]
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
					logger.info("PDF-Entscheid direkt: "+json.dumps(item))
					logger.info("Hole nun URL als PDF: "+self.HOST+url)
					yield item
#					else:
#						logger.info("Hole nun URL als HTML: "+self.HOST+url)
#						request=scrapy.Request(url=self.HOST+url,callback=self.parse_details, errback=self.errback_httpbin, meta={'item': item})
#						yield request
				else:
					logger.error("kein Metamatch für "+meta)
				
					
	def parse_details(self, response):
		logger.info("parse_details response.status "+str(response.status))
		contenttype=response.headers['Content-Type'].decode("ascii")
		logger.info("parse_detail Content-Type: "+contenttype)
		item=response.meta['item']
		if contenttype=="application/pdf":
			item['PDFUrls']=[response.url]
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
			logger.info("PDF-Entscheid als redirect: "+json.dumps(item))
			logger.info("Hole nun URL als PDF: "+response.url)
			yield item
			
		else:
			antwort=response.text
			logger.info("parse_details Rohergebnis "+str(len(antwort))+" Zeichen")
			logger.debug("parse_details Rohergebnis: "+antwort[:30000])

			item['Abstract']=PH.NC(response.xpath("//div[@class='content-outer']//div[@class='icms-wysiwyg']/text()").get(),warning="keinen Abstract gefunden für "+item['Num']+" in "+antwort)
			pdf=PH.NC(response.xpath("//a[@class='icms-btn icms-btn-primary icms-btn-block']/@href").get(),warning="keine URL für ein PDF gefunden, wird ignoriert: "+antwort)
			if pdf:
				item['PDFUrls']=[self.HOST+pdf]
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				logger.info("Entscheid: "+json.dumps(item))
				yield item


