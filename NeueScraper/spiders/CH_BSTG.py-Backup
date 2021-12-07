# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.weblaw import WeblawSpider

logger = logging.getLogger(__name__)

class CH_BSTG(WeblawSpider):
	name = 'CH_BSTG'

	DOMAIN='https://bstger.weblaw.ch'
	SUCH_URL='/index.php?='
	NEWS_URL='/index.php?method=news'
	reTREFFER=re.compile(r'<td colspan=\"6\" class=\"table_data\"><nobr>\s+(?P<treffer>\d+) Treffer \(')
	rePDF=re.compile(r"\'(?P<name>[^\']+)\'")
	HEADERS={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:82.0) Gecko/20100101 Firefox/82.0',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
			'Accept-Language': 'en-US,en;q=0.5',
			'Accept-Encoding': 'gzip, deflate, br',
			'Content-Type': 'application/x-www-form-urlencoded',
			'Origin:': 'https://bstger.weblaw.ch/',
			'DNT': '1',
			'Connection': 'keep-alive',
			'Referer': 'https://bstger.weblaw.ch/',
			'Upgrade-Insecure-Requests': '1',
			'Pragma': 'no-cache',
			'Cache-Control': 'no-cache',
			'Cookie': '_ga=GA1.2.1816131663.1569870731; __gads=ID=c4a85440ac150faa:T=1569870731:S=ALNI_MYxfPvI28WiR7rAG9E8DUH5NZxACQ; lang=de'}

	def request_generator(self, ab):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Query Ticket zu holen

		if ab is not None:
			request=scrapy.Request(url=self.DOMAIN+self.NEWS_URL, headers=self.HEADERS, callback=self.parse_einzelseite, errback=self.errback_httpbin)		
		else:
			request=scrapy.Request(url=self.DOMAIN+self.SUCH_URL, headers=self.HEADERS, callback=self.parse_suchform, errback=self.errback_httpbin)
		return [request]

	def parse_einzelseite(self, response):
		logger.info("parse_einzelseite response.status "+str(response.status))
		logger.info("parse_einzelseite Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_einzelseite Rohergebnis: "+response.body_as_unicode())
		entscheide=response.xpath("//table/tr[td[@class='table_data head2 nowrap']]")
		logger.info(str(len(entscheide))+" potentielle Entscheide gefunden.")
		for e in entscheide:
			zeilen=e.xpath("./td")
			logger.info(str(len(zeilen))+" td in tr gefunden.")
			if len(zeilen)==6:
				logger.info("potentieller Entscheid: "+e.get())
				item={}
				item['Num']=e.xpath('./td[1]/a/text()').get().strip()
				if item['Num']:
					item['VGericht']=''
					item['VKammer']=''
					item['EDatum']=self.norm_datum(e.xpath('./td[3]/text()').get())
					item['Leitsatz']=e.xpath('./td[6]/text()').get()
					item['Weiterzug']=e.xpath('./td[4]/text()').get()
					pdf=e.xpath('./td[2]/a/@onclick').get()
					if pdf:
						logger.info("PDF: "+pdf)
						re=self.rePDF.search(pdf)
						if re:
							item['PDFUrls']=[self.DOMAIN+"/"+re.group('name')]
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
					item['Kanton']=self.kanton_kurz
					yield item
				else:
					logger.error("Geschäftsnummer nicht gefunden in: "+e.get())



	def process_liste(self, response, requests, items):
		zahl=0
		entscheide=response.xpath("//table/tr[td[@class='table_data head2 nowrap']]")
		logger.debug(str(len(entscheide))+" potentielle Entscheide gefunden.")
		for e in entscheide:
			zeilen=e.xpath("./td")
			logger.debug(str(len(zeilen))+" td in tr gefunden.")
			if len(zeilen)>=7:
				logger.debug("potentieller Entscheid: "+e.get())
				item={}
				item['Num']=e.xpath('./td[1]/a/text()').get().strip()
				if item['Num']:
					item['VGericht']=''
					item['VKammer']=e.xpath('./td[4]/text()').get() if e.xpath('./td[4]/text()').get() else ''
					item['EDatum']=self.norm_datum(e.xpath('./td[3]/text()').get())
					item['Leitsatz']=e.xpath('./td[7]/text()').get()
					item['Weiterzug']=e.xpath('./td[5]/text()').get()
					pdf=e.xpath('./td[2]/a/@onclick').get()
					if pdf:
						logger.debug("PDF: "+pdf)
						re=self.rePDF.search(pdf)
						if re:
							item['PDFUrls']=[self.DOMAIN+"/"+re.group('name')]
					item['Signatur'], item['Gericht'], item['Kammer']=self.detect(item['VGericht'], item['VKammer'], item['Num'])
					item['Kanton']=self.kanton_kurz
					zahl=zahl+1
					items.append(item)
				else:
					logger.error("Geschäftsnummer nicht gefunden in: "+e.get())
		return zahl


