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
	
	VERZEICHNIS_URL={'Obergericht': '/og/entscheide','Verwaltungsgericht':'/vg/entscheide'}
	HOST ="http://rechtsprechung.tg.ch"
	
	reMetaOG=re.compile(r'(?:Obergericht|Rekurskommission|Obergerichtspräsidium),\s(?:(?P<VKammer>.+),\s)?(?P<Datum>\d+\.\s(?:'+"|".join(BasisSpider.MONATEde)+r')\s+(?:19|20)\d\d),\s+(?P<Num>[A-Z]{1,3}(?:\s+\d\d\s+\d+|\.(?:19|20)\d\d\.\d+))')
	reMetaVG=re.compile(r'Urteil vom (?P<Datum>\d+\.\s(?:'+"|".join(BasisSpider.MONATEde)+r')\s+(?:19|20)\d\d)\s+\((?P<Num>[1-9]+[A-Z]{1,3}\.\d+/(?:19|20)\d\d\.\d+)\)')
	reSpaces=re.compile(r'\s+')
	
	def get_requests(self):
		requests=[]
		for i in self.VERZEICHNIS_URL:
			requests.append(scrapy.FormRequest(url=self.HOST+self.VERZEICHNIS_URL[i], callback=self.parse_jahresliste, errback=self.errback_httpbin, meta={'Gericht': i}))
		return requests
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = self.get_requests()

	def parse_jahresliste(self, response):
		logger.info("parse_jahresliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		jahre=response.xpath('//span[@class="vp-accordion-link-group__title-inner"]/a/@href')
		logger.info("Für "+response.meta['Gericht']+": "+str(len(jahre))+" Jahre gefunden.")
		for jahr in jahre:
			jahresstring=jahr.get()
			if jahresstring[0:2]=="..":
				jahr=self.HOST+jahresstring[2:]
				request=scrapy.Request(url=jahr, callback=self.parse_trefferliste,errback=self.errback_httpbin, meta=response.meta)
				yield request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" für "+response.request.url)
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])

		entscheide=response.xpath("//div[@class='vp-content-by-label-items']/ul/li[a]")
		logger.info("Anzahl der gefundenen Entscheide: "+str(len(entscheide)))

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.debug("Eintrag: "+text)
			item['Num']=PH.NC(entscheid.xpath("./a/text()").get(),error="keine Geschäftsnummer gefunden "+text)
			url=PH.NC(entscheid.xpath("./a/@href").get(),error="keine URL für das Dokument gefunden "+text)
			if url[:2]=="..":
				url=self.HOST+url[2:]
				
			item["HTMLUrls"]=[url]
			item['Leitsatz']=PH.NC(entscheid.xpath("./p/text()").get().strip(),info="keinen Leitsatz gefunden in "+text)
			item['VGericht']=response.meta['Gericht']
			logger.info("Entscheid bislang: "+json.dumps(item))
			request=scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			yield request
			
	def parse_document(self, response):
		logger.debug("parse_document response.status "+str(response.status)+" für "+response.request.url)
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:30000])
		
		item=response.meta['item']
		
		vkammer=""
		metas=response.xpath("//section[@id='main-content']/p[last()]/text()")
		if not metas:
			logger.warning("Meta nicht gefunden "+item['Num']+" "+response.url)
			# EDatum notfalls aus der Jahreszahl erstellen.
			item['EDatum']=self.norm_datum(item['Num'])
			
		else:
			meta=metas.get()
			if item['VGericht']=="Obergericht":
				matchmeta=self.reMetaOG.search(meta)
			else:
				matchmeta=self.reMetaVG.search(meta)
			if matchmeta:
				item['Num2']=self.reSpaces.sub(" ",matchmeta.group('Num'))
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

	
			
