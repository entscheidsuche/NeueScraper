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


class AG_Baugesetzgebung(BasisSpider):
	name = 'AG_Baugesetzgebung'

	HOST='https://www.ag.ch'
	URL='/app/search-service/api/v1/doctable'
	
	BODY1={
		"pagination": {"page": 0, "size": 200},
		"filter": {
			"operator": "in",
			"field": "categories",
			"values": [
				"f46f0fe7-d92e-45a9-b5b7-0f3402debb21",
			],
		},
		"sort": [{"field": "documentDatetime", "direction": "desc"}]
	}

	BODY2={
		"pagination": {"page": 0, "size": 200},
		"filter": {
			"operator": "in",
			"field": "categories",
			"values": [
				"a2f10c55-82f9-403c-b7fa-6a5dfc3cc01f",
				"b8460a34-2978-4878-9f84-00b9c32b1114",
				"110b2681-6e2a-4e11-9bfa-8e270b6cee24",
				"9a6bb2aa-9a7c-4f2f-92d9-ceb395637d2a",
			],
		},
		"sort": [{"field": "documentDatetime", "direction": "desc"}]
	}

       
	HEADERS = {
		"Accept": "*/*",
		"Accept-Language": "de,en-US;q=0.7,en;q=0.3",
		"Content-Type": "application/json",
		"Origin": "https://www.ag.ch",
		"Referer": (
			"https://www.ag.ch/de/verwaltung/bvu/bauen/baurecht/entscheidsammlung"
		),
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
		request1=scrapy.Request(url=self.HOST+self.URL, method="POST", body=json.dumps(self.BODY1), headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)
		request2=scrapy.Request(url=self.HOST+self.URL, method="POST", body=json.dumps(self.BODY2), headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)		
		return [request1,request2]

	# Unklar ob es sich um eine Menüseite oder eine Trefferliste handelt
	def parse_page(self, response):
		logger.info("parse_page response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_page Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+antwort[:40000])
		
		struktur=json.loads(antwort)
		entries=struktur['files']
		logger.info(str(len(entries))+" Dokumente gefunden")
		if entries:
			for entry in entries:
				logger.info("Verarbeite Entscheid "+json.dumps(entry))
				item={}
				item['PDFUrls']=[self.HOST+PH.NC(entry['targetUrls'][0]['url'], error="Url für PDF des Entscheids nicht gefunden in "+json.dumps(entry))]
				item['EDatum']=PH.NC(self.norm_datum(entry['documentDatetime']), warning="kein Datum gefunden in "+json.dumps(entry))
				item['Num']=PH.NC(entry['title'], warning="kein title als Num-Ersatz gefunden in "+json.dumps(entry))
				item['noNumDisplay']=True
				item['Leitsatz']=PH.NC(entry['teaser'], warning="kein Teaser als Leitsatz gefunden in "+json.dumps(entry))
				item['VGericht']=''
				item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], "", item['Num'])
				logger.info("Item: "+json.dumps(item))
				yield item
		else:
			logger.error("keine Entscheidtabelle gefunden")
