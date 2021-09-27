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


class SG_Publikationen(BasisSpider):
	name = 'SG_Publikationen'
	
	SUCH_URL='/search/?type=180&filter[type][0]=tx_diamjudicalsg_domain_model_judicalpublication&filter[type][1]=tx_diamjudicalsg_domain_model_judicaldepartmentpublication&timerange[type]=4&page={Seite}&tx_diamcore_search[action]=resultAjax&tx_diamcore_search[controller]=Search'
	HOST ="https://publikationen.sg.ch"
	HEADERS = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'}
	
	def get_next_request(self, seite=1):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL.format(Seite=seite), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'seite': seite}, headers=self.HEADERS)
		return request
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.get_next_request()]

	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		seite=response.meta['seite']
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])

		entscheide=response.xpath("//article[@class='publication-summary']")
		anzahl = len(entscheide)
		logger.info("Anzahl der gefundenen Entscheide: "+str(anzahl)+" (Seite "+str(seite)+")")

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.info("Eintrag: "+text)
			url=PH.NC(entscheid.xpath(".//h2/a[@class='publication-summary__title']/@href").get(),error="keine URL gefunden für "+text)
			request=scrapy.Request(url=self.HOST+url, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item}, headers=self.HEADERS)
			yield request
		
		if anzahl==10:
			logger.info("Hole nun Seite: "+str(seite+1))
			yield self.get_next_request(seite+1)
		else:
			logger.info("Nur "+anzahl+" Treffer auf der Seite, daher Ende bei Seite "+seite)
		
			
	def parse_document(self, response):
		logger.debug("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:30000])
		
		item=response.meta['item']
		item['Num']=PH.NC(response.xpath("//div[@class='publication-detail__metadatadynamic']/dl/dt[.='Fall-Nr.:']/following-sibling::dd[1]/text()").get(),error="keine Num gefunden für "+antwort)
		item['EDatum']=self.norm_datum(PH.NC(response.xpath("//div[@class='publication-detail__metadatadynamic']/dl/dt[.='Entscheiddatum:']/following-sibling::dd[1]/text()").get(),warning="kein EDatum gefunden für "+antwort))
		item['PDatum']=self.norm_datum(PH.NC(response.xpath("//div[@class='publication-detail__metadatadynamic']/dl/dt[.='Publikationsdatum:']/following-sibling::dd[1]/text()").get(),warning="kein PDatum gefunden für "+antwort))
		item['VGericht']=PH.NC(response.xpath("//div[@class='publication-detail__metadatadynamic']/dl/dt[.='Publizierende Stelle:']/following-sibling::dd[1]/text()").get(),warning="keine Stelle gefunden für "+antwort)
		item['VKammer']=PH.NC(response.xpath("//div[@class='publication-detail__metadatadynamic']/dl/dt[.='Rubrik:']/following-sibling::dd[1]/text()").get(),warning="keine Rubrik gefunden für "+antwort)
		item['PDFUrls']=[self.HOST+PH.NC(response.xpath("//a[@title='Diese Publikation als PDF-Version herunterladen']/@href").get(),error="keine PDF-URL gefunden für "+antwort)]
		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],item['VKammer'],item['Num'])
		yield item

	
			
