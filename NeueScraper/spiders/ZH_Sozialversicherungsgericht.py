# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from ..pipelines import PipelineHelper
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper
import json

logger = logging.getLogger(__name__)

class ZurichSozversSpider(BasisSpider):
	name = 'ZH_Sozialversicherungsgericht'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	SEARCH_PAGE_URL='https://api.findex.webgate.cloud/api/search/*'
	PAYLOAD={"Rechtsgebiet":"","datum":"","operation":">","prozessnummer":""}
	AB_DEFAULT=""
	RESULT_PAGE_URL="https://findex.webgate.cloud/entscheide/"

	HEADERS = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0',
				'Accept': '*/*',
				'Accept-Language': 'en-US,en;q=0.5',
				'Accept-Encoding': 'gzip, deflate, br',
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest',
				'Origin': 'https://findex.webgate.cloud/',
				'Connection': 'keep-alive',
				'Referer': 'https://findex.webgate.cloud/',
				'Pragma': 'no-cache',
				'Cache-Control': 'no-cache'}


	def request_generator(self):
		""" Generates scrapy frist request
		"""

		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen
		return [self.initial_request(self.ab)]

	def initial_request(self,ab=""):
		logging.info("Generiere Request für Suchseite")
		self.PAYLOAD['datum']=ab
		return scrapy.Request(url=self.SEARCH_PAGE_URL, method="POST", body=json.dumps(self.PAYLOAD), headers=self.HEADERS, callback=self.parse_trefferliste, errback=self.errback_httpbin, dont_filter=True)

	def __init__(self,ab=AB_DEFAULT, neu=None):
		super().__init__()
		self.ab = ab
		self.neu = neu
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logging.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logging.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logging.debug("parse_trefferliste Rohergebnis: "+antwort[:20000])
		struktur=json.loads(antwort)
		trefferZahl=len(struktur)
		logging.info(str(trefferZahl)+" Treffer")
		for entscheid in struktur:
			num=entscheid["prozessnummer"]
			logging.info("Verarbeite Entscheid "+num)
			edatum=self.norm_datum(entscheid["entscheiddatum"][:10])
			titel=entscheid["betreff"]
			rechtsgebiet=entscheid["rechtsgebiet"]
			if entscheid["bge"]: titel+=" (BGE "+entscheid["bge"].strip()+")"
			if entscheid["weiterzug"]: titel+=" ("+entscheid["weiterzug"].strip()+")"
			url=self.RESULT_PAGE_URL+num+".html"
			vkammer=''
			vgericht=''
			signatur, gericht, kammer=self.detect(vgericht, vkammer, num)
			item = {
				'Kanton': self.kanton_kurz,
				'Gericht' : gericht,
				'EDatum': edatum,
				'Titel': titel,
				'Num': num,
				'HTMLUrls': [url],
				'PDFUrls': [],
				'Signatur': signatur
			}
			logger.info("Item gelesen: "+json.dumps(item))
			request=scrapy.Request(url=item['HTMLUrls'][0], headers=self.HEADERS, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			if self.check_blockliste(item):
				yield(request)
			else: logging.warning(num+" wurde geblockt (Blockliste).")

	def parse_document(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logging.debug("parse_page response.status "+str(response.status))
		item=response.meta['item']
		text=response.body_as_unicode()
		logging.info("parse_page Rohergebnis "+str(len(text))+" Zeichen für "+item['Num'])
		logging.info("parse_page Rohergebnis: "+text[:10000])

		PipelineHelper.write_html(response.body_as_unicode(), item, self)
		logging.info("yield "+item['Num'])
		yield(item)								
