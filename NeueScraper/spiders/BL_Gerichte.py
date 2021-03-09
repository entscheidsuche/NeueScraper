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


class BL_Gerichte(BasisSpider):
	name = 'BL_Gerichte'

	URLs={
		"Kantonsgericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/kantonsgericht/chronologische-anordnung", "direkt": False},
		"Steuergericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/steuergericht", "direkt": False},
		"Enteignungsgericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/enteignungsgericht/entscheide-chronologisch", "direkt": True},
		"Zwangsmassnahmengericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/zwangsmassnahmengericht", "direkt": False}}
	HOST="https://www.baselland.ch"
	
	reJahre=re.compile(r'<a\s[^>]*href="(?P<URL>[^"]+)"[^>]*>\s*(?P<Jahr>(?:20|19)\d\d)\s*</a>')
	
	def request_generator(self):
		requests=[]
		for r in self.URLs:
			if self.URLs[r]['direkt']:
				request = scrapy.Request(url=self.HOST+self.URLs[r]['url'], callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': r})			
			else:
				request = scrapy.Request(url=self.HOST+self.URLs[r]['url'], callback=self.parse_jahresliste, errback=self.errback_httpbin, meta={'Gericht': r})
			requests.append(request)
		return requests
	
	def __init__(self, ab=None, neu=None):
		self.ab=ab
		self.neu=neu
		super().__init__()
		self.request_gen = self.request_generator()

	def parse_jahresliste(self, response):
		logger.info("parse_jahresliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_jahresliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_jahresliste Rohergebnis: "+antwort[:30000])
		jahre=self.reJahre.findall(antwort)
		if len(jahre)==0:
			logger.error("Keine Entscheidjahre gefunden für "+response.meta['Gericht'])
		else:
			logger.info(str(len(jahre))+" Jahrgänge gefunden für "+response.meta['Gericht'])
		for j in self.reJahre.finditer(antwort):
			if self.ab is None or int(j.group('Jahr'))>=int(self.ab):
				request = scrapy.Request(url=j.group('URL'), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht']})
				yield request			

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		urteile=response.xpath("//table[@class='invisible' or @class='plain']/tbody/tr[td[1]//a]")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['Gericht'])
		else:
			#Teilweise sind die Jahre nochmal aufgeteilt
			if not "Teiljahr" in response.meta:
				andere_monate=response.xpath(".//a[contains(text(),' bis ')]/@href")
				for l in andere_monate:
					logger.info("Andere Monate-URL: "+l.get())
					request = scrapy.Request(url=l.get(), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht'], 'Teiljahr': True})
					yield request
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./td//a/@href").get()
				item['VGericht']=response.meta['Gericht']
				edatum=entscheid.xpath("string(./td//a)").get()
				norm=self.norm_datum(edatum, warning="Kein Datum identifiziert")
				if norm!="nodate":
					item['EDatum']=norm
				regeste=entscheid.xpath("string(./td[preceding-sibling::*])").get()
				if regeste:
					item['Leitsatz']=regeste.strip()
				if url[:8]=='https://':
					if url[-4:]=='.pdf':
						item['Num']=url[:-4].split("/")[-1]
						if len(item['Num'])<6:
							item['Num']=url[:-4].split("/")[-2]+"/"+item['Num']
						item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'],"",item['Num'])
						if "/downloads/" in url:
							url+="/@@download/file/"+url.split("/downloads/")[-1]
						else:
							url+="/@@download/file/"+url.split("/")[-1]
							
						item['PDFUrls']=[url]
							
						if self.check_blockliste(item):
							logger.info("PDF-Item: "+json.dumps(item))
							yield item
					else:
						item['HTMLUrls']=[url]
						item['Num']=url.split("/")[-1]
						if len(item['Num'])<6:
							item['Num']=url.split("/")[-2]+"/"+item['Num']
						item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'],"",item['Num'])
						if self.check_blockliste(item):
							request = scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht'], 'item': item})
							logger.info("HTML-Item bis jetzt: "+json.dumps(item))
							yield request
				else:
					logger.warning("falscher Link: "+url+". Urteil wird ignoriert.")	

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='content-content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
