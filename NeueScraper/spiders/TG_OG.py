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


class TG_OG(BasisSpider):
	name = 'TG_OG'
	
	SUCH_URL='/search/result.cfm?hilfe='
	HOST ="http://ogbuch.tg.ch"
	
	reMeta=re.compile(r'(?:Obergericht|Rekurskommission|Obergerichtspräsidium),\s(?:(?P<VKammer>.+),\s)?(?P<Datum>\d+\.\s(?:'+"|".join(BasisSpider.MONATEde)+r')\s+(?:19|20)\d\d),\s+(?P<Num2>[A-Z]{1,3}(?:\s+\d\d\s+\d+|\.(?:19|20)\d\d\.\d+))')
	reSpaces=re.compile(r'\s+')
	
	def get_next_request(self):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, callback=self.parse_trefferliste, errback=self.errback_httpbin)
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

		entscheide=response.xpath("//table[@border='0' and @width='100%']/tr/td/table[@border='0' and @width='100%']/tr[//a]")
		logger.info("Anzahl der gefundenen Entscheide: "+str(len(entscheide)))

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.debug("Eintrag: "+text)
			item['Num']=PH.NC(entscheid.xpath("./td/a/b[@class='Titel']/text()").get(),error="keine Geschäftsnummer gefunden "+text)
			url=PH.NC(entscheid.xpath("./td/a/@href").get(),error="keine URL für das Dokument gefunden "+text)
			if url[:2]=="..":
				url=self.HOST+url[2:]
			else:
				url=self.HOST+url
			item["HTMLUrls"]=[url]
			item['Leitsatz']=PH.NC(entscheid.xpath("./td/font[@class='legenden']/text()").get().strip(),info="keinen Leitsatz gefunden in "+text)
			logger.info("Entscheid bislang: "+json.dumps(item))
			request=scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			yield request
			
	def parse_document(self, response):
		logger.debug("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:30000])
		
		item=response.meta['item']
		
		vkammer=""
		metas=response.xpath("((//p/descendant-or-self::*)|(//td/div/span))[starts-with(.,'Obergericht') or starts-with(.,'Rekurskommission') or starts-with(.,'Obergerichtspräsidium')]/text()").getall()
		if len(metas)==0:
			logger.warning("Meta nicht gefunden "+item['Num']+" "+response.url)
			# EDatum notfalls aus der Jahreszahl erstellen.
			item['EDatum']=self.norm_datum(item['Num'])
			
		else:
			meta=metas[-1]
			matchmeta=self.reMeta.search(meta)
			if matchmeta:
				item['Num2']=self.reSpaces.sub(" ",matchmeta.group('Num2'))
				item['EDatum']=self.norm_datum(matchmeta.group('Datum'))
				if matchmeta.group('VKammer'):
					item['VKammer']=matchmeta.group('VKammer')
					vkammer=item['VKammer']
			else:
				logger.warning("Detaillierte Metainformationen nicht erkannt in "+item['Num']+": "+meta)
				# EDatum notfalls aus der Jahreszahl erstellen.
				item['EDatum']=self.norm_datum(meta+" "+item['Num'])
		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",vkammer,item['Num'])
		PH.write_html(antwort, item, self)
		yield item

	
			
