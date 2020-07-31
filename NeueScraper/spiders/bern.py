# -*- coding: utf-8 -*-
import scrapy
import re
import logging


class BernSpider(scrapy.Spider):
	name = 'bern_virtual'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	reVor=re.compile('//OK\\[[0-9,\\.]+\\[')
	reAll=re.compile('(?<=,\\")[^\\"]*(?:\\\\\\"[^\\"]*)*(?=\\",)')
	reID=re.compile('[0-9a-f]{32}')
	reDatum=re.compile('\d{4}-\d{2}-\d{2}')
	reRG=re.compile('[^0-9\\.:-]{3}.{3,}')
	reTreffer=re.compile('(?<=^//OK\\[)[0-9]+')
	page_nr=0
	trefferzahl=0
	
	def get_next_request(self):
		if self.ab is None:
			body = self.RESULT_QUERY_TPL.format(page_nr=self.page_nr)
		else:
			body = self.RESULT_QUERY_TPL_AB.format(page_nr=self.page_nr, datum=self.ab)
		self.page_nr=self.page_nr+1
		return body	
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		body=self.get_next_request()
		return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)]

	def __init__(self,ab=None):
		super().__init__()
		self.ab = ab
		self.request_gen = self.request_generator()

	def start_requests(self):
		# treat the first request, subsequent ones are generated and processed inside the callback
		for request in self.request_gen:
			yield request
		logging.info("Normal beendet")

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
	
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			# construct and download document links
			logging.info("Rohergebnis: "+response.body_as_unicode())
			if self.page_nr==1:
				treffer=self.reTreffer.search(response.body_as_unicode())
				if treffer:
					logging.info("Trefferzahl: "+treffer.group())
					self.trefferzahl=int(treffer.group())
			
			content = self.reVor.sub('',response.body_as_unicode())
			
			logging.info("Ergebnisseite: "+content)

			werte=self.reAll.findall(content)
			i=0
			for wert in werte:
				logging.info("Wert " +str(i)+": "+ wert)
				i=i+1

			brauchbar=True
			kammer=werte[3]
			id_=werte[5]
			titel=werte[6]
			num=werte[7]
			entscheiddatum=werte[8]
			leitsatz=werte[9]
			rechtsgebiet=werte[13]
			publikationsdatum=werte[len(werte)-1]
			if self.reDatum.fullmatch(publikationsdatum)==None: publikationsdatum=werte[len(werte)-2]
			
			if len(kammer)<11:
				logging.warning("Type mismatch keine Kammer '"+kammer+"'")
				kammer=""
			if self.reID.fullmatch(id_)==None:
				logging.warning("Type mismatch keine ID '"+id_+"'")	
				brauchbar=False
			if len(titel)<11:
				logging.warning("Type mismatch keine Titel '"+titel+"'")
				titel=""	 
			if self.reNum.fullmatch(num)==None:
				logging.warning("Type mismatch keine Geschäftsnummer '"+num+"'")
				brauchbar=False
			if self.reDatum.fullmatch(entscheiddatum)==None:
				logging.warning("Type mismatch keine Entscheiddatum '"+entscheiddatum+"'")
				brauchbar=False
			if len(leitsatz)<11:
				if leitsatz != '-':
					logging.warning("Type mismatch kein Leitsatz '"+leitsatz+"'")
				leitsatz=""
			if self.reRG.fullmatch(rechtsgebiet)==None:
				logging.warning("Type mismatch kein Rechtsgebiet '"+rechtsgebiet+"'")
				rechtsgebiet=""			   
			if self.reDatum.fullmatch(publikationsdatum)==None:
				logging.warning("Type mismatch letzter und vorletzter Eintrag kein Publikationsdatum '"+publikationsdatum+"'")
				publikationsdatum=""

			if brauchbar:
				numstr = num.replace(" ", "_")
				href = self.PDF_PATTERN.format(self.DOWNLOAD_URL, numstr, id_,self.PDF_PATH, id_, numstr)
				yield {
					'Kanton': 'Bern',
					'Zweig': self.GERICHTSZWEIG,
					'Num':num ,
					'Kammer':kammer,
					'EDatum': entscheiddatum,
					'PDatum': publikationsdatum,
					'Titel': titel,
					'Leitsatz': leitsatz,
					'Rechtsgebiet': rechtsgebiet,
					'DocId':id_,
					'PDFUrl': [href],
					'Raw': content
				}

				if self.page_nr < min(self.trefferzahl, self.MAX_PAGES):
					body = self.get_next_request()
					yield scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)
		else:
			logging.error("ungültige Antwort")
			
			
	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))

 