# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class XX_Upload(BasisSpider):
	name = 'XX_Upload'
	
	HOST='https://entscheidsuche.ch'
	URL='/docs/lese_upload.php'
	PDF='/docs/view_upload.php'
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = self.generate_request()

	def generate_request(self):
		return [scrapy.Request(url=self.HOST+self.URL, callback=self.parse_list, errback=self.errback_httpbin)]
		
	def parse_list(self, response):
		logger.info("parse_uploadliste response.status "+str(response.status))
		logger.info("parse_uploadliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_uploadliste Rohergebnis: "+response.body_as_unicode()[:10000])
		uploadliste=json.loads(response.body_as_unicode())
		logger.info(str(len(uploadliste))+" Upload-Einträge gefunden")
		for upload in uploadliste:
			item={}
			item['EDatum']=upload['EDAT']
			item['Num']=upload['Num1']
			if 'Num2' in upload and upload['Num2']:
				item['Num2']=upload['Num2']
			if 'Num3' in upload and upload['Num3']:
				item['Num3']=upload['Num3']
			if 'Titel' in upload and upload['Titel']:
				item['Titel']=upload['Titel']
			if 'Gericht' in upload and upload['Gericht']:
				item['Gericht']=upload['Gericht']
				item['VGericht']=upload['Gericht']				
			if 'Kammer' in upload and upload['Kammer']:
				item['Kammer']=upload['Kammer']
				item['VKammer']=upload['Kammer']
			if 'Kanton' in upload:
				item['Kanton']=upload['Kanton']
			item['PDFUrls']=[self.HOST+self.PDF+'?ID='+upload['ID']]
			item['Signatur']=item['Kanton']+'_UPL_001'
			item['Upload']=True
			yield item

	
		

