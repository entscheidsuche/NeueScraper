# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from twisted.internet import defer, threads


logger = logging.getLogger(__name__)

class WeblawSpider(BasisSpider):
	#name = 'Weblaw (virtuell)'

	TREFFERLISTE_BODY='s_word=&zips=&method=set_query&query_ticket='
	BLAETTERN_BODY='offset={}&s_pos=1&method=reload_query&query_ticket='
	reQUERY_TICKET=re.compile(r"<input type=\"hidden\" name=\"query_ticket\" value=\"(?P<query_ticket>[^\"]+)\">")

	
	def request_generator(self, ab=None):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Query Ticket zu holen

		request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, headers=self.HEADERS, callback=self.parse_suchform, errback=self.errback_httpbin)
		return [request]

	def __init__(self, ab=None, neu=None):
		self.ab=ab
		self.neu=neu
		super().__init__()
		self.request_gen = self.request_generator(self.ab)

	def parse_suchform(self,response):
		logger.info("parse_suchform response.status "+str(response.status))
		logger.info("parse_suchform Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_suchform Rohergebnis: "+response.text)
		qt=self.reQUERY_TICKET.search(response.text)
		if qt and qt.group('query_ticket'):
			self.query_ticket=qt.group('query_ticket')
			request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, method="POST", headers=self.HEADERS, body=self.TREFFERLISTE_BODY+self.query_ticket, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'offset': 0})
			yield(request)
		else:
			logger.error("kein Query-Ticket gefunden in: "+response.text)

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.text)
		
		tr=self.reTREFFER.search(response.text)
		if tr and tr.group('treffer'):
			treffer=tr.group('treffer')
			trefferZahl=int(treffer)
			logger.info(treffer+" Treffer gefunden")
			logger.info("Rufe nun process_liste für "+self.name+" auf.")
			requests=[]
			items=[]
			zahl=self.process_liste(response,requests, items)
			logger.info("Es wurden "+str(zahl)+" Entscheide verarbeitet.")
			for r in requests:
				yield r
			for i in items:
				yield i
		
		# Nun Blättern
		offset=response.meta['offset']+10

		if offset<trefferZahl:
			logger.info("Hole mit Offset "+ str(offset) +" von "+treffer+" Treffern.")
			request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, method="POST", headers=self.HEADERS, body=self.BLAETTERN_BODY.format(offset)+self.query_ticket, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'offset': offset})
			yield(request)


	def process_liste(self, antwort):
		logger.error("Aufruf der dummy Methode 'process_liste', die von den abgeleiteten Klassen aufgerufen werden sollte")
		return 0



	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
