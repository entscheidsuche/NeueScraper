# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider

logger = logging.getLogger(__name__)

class AargauSpider(BasisSpider):
	name = 'AG_Gerichte'

	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	DOMAIN='https://agve.weblaw.ch'
	SUCH_URL='/?method=hilfe&ul=de'
	TREFFERLISTE_BODY='s_word=&zips=&method=set_query&query_ticket='
	BLAETTERN_BODY='offset={}&s_pos=1&method=reload_query&query_ticket='
	reQUERY_TICKET=re.compile(r"<input type=\"hidden\" name=\"query_ticket\" value=\"(?P<query_ticket>[^\"]+)\">")
	reTREFFER=re.compile(r"</b>,\s+(?P<treffer>\d+) Treffer \(")
	reEINTRAG=re.compile(r"title=\"(?P<num>[^\"]+)\"[^\"]+<span class=\"s_orgeinh\">\s+(?P<gericht>[^<]+[^\s])\s+</span>\s+<span class=\"s_category\">\s+(?P<kammer>[^<]+[^\s])\s+</span>\s+</div>\s+<div class=\"s_text\">\s+(?P<regeste>[^<]+[^\s])\s+[\s\w>=</\"\.\?%&;-]{1,2000}<a href=\"(?P<html>https?://agve\.weblaw\.ch/html/[^\"]+html)\" target=\"agveresult\">\s+<img src=\"/img/orig\.png\" alt=\"Original\">\s+</a>\s+<a href=\"(?P<pdf>/pdf[^\"]+pdf)\"")
	MONATE=["Jan","Fe","März","April","Mai","Juni","Juli","Au","Sept","Okt","Nov","Dez"]
	reEDATUM=re.compile(r"(?P<tag>\d+)\.(?:.|\s){1,50}(?P<monat>"+"|".join(MONATE)+")(?:.|\s){1,50}(?P<jahr>(?:19|20)\d\d)")
	HEADERS={'POST': '/?method=hilfe&ul=de HTTP/1.1',
			'Host': 'agve.weblaw.ch',
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/82.0',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
			'Accept-Language': 'en-US,en;q=0.5',
			'Accept-Encoding': 'gzip, deflate, br',
			'Content-Type': 'application/x-www-form-urlencoded',
			'Origin: https': '//agve.weblaw.ch',
			'DNT': '1',
			'Connection': 'keep-alive',
			'Referer': 'https://agve.weblaw.ch/?method=hilfe&ul=de',
			'Upgrade-Insecure-Requests': '1',
			'Pragma': 'no-cache',
			'Cache-Control': 'no-cache'}
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen

		request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, callback=self.parse_suchform, errback=self.errback_httpbin)
		return [request]

	def __init__(self):
		super().__init__()
		self.request_gen = self.request_generator()

	def parse_suchform(self,response):
		logger.info("parse_suchform response.status "+str(response.status))
		logger.info("parse_suchform Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_suchform Rohergebnis: "+response.body_as_unicode())
		qt=self.reQUERY_TICKET.search(response.body_as_unicode())
		if qt and qt.group('query_ticket'):
			self.query_ticket=qt.group('query_ticket')
			request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, method="POST", headers=self.HEADERS, body=self.TREFFERLISTE_BODY+self.query_ticket, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'offset': 0})
			yield(request)
		else:
			logger.error("kein Query-Ticket gefunden in: "+response.body_as_unicode())

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode())
		
		# Da das HTML nicht wohlgeformt ist, keine Verwendung von XPATH
		tr=self.reTREFFER.search(response.body_as_unicode())
		if tr and tr.group('treffer'):
			treffer=tr.group('treffer')
			trefferZahl=int(treffer)
			logger.info(treffer+" Treffer gefunden")
			
			for eintrag in self.reEINTRAG.finditer(response.body_as_unicode()):
				item={}
				logger.info("Eintrag Roh: "+eintrag[0])
				if eintrag["num"]:
					item['Num']=eintrag['num']
					item['VGericht']=eintrag['gericht'] if eintrag['gericht'] else ''
					item['VKammer']=eintrag['kammer'] if eintrag['kammer'] else ''
					item['Leitsatz']=eintrag['regeste'] if eintrag['regeste'] else ''
					item['HTMLUrls']=[eintrag['html']] if eintrag['html'] else ''
					item['PDFUrls']=[self.DOMAIN+eintrag['pdf']] if eintrag['pdf'] else ''
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
					item['Kanton']=self.kanton_kurz
					request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item})
					yield(request)
		
		# Nun Blättern
		offset=response.meta['offset']+10

		if offset<trefferZahl:
			logger.info("Hole mit Offset "+ str(offset) +" von "+treffer+" Treffern.")
			request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, method="POST", headers=self.HEADERS, body=self.BLAETTERN_BODY.format(offset)+self.query_ticket, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'offset': offset})
			yield(request)
		

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.info("parse_page response.status "+str(response.status))
		logger.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+response.body_as_unicode())
		item=response.meta['item']
		item['html']=response.body_as_unicode()
		edatum=self.reEDATUM.search(response.body_as_unicode())
		if edatum:
			edatum_string=edatum['jahr']+"-"+str(self.MONATE.index(edatum['monat'])+1).rjust(2,'0')+"-"+edatum['tag'].rjust(2,'0')
		else:
			logger.warning("Kein EDatum erkannt. Nehme dann nur den Jahrgang")
			edatum_string=item["Num"][5:9]
		item['EDatum']=edatum_string
		yield(item)								


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
