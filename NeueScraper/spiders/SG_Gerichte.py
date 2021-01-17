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


class SG_Gerichte(BasisSpider):
	name = 'SG_Gerichte'

	SUCH_URL='/rechtsprechung-gerichte/?filter%5BtimerangeType%5D=5&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D=&filter%5BtimerangeStop%5D=&filter%5Binstitution%5D=&searchQuery='
	SUCH_URL_ab='/rechtsprechung-gerichte/?filter%5BtimerangeType%5D=6&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D={ab}&filter%5BtimerangeStop%5D=31.12.2099&filter%5Binstitution%5D=&searchQuery='
	HOST ="https://publikationen.sg.ch"
	HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0'}

	reURL=re.compile(r'^<a href="(?P<URL>[^"]+)">(?P<Num>\s*\d+/\d+ \d+)\s+(?P<Titel>[^\s(<][^(<]*[^<])?(?:</a>)?$')
	next_link=""
	timer=0
	
	def get_next_request(self, ab=None):
		if ab:
			request=scrapy.Request(url=self.HOST+self.SUCH_URL_ab.format(ab=ab), headers=self.HEADERS, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'gesehen': 0})
		else:
			request=scrapy.Request(url=self.HOST+self.SUCH_URL, headers=self.HEADERS, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'gesehen': 0})
		return request
	
	def __init__(self, ab=None):
		super().__init__()
		self.ab=ab
		self.request_gen = [self.get_next_request(ab)]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])
		
		gesehen=response.meta['gesehen']
		if gesehen==0:
			treffer=PH.NC(response.xpath("//div[@class='box box-large box-mainbox pb-3']/p[@class='mt-4 mb-0']/b/text()").get(),error='Trefferzahl nicht erkannt in '+response.url+': '+antwort)
			trefferzahl=int(treffer.split(" ")[0])
			self.timer=int((datetime.datetime.now()-datetime.datetime(1970,1,1)).total_seconds()*1000)
			self.next_link=PH.NC(response.xpath("//a[@class='control-pagebrowser__next-page']/@href").get(), error="Nextlink nicht gefunden in"+response.url+': '+antwort)
			page=2
			if 'page=2' in self.next_link:
				pos=self.next_link.index('page=2')
				self.next_link=self.next_link[:pos+5]+'{page}'+self.next_link[pos+6:]
			else:
				logger.error("page nicht gefunden in: "+self.next_link)
		else:
			trefferzahl=response.meta['trefferzahl']
			page=response.meta['page']+1
		next_link=self.next_link.format(page=page)+"&_="+str(self.timer)
		self.timer+=1
		
		entscheide=response.xpath('//div[@class="publication-list__item publication-list__item--publication box box-large box-mainbox pb-5"]')
		logger.info("Treffer auf dieser Seite: "+str(len(entscheide)))
		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			item['Num']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Fall-Nr.')]/following-sibling::dd/text()").get(), error="Keine Geschäftsnummer erkannt in: "+text)
			item['VKammer']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Rubrik')]/following-sibling::dd/text()").get(), error="Gericht nicht erkannt in: "+text)
			item['VGericht']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Publizierende Stelle')]/following-sibling::dd/text()").get(), error="Gericht nicht erkannt in: "+text)
			item['PDatum']=self.norm_datum(PH.NC(entscheid.xpath(".//li/span/b[starts-with(.,'Publikationsdatum')]/text()").get(), error="kein Publikationsdatum erkannt in: "+text))
			item['EDatum']=self.norm_datum(PH.NC(entscheid.xpath(".//li/span/b[starts-with(.,'Entscheiddatum')]/text()").get(), error="kein Entscheiddatum erkannt in: "+text))
			item['Abstract']=PH.NC(entscheid.xpath(".//article[@class='publication-summary']/p/text()").get(), error="keinen Abstract gefunden in: "+text)
			url=self.HOST+PH.NC(entscheid.xpath(".//div[@class='publication-list__item-buttons d-flex main-box-btn-wrap justify-content-md-start align-items-center pt-2 flex-wrap flex-md-nowrap']/a/@href").get(),error="keine PDF-Url gefunden in: "+text)
			item['PDFUrls']=[url]
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],item['VKammer'],item['Num'])

			yield item
		
		gesehen+=len(entscheide)
		if gesehen<trefferzahl:
			request=scrapy.Request(url=self.HOST+next_link, headers=self.HEADERS, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'gesehen': gesehen, 'trefferzahl': trefferzahl, 'page': page})
			yield request
			
			
		