# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime

class AargauSpider(scrapy.Spider):
	name = 'aargau'
	KANTON = 'Aargau'

	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	TREFFERLISTE_URL='https://agve.weblaw.ch/?method=hilfe&ul=de'
	TREFFERLISTE_BODY='s_word=&zips=&method=set_query&query_ticket=RY446H1Y'
	ab=None
	reDatum=re.compile('[0-9]{2}\\.[0-9]{2}\\.[0-9]{4}')
	reTyp=re.compile('.+(?= vom [0-9]{2}\\.[0-9]{2}\\.[0-9]{4})')	
	def request_generator(self, ab, page):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen
		
		if(ab==None):
			request=scrapy.Request(url=self.TREFFERLISTE_URL.format(page=page), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': page})
		else:
			request=scrapy.Request(url=self.TREFFERLISTE_URL.format(page=page), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': page})	
		return [request]

	def __init__(self, ab=None):
		super().__init__()
		self.ab=ab
		self.request_gen = self.request_generator(self.ab, 1)

	def start_requests(self):
		# treat the first request, subsequent ones are generated and processed inside the callback
		logging.info("Normal gestartet")
		for request in self.request_gen:
			yield request
		logging.info("Normal beendet")

	def parse_trefferliste(self, response):
		logging.info("parse_trefferliste response.status "+str(response.status))
		logging.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode())
		
		treffer=response.xpath("(//table[@width='98%']//table[@width='100%']/tr/td/b/text())[2]").get()
		trefferZahl=int(treffer)
		
		entscheide=response.xpath("//table[@width='100%']/tr/td[@valign='top']/table")
		for entscheid in entscheide:
			logging.info("Verarbeite Entscheid: "+entscheid.get())
			url=entscheid.xpath(".//a/@href").get()
			logging.info("url: "+url)
			num=entscheid.xpath(".//a/font/text()").get()
			logging.info("num: "+num)
			kammer=entscheid.xpath(".//tr[1]/td[4]/font/text()").get()
			if kammer==None:
				kammer=""
				logging.info("keine Kammer")
			else:
				logging.info("Kammer: "+kammer)
			titel=entscheid.xpath(".//tr[2]/td[2]/b/text()").get()
			logging.info("Titel: "+titel)
			regesten=entscheid.xpath(".//tr[2]/td[2]/text()").getall()
			regeste=""
			for s in regesten:
				if not(s.isspace() or s==""):
					if len(regeste)>0:
						regeste=regeste+" "
					regeste=regeste+s
			datum=entscheid.xpath(".//td[@colspan='2']/i/text()").get()
			logging.info("Typ+Datum: "+datum)
			edatum=self.reDatum.search(datum).group(0)
			if self.reTyp.search(datum):
				typ= self.reTyp.search(datum).group(0)
			else:
				typ=""
			id=entscheid.xpath(".//td[a]/text()").get()
			logging.info("ID?: "+id)	
			item = {
				'Kanton': self.KANTON,
				'Gericht' : self.GERICHT,
				'EDatum': edatum,
				'Titel': titel,
				'Leitsatz': regeste.strip(),
				'Num': num,
				'HTMLUrl': [url],
				'PDFUrl': [],
				'Kammer': kammer,
				'Entscheidart': typ
			}
			request=scrapy.Request(url=url, callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item})
			yield(request)
		
		page=response.meta['page']+1

		if page*10<trefferZahl:
			logging.info("Hole Seite "+ str(page) +" von "+treffer+" Treffern.")
			request=self.request_generator(self.ab,page)[0]
			yield(request)
		

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logging.info("parse_page response.status "+str(response.status))
		logging.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_page Rohergebnis: "+response.body_as_unicode())
		item=response.meta['item']
		item['html']=response.body_as_unicode()
		yield(item)								


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))
