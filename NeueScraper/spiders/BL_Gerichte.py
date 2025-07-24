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
		"Kantonsgericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/kantonsgericht_rs/chronologische-anordnung", "direkt": False},
		"Steuergericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/steuergericht", "direkt": False},
		"Enteignungsgericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/enteignungsgericht/entscheide-chronologisch", "direkt": True},
		"Zwangsmassnahmengericht": { "url": "/politik-und-behorden/gerichte/rechtsprechung/zwangsmassnahmengericht", "direkt": False}}
	HOST="https://www.baselland.ch"
	PROXY="http://v2202109132150164038.luckysrv.de:8181/"
	
	reJahre=re.compile(r'<a\s[^>]*href="(?P<URL>[^"]+)"[^>]*>\s*(?P<Jahr>(?:20|19)\d\d)\s*</a>')
	
	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/119.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Upgrade-Insecure-Requests': '1',
		'Sec-Fetch-Dest': 'document',
		'Sec-Fetch-Mode': 'navigate',
		'Sec-Fetch-Site': 'none',
		'Sec-Fetch-User': '?1',
		'Pragma': 'no-cache',
		'Cache-Control': 'no-cache'
	}
	
	def request_generator(self):
		requests=[]
		for r in self.URLs:
			if self.URLs[r]['direkt']:
				request = scrapy.Request(url=self.PROXY+self.HOST+self.URLs[r]['url'], callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': r})			
			else:
				request = scrapy.Request(url=self.PROXY+self.HOST+self.URLs[r]['url'], callback=self.parse_jahresliste, errback=self.errback_httpbin, meta={'Gericht': r})
			requests.append(request)
		return requests
	
	def __init__(self, ab=None, neu=None):
		self.ab=ab
		self.neu=neu
		super().__init__()
		self.request_gen = self.request_generator()

	def parse_jahresliste(self, response):
		logger.info("parse_jahresliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_jahresliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_jahresliste Rohergebnis: "+antwort[:30000])
		jahre=self.reJahre.findall(antwort)
		if len(jahre)==0:
			logger.error("Keine Entscheidjahre gefunden für "+response.meta['Gericht'])
		else:
			logger.info(str(len(jahre))+" Jahrgänge gefunden für "+response.meta['Gericht'])
		for j in self.reJahre.finditer(antwort):
			if self.ab is None or int(j.group('Jahr'))>=int(self.ab):
				logger.info("Hole Jahr "+j.group('Jahr')+" für "+response.meta['Gericht']+" mit URL:"+j.group('URL'))
				request = scrapy.Request(url=self.PROXY+j.group('URL'), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht']})
				yield request			

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" für URL "+response.url)
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		#Teilweise sind die Jahre nochmal aufgeteilt
		if not "Teiljahr" in response.meta:
			andere_monate=response.xpath(".//a[contains(translate(.,'\xa0',' '),' bis ')]/@href")
			for l in andere_monate:
				logger.info("Andere Monate-URL: "+l.get())
				request = scrapy.Request(url=self.PROXY+l.get(), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht'], 'Teiljahr': True})
				yield request
		urteile=response.xpath("//table/tbody/tr[td[1]//a]")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['Gericht']+" URL: "+response.url)
		else:
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
					if url[-4:]=='.pdf' or 'downloads' in url:
						item['Num']=url[:-4].split("/")[-1]
						if len(item['Num'])<6:
							item['Num']=url[:-4].split("/")[-2]+"/"+item['Num']
						item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'],"",item['Num'])
						if "/downloads/" in url:
							url+="/@@download/file/"+url.split("/downloads/")[-1]
						else:
							url+="/@@download/file/"+url.split("/")[-1]
							
						item['PDFUrls']=[self.PROXY+url]
							
						if self.check_blockliste(item):
							logger.info("PDF-Item: "+json.dumps(item))
							yield item
					else:
						item['HTMLUrls']=[self.PROXY+url]
						item['Num']=url.split("/")[-1]
						if len(item['Num'])<6:
							item['Num']=url.split("/")[-2]+"/"+item['Num']
						item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'],"",item['Num'])
						if self.check_blockliste(item):
							request = scrapy.Request(url=self.PROXY+url, callback=self.parse_document, errback=self.errback_httpbin, meta={'Gericht': response.meta['Gericht'], 'item': item})
							logger.info("HTML-Item bis jetzt: "+json.dumps(item))
							yield request
				else:
					logger.warning("falscher Link: "+url+". Urteil wird ignoriert.")	

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='content-content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
