# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
import json

logger = logging.getLogger(__name__)

class AargauSpider(BasisSpider):
	name = 'AG_Gerichte'
	HOST="https://decwork.ag.ch"
	SUCH_URL="/api/main/v1/de/decrees_chronology"
	HEADERS= {
		'Host': 'decwork.ag.ch',
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:99.0) Gecko/20100101 Firefox/99.0',
		'Accept': 'application/json, text/plain, */*',
		'Accept-Language': 'en-US,en;q=0.5',
		'Accept-Encoding': 'gzip, deflate, br',
		'Content-Type': 'application/json',
		'Origin': 'https://gesetzessammlungen.ag.ch',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Sec-Fetch-Dest': 'empty',
		'Sec-Fetch-Mode': 'cors',
		'Sec-Fetch-Site': 'same-site'
	}
	DOWNLOAD_PATH="/api/main/v1/de/decrees_pdf/"
	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+self.SUCH_URL,method="POST", body="{}", headers=self.HEADERS, callback=self.parse_trefferliste, errback=self.errback_httpbin)]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		struktur=json.loads(antwort)
		count=struktur['count']
		logger.info("Trefferzahl: "+str(count))
		for jahr in struktur['chronology']:
			for monat in struktur['chronology'][jahr]:
				for urteil in struktur['chronology'][jahr][monat]:
					item={}
					logger.info("Verarbeite nun: "+json.dumps(urteil))
					item['VGericht']=urteil['institution_name']
					item['VKammer']=urteil['institution_name']
					item['Leitsatz']=urteil['guidance_summary']
					item['EDatum']=self.norm_datum(urteil['decree_date'])
					item['Num']=urteil['number']
					item['DocID']=str(urteil['decree_id'])
					item['PDFUrls']=[self.HOST+self.DOWNLOAD_PATH+str(urteil['decree_id'])]
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
					logger.info("Item: "+json.dumps(item))
					yield item
					