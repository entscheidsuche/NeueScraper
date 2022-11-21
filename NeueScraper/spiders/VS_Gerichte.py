# -*- coding: utf-8 -*-
import scrapy
import copy
import logging
import json
import re
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.spiders.basis import BasisSpider

logger = logging.getLogger(__name__)

class VS_Gerichte(BasisSpider):
	name = 'VS_Gerichte'
	

	SUCH_URL='/api/search/?offset={offset}&limit={itemsperpage}&sort=_score'
	HOST="https://api-justsearche.vs.ch"
	DOWNLOAD_PATH="/api/documents/"
	ITEMSPERPAGE=50
	ab=None
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		super().__init__()
		if ab:
			self.ab=ab
			self.SUCH_URL+="&date_publication_gte="+self.ab
		self.request_gen = [self.request_generator()]

	def request_generator(self, seite=1):
		request = scrapy.Request(url=self.HOST+self.SUCH_URL.format(offset=str((seite-1)*self.ITEMSPERPAGE), itemsperpage=self.ITEMSPERPAGE), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'seite':seite})
		return request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		struktur=json.loads(antwort)
		seite=response.meta['seite']
		trefferzahl=struktur['count']
		logger.info("Trefferzahl: "+str(trefferzahl))
		for urteil in struktur['results']:
			item={}
			logger.info("Verarbeite nun: "+json.dumps(urteil))
			item['VGericht']=PH.NC(urteil['tribunal']['abbreviation'], error="kein Gericht erkannt")
			item['VKammer']=PH.NC(urteil['case_instance']['text'], warning="keine Kammer")
			if len(urteil['pages'])>0:
				if 'content_display' in urteil['pages'][0]:
					item['Leitsatz']=PH.NC(urteil['pages'][0]['content_display'], warning="kein Leitsatz erkannt")
			item['EDatum']=PH.NC(self.norm_datum(urteil['date_decision']), error="kein EDATUM")
			item['PDatum']=PH.NC(self.norm_datum(urteil['date_publication']), warning="kein PDATUM")
			item['Num']=PH.NC(urteil['case_number']['text'], error="kein Aktenzeichen")
			item['DocID']=str(urteil['id'])
			item['PDFUrls']=[self.HOST+self.DOWNLOAD_PATH+str(urteil['id'])+'/file/']
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
			logger.info("Item: "+json.dumps(item))
			yield item
		# Wenn noch weitere Seiten übrig sind, weiterblättern
		if trefferzahl > seite*self.ITEMSPERPAGE:
			seite += 1
			r=self.request_generator(seite)
			yield r
		
					