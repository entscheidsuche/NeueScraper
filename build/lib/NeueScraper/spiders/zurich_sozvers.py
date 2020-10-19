# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from ..pipelines import PipelineHelper

class ZurichSozversSpider(scrapy.Spider):
	name = 'zurich_sozvers'
	KANTON = 'Zürich'
	GERICHT ="Sozialversicherungsgericht"
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	SEARCH_PAGE_URL='https://chid003d.ideso.ch/c050018/svg/findexweb.nsf/suche.xsp'
	RESULT_PAGE_URL='https://chid003d.ideso.ch/c050018/svg/findexweb.nsf/suche.xsp?$$ajaxid=@none'
	RESULT_PAGE_PAYLOAD='view%3A_id1%3Asuchbegriff=&view%3A_id1%3Aprozessnummer={Jahr}&view%3A_id1%3Adatumbereich=3&view%3A_id1%3Adatum=&view%3A_id1%3Arechtsgebiet=&%24%24viewid={viewid}&%24%24xspsubmitid=view%3A_id1%3A_id55&%24%24xspexecid=&%24%24xspsubmitvalue=&%24%24xspsubmitscroll=0%7C0&view%3A_id1=view%3A_id1'
	NEXT_PAGE_URL='https://chid003d.ideso.ch/c050018/svg/findexweb.nsf/ergebnis.xsp?$$ajaxid=view:_id1:vipResultate_OUTER_TABLE'
	NEXT_PAGE_PAYLOAD='%24%24viewid={viewid}&%24%24xspsubmitid=view%3A_id1%3AvipResultate%3Apager1__NextImage&%24%24xspexecid=view%3A_id1%3AvipResultate%3Apager1&%24%24xspsubmitvalue=&%24%24xspsubmitscroll=0%7C2134&view%3A_id1=view%3A_id1'
	BASIS_URL='https://chid003d.ideso.ch'
	reForward=re.compile('(?<=^window\.location\.href=\\")[^\\"]+(?=\\")')
	reTreffer=re.compile('^[0-9]+')

	AB_DEFAULT='1993'

	HEADERS = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0',
				'Accept': '*/*',
				'Accept-Language': 'en-US,en;q=0.5',
				'Accept-Encoding': 'gzip, deflate, br',
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest',
				'Origin': 'https://chid003d.ideso.ch',
				'Connection': 'keep-alive',
				'Referer': 'https://chid003d.ideso.ch/c050018/svg/findexweb.nsf/suche.xsp',
				'Pragma': 'no-cache',
				'Cache-Control': 'no-cache'}

	NEXT_PAGE_HEADERS = { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0',
				'Accept': '*/*',
				'Accept-Language': 'en-US,en;q=0.5',
				'Accept-Encoding': 'gzip, deflate, br',
				'Content-Type': 'application/x-www-form-urlencoded',
				'X-Requested-With': 'XMLHttpRequest',
				'Origin': 'https://chid003d.ideso.ch',
				'Connection': 'keep-alive',
				'Referer': 'https://chid003d.ideso.ch/c050018/svg/findexweb.nsf/ergebnis.xsp',
				'Pragma': 'no-cache',
				'Cache-Control': 'no-cache'}


	def cookie_debug(self, request, response, name):
		cookies= "Received: "
		for c in response.headers.getlist('Set-Cookie'):
			cookies = cookies+"\n"+c.decode()
		cookies = cookies+"\nto be sent: "			
		for c in request.headers.getlist('Cookie'):
			cookies = cookies+"\n"+c.decode()
		msg = "Sending cookies with request to: {}\n{}".format(request, cookies)
		logging.info("Cookie Debug "+name+": "+name+", "+msg)


	def request_generator(self):
		""" Generates scrapy frist request
		"""

		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen
		return [self.initial_request(int(self.ab))]

	def initial_request(self, jahr):
		logging.info("Generiere Initialrequest für Suchseite für Jahr "+str(jahr))
		return scrapy.Request(url=self.SEARCH_PAGE_URL, callback=self.parse_searchform, errback=self.errback_httpbin, dont_filter=True, meta={"jahr":jahr})

	def __init__(self,ab=AB_DEFAULT):
		super().__init__()
		self.ab = ab
		self.request_gen = self.request_generator()

	def start_requests(self):
		# treat the first request, subsequent ones are generated and processed inside the callback
		for request in self.request_gen:
			yield request
		logging.info("Normal beendet")

	def parse_searchform(self, response):
		logging.info("parse_searchform response.status "+str(response.status))
		logging.info("parse_searchform Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_searchform Rohergebnis: "+response.body_as_unicode())
		jahr=response.meta['jahr']
		viewId=response.xpath("//input[@id='view:_id1__VUID']/@value").get()
		logging.info("View-ID: "+viewId)
		logging.info("search_request für Jahr "+str(jahr)+" mit viewId "+viewId)
		cookieJar = response.meta.setdefault('cookie_jar', CookieJar())
		cookieJar.extract_cookies(response, response.request)
		request = scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=jahr, viewid=viewId), headers=self.HEADERS, callback=self.parse_trefferliste_forward, errback=self.errback_httpbin, meta = {'cookie_jar': cookieJar, 'jahr':jahr})
		cookieJar.add_cookie_header(request) # apply Set-Cookie ourselves
		self.cookie_debug(request, response, "parse_searchform")
		return request

	def parse_trefferliste_forward(self, response):
		logging.info("parse_trefferliste_forward response.status "+str(response.status))
		logging.info("parse_trefferliste_forward Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_trefferliste_forward Rohergebnis: "+response.body_as_unicode())
		jahr=response.meta['jahr']
		cookieJar = response.meta.setdefault('cookie_jar', CookieJar())
		cookieJar.extract_cookies(response, response.request)
		forward=response.xpath("//script/text()").get()
		forwardUrl=self.reForward.search(forward).group(0)
		logging.info("Forward-URL: "+forwardUrl)
		request = scrapy.Request(url=forwardUrl, headers=self.HEADERS, dont_filter=True , callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'cookie_jar': cookieJar, 'jahr':jahr, 'geholt':0})
		cookieJar.add_cookie_header(request) # apply Set-Cookie ourselves
		self.cookie_debug(request, response, "parse_trefferliste_forward")
		yield(request) 

	def parse_trefferliste(self, response):
		logging.info("parse_trefferliste response.status "+str(response.status))
		logging.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode())
		jahr=response.meta['jahr']
		#Bei der ersten Trefferseite steht die view_ID und die Trefferzahl im HTML, danach wird sie mit meta übergeben
		geholt=response.meta['geholt']
		if geholt==0:
			viewId=response.xpath("//input[@id='view:_id1__VUID']/@value").get()
			treffer=response.xpath("//span[@id='view:_id1:cfResults']/text()").get()
			logging.info("Treffer: "+treffer)
			trefferZahl=int(self.reTreffer.search(treffer).group(0))
		else:
			viewId=response.meta['viewId']
			trefferZahl=response.meta['trefferZahl']
		logging.info("View-ID: "+viewId)
		
		cookieJar = response.meta.setdefault('cookie_jar', CookieJar())
		cookieJar.extract_cookies(response, response.request)
		if trefferZahl >= 5000:
			logging.error("Zu viele Treffer ("+str(trefferZahl)+"): Es fehlen vermutlich Dokumente")
		if trefferZahl == 0:
			logging.info("keine Treffer für Jahr "+str(jahr))
		else:
			logging.info(str(trefferZahl)+" Treffer für Jahr "+str(jahr))
			entscheide=response.xpath("//tr[@role='row' and td[@class='xspColumnViewStart']]")
			trefferAufSeite = len(entscheide)
			logging.info("Treffer auf Trefferseite: "+str(trefferAufSeite)+", vorher schon geholt: "+str(geholt))

			for entscheid in entscheide:
				logging.info("Verarbeite Entscheid "+entscheid.extract())
				attribute=entscheid.xpath(".//span[@class='xspTextViewColumn']/text()").getall()
				if len(attribute)!=3:
					logging.error("Falsche Anzahl Attribut: "+len(attribute)+" bei: "+entscheid.extract())
				url=self.BASIS_URL+entscheid.xpath(".//a[@class='xspLink']/@href").get()
				titel=entscheid.xpath(".//a[@class='xspLink']/text()").get()
				item = {
					'Kanton': self.KANTON,
					'Gericht' : self.GERICHT,
					'EDatum': attribute[1],
					'Titel': titel,
					'Num': attribute[0],
					'HTMLUrls': [url],
					'PDFUrls': []
				}
				request=scrapy.Request(url=url, callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item})
				yield(request)
				yield(item)
			geholt=geholt+trefferAufSeite
			if geholt<trefferZahl:
				logging.info("search_request für Treffer "+str(geholt)+"+ von "+str(trefferZahl)+" mit viewId "+viewId)
				cookieJar = response.meta.setdefault('cookie_jar', CookieJar())
				cookieJar.extract_cookies(response, response.request)
				request = scrapy.Request(url=self.NEXT_PAGE_URL, method="POST", body= self.NEXT_PAGE_PAYLOAD.format(viewid=viewId), headers=self.NEXT_PAGE_HEADERS, callback=self.parse_trefferliste, dont_filter=True, errback=self.errback_httpbin, meta = {'cookie_jar': cookieJar, 'jahr':jahr, 'viewId': viewId, 'trefferZahl': trefferZahl, 'geholt': geholt})
				logging.info("URL: "+request.url)
				logging.info("body: "+request.body.decode())
				cookieJar.add_cookie_header(request) # apply Set-Cookie ourselves
				self.cookie_debug(request, response, "parse_trefferliste")
				yield(request)
				return
			else:
				logging.info(str(geholt)+" von "+str(trefferZahl)+" für Jahr "+str(jahr)+" wurden geholt.")	
		aktJahr=datetime.datetime.now().year
		if jahr<aktJahr:
			jahr=jahr+1
			logging.info("Weiter mit Jahr "+str(jahr))
			request=self.initial_request(jahr)
			self.cookie_debug(request, response, "neues Jahr "+str(jahr))
			yield(request)
		else:
			logging.info("Beende Scrapen bei Jahr "+str(jahr))

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logging.info("parse_page response.status "+str(response.status))
		logging.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logging.info("parse_page Rohergebnis: "+response.body_as_unicode())
		item=response.meta['item']
		path=PipelineHelper.file_path(response.url, response, self)

		#yield store.persist_file(path, response.body_as_unicode(), info=self, meta=response.meta, headers=None)
		#checksum = md5sum(buf)
		item['html']=response.body_as_unicode()
		yield(item)								


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))
