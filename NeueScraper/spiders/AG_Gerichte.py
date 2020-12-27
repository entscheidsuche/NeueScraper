# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.weblaw import WeblawSpider
from NeueScraper.pipelines import PipelineHelper

logger = logging.getLogger(__name__)

class AargauSpider(WeblawSpider):
	name = 'AG_Gerichte'

	DOMAIN='https://agve.weblaw.ch'
	SUCH_URL='/?method=hilfe&ul=de'
	reTREFFER=re.compile(r"</b>,\s+(?P<treffer>\d+) Treffer \(")
	reEINTRAG=re.compile(r"title=\"(?P<num>[^\"]+)\"[^\"]+<span class=\"s_orgeinh\">\s+(?P<gericht>[^<]+[^\s])\s+</span>\s+<span class=\"s_category\">\s+(?P<kammer>[^<]+[^\s])\s+</span>\s+</div>\s+<div class=\"s_text\">\s+(?P<regeste>[^<]+[^\s])\s+[\s\w>=</\"\.\?%&;-]{1,2000}<a href=\"(?P<html>https?://agve\.weblaw\.ch/html/[^\"]+html)\" target=\"agveresult\">\s+<img src=\"/img/orig\.png\" alt=\"Original\">\s+</a>\s+<a href=\"(?P<pdf>/pdf[^\"]+pdf)\"")
	MONATE=["Jan","Fe","März","April","Mai","Juni","Juli","Au","Sept","Okt","Nov","Dez"]
	reEDATUM=re.compile(r"(?P<tag>\d+)\.(?:.|\s){1,50}(?P<monat>"+"|".join(MONATE)+")(?:.|\s){1,50}(?P<jahr>(?:19|20)\d\d)")
	HEADERS={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/82.0',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
			'Accept-Language': 'en-US,en;q=0.5',
			'Accept-Encoding': 'gzip, deflate, br',
			'Content-Type': 'application/x-www-form-urlencoded',
			'Origin': 'https://agve.weblaw.ch',
			'DNT': '1',
			'Connection': 'keep-alive',
			'Referer': 'https://agve.weblaw.ch/?method=hilfe&ul=de',
			'Upgrade-Insecure-Requests': '1',
			'Pragma': 'no-cache',
			'Cache-Control': 'no-cache'}
	
	def process_liste(self, response, requests, items):
		zahl=0
		logger.info("process_liste: "+response.body_as_unicode())
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
				requests.append(scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item}))
				zahl=zahl+1
		return zahl

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.info("parse_page response.status "+str(response.status))
		logger.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+response.body_as_unicode())
		item=response.meta['item']
		edatum=self.reEDATUM.search(response.body_as_unicode())
		if edatum:
			edatum_string=edatum['jahr']+"-"+str(self.MONATE.index(edatum['monat'])+1).rjust(2,'0')+"-"+edatum['tag'].rjust(2,'0')
		else:
			logger.warning("Kein EDatum erkannt. Nehme dann nur den Jahrgang")
			edatum_string=item["Num"][5:9]
		item['EDatum']=edatum_string
		PipelineHelper.write_html(response.body_as_unicode(), item, self)

		yield(item)								

