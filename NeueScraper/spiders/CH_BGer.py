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
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
from urllib.parse import quote
import random
import os, base64, hashlib, time


logger = logging.getLogger(__name__)

class CH_BGer(BasisSpider):
	name = 'CH_BGer'

	INITIAL_URL='/sitemaps/sitemapindex.xml'
	HOST='http://relevancy.bger.ch'

	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Referer': 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index.php',
		'Upgrade-Insecure-Requests': '1',
		'Sec-Fetch-Dest': 'document',
		'Sec-Fetch-Mode': 'navigate',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-User': '?1',
		'Priority': 'u=0, i',
		'Pragma': 'no-cache',
		'Cache-Control': 'no-cache',
		'TE': 'trailers'
	}
	
	custom_settings = {
	#	"CONCURRENT_REQUESTS": 1,
		"DOWNLOAD_DELAY": 0.5,
		"ZYTE_API_PRESERVE_DELAY": True
	}

	reAZA=re.compile(r"sitemap_aza_(?P<Jahr>[12][90][0-9][0-9])\.xml$")
	reID=re.compile(r"JumpCGI\?id=(?P<ID>(?P<DATUM>\d\d\.\d\d\.\d\d\d\d)_(?P<NUM>[-_0-9A-Z]+/[12][90]\d\d))\s*$")
	
	# ab und bis nur in Jahreszahlen
	def __init__(self, ab=None, neu=None, bis=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		self.bis=bis
		self.request_gen = self.request_generator(ab, bis)

	def request_generator(self,ab=None,bis=None):
		if ab:
			self.ab=ab
		else:
			self.ab=None
			
		if bis:
			self.bis=bis
		else:
			self.bis=None
			
		return [scrapy.Request(url=self.HOST+self.INITIAL_URL, headers=self.HEADER, callback=self.parse_sitemap)]

	def parse_sitemap(self, response):
		antwort=response.text
		logger.info("parse_sitemap Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_sitemap Rohergebnis: "+antwort[:30000])
		entries=response.xpath('//*[local-name()="loc"]/text()').getall()
		if entries==None:
			logger.info("keine Einträge in der Sitemap gefunden: "+antwort)
		else:
			for entry in entries:
				link=entry
				aza=self.reAZA.search(link)
				if aza:
					jahr=int(aza.group('Jahr'))
					if (self.ab and int(self.ab)>jahr) or (self.bis and int(self.bis)<jahr):
						logger.info(f"Gefunden {link}. {jahr} ist nicht im Intervall von {self.ab} - {self.bis}")
					else:
						request=scrapy.Request(url=link, headers=self.HEADER, callback=self.parse_jahressitemap)
						yield request
					
	def parse_jahressitemap(self, response):
		antwort=response.text
		logger.info("parse_jahressitemap Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_jahressitemap Rohergebnis: "+antwort[:30000])
		entries=response.xpath('//*[local-name()="loc"]/text()').getall()
		if entries==None:
			logger.info("keine Einträge in der Jahres-Sitemap gefunden: "+antwort)
		else:
			for entry in entries:
				item={}
				link=entry
				meta=self.reID.search(link)
				if meta:
					item['DocID']=PH.NC(meta.group("ID"),error="keine DokumentID in "+link)
					item['Num']=PH.NC(meta.group("NUM"),error="keine Geschäftsnummer in "+link)
					item['EDatum']=PH.NC(self.norm_datum(meta.group("DATUM")),error="kein Datum in "+link)
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
					item['HTMLUrls']=[link]
					request = scrapy.Request(url=link, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
					yield request
				else:
					logger.error(f"konnte {link} nicht zerlegen")

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:30000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:30000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
