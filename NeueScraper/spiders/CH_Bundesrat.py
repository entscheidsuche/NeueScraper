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


class CH_Bundesrat(BasisSpider):
	name = 'CH_Bundesrat'

	HOST='https://www.bj.admin.ch'
	URL='/bj/de/home/publiservice/publikationen/beschwerdeentscheide.html'

       
	HEADERS = {
		"Accept": "*/*",
		"Accept-Language": "de,en-US;q=0.7,en;q=0.3",
		"Content-Type": "application/json",
		"Origin": "https://www.ag.ch",
		"DNT": "1",
		"User-Agent": (
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) "
			"Gecko/20100101 Firefox/139.0"
		),
    }
	
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = self.generate_request()

	def generate_request(self):
		return [scrapy.Request(url=self.HOST+self.URL, headers=self.HEADERS, callback=self.parse_teaserlistid, errback=self.errback_httpbin)]

	def generate_pagerequests(self, page):
		logger.info("generiere Request für Seite "+str(page)+" und basisurl "+self.listenURL)
		url=self.HOST+self.listenURL.format(page=page)
		logger.info("generierte URL: "+url)
		return scrapy.Request(url=url, callback=self.parse_iste, errback=self.errback_httpbin, meta={page: page})

	def parse_teaserlistid(self, response):
		logger.info("parse_teaserlistid response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_teaserlistid Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_teaserlistid Rohergebnis: "+antwort[:40000])
		
		teaserlistid=response.xpath("//div[@class='mod mod-dynamic' and @data-url and @data-connectors]")
		if teaserlistid:
			listenURL=teaserlistid.xpath("./@data-url").get()
			self.listenURL=listenURL.replace("%7B%7D","{page}")
			logger.info("generiere Request für basisurl "+self.listenURL)
			url=self.HOST+self.listenURL.format(page=1)
			logger.info("generierte URL für Trefferliste: "+url)
			yield scrapy.Request(url=url, callback=self.parse_liste, errback=self.errback_httpbin, meta={'page': 1})
		


	def parse_liste(self, response):
		logger.info("parse_liste response.status "+str(response.status)+" for "+response.request.url+" Seite "+str(response.meta['page']))
		antwort=response.text
		logger.info("parse_liste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_liste Rohergebnis: "+antwort[:40000])
		
		entries=response.xpath("//div[@class='mod mod-teaser clearfix ']")
		
		logger.info(str(len(entries))+" Dokumente gefunden")
		if entries:
			for entry in entries:
				item={}
				html=self.HOST+PH.NC(entry.xpath(".//a/@href").get(), error="Url für PDF des Entscheids nicht gefunden in "+entry.get())
				item['EDatum']=PH.NC(self.norm_datum(entry.xpath(".//p[@class='teaserDate']/text()").get()), warning="kein Datum gefunden in "+entry.get())
				item['Num']=entry.xpath(".//a/@href").get()
				item['noNumDisplay']=True
				# item['Leitsatz']=PH.NC(entry.xpath(".//a/@title").get(), warning="kein Teaser als Leitsatz gefunden in "+entry.get())
				item['VGericht']=''
				item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], "", item['Num'])
				logger.info("parse_liste Item: "+json.dumps(item))
				
				if html:
					yield scrapy.Request(url=html, callback=self.parse_page, errback=self.errback_httpbin,meta={'item': item})
			if response.xpath("//li[@class='separator-left' and a/text()='Weiter']"):
				#weitere Einträge vorhanden:
				logger.info("Nach Seite "+str(response.meta['page'])+" nun Seite "+str(response.meta['page']+1))
				logger.info("generiere Request mit basisurl "+self.listenURL)
				url=self.HOST+self.listenURL.format(page=response.meta['page']+1)
				logger.info("generierte URL für die nächste Seite: "+url)
				yield scrapy.Request(url=url, callback=self.parse_liste, errback=self.errback_httpbin, meta={'page': response.meta['page']+1})
		else:
			logger.error("keine Entscheidtabelle gefunden")


	def parse_page(self, response):
		logger.info("parse_page response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_page Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+antwort[:40000])
		
		link=response.xpath("//li[@class='line']/a[@href and @title and @class='icon icon--before icon--pdf']/@href")
		item=response.meta['item']
		item['PDFUrls']=[self.HOST+link.get()]
		item['Leitsatz']=PH.NC(response.xpath(".//li[@class='line']/a[@href and @title and @class='icon icon--before icon--pdf']/@title").get(), warning="kein Teaser als Leitsatz gefunden in: "+antwort)
		logger.info("parse_page item: "+json.dumps(item))
		yield item
		