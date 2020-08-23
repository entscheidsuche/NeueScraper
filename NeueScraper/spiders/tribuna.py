# -*- coding: utf-8 -*-
import scrapy
import re
import logging

class TribunaSpider(scrapy.Spider):
	name = 'tribuna_virtual'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	reVor=re.compile('//OK\\[[0-9,\\.]+\\[')
	reAll=re.compile('(?<=,\\")[^\\"]*(?:\\\\\\"[^\\"]*)*(?=\\",)')
	reID=re.compile('[0-9a-f]{32}|[0-9]{15,17}')
	reDatum=re.compile('\d{4}-\d{2}-\d{2}')
	reRG=re.compile('[^0-9\\.:-]{3}.{3,}')
	reTreffer=re.compile('(?<=^//OK\\[)[0-9]+')
	reDecrypt=re.compile('(?<=//OK\\[1,\\[")[0-9a-f]+')
	page_nr=0
	trefferzahl=0
	ENCRYPTED=False
	
	def get_next_request(self):
		logging.info("Hole Treffer Nr. "+str(self.page_nr))
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
			korrektur=0
			kammer=werte[3]
			if werte[4]!="": korrektur=-1
			id_=werte[5+korrektur]
			titel=werte[6+korrektur]
			num=werte[7+korrektur]
			entscheiddatum=werte[8+korrektur]
			leitsatz=werte[9+korrektur]
			pfad=werte[12+korrektur]
			rechtsgebiet=werte[13+korrektur]
			publikationsdatum=werte[len(werte)-1]
			if self.reDatum.fullmatch(publikationsdatum)==None: publikationsdatum=werte[len(werte)-2]
			
			if len(kammer)<11:
				logging.warning("Type mismatch keine Kammer '"+kammer+"'")
				kammer=""
			if self.reID.fullmatch(id_)==None:
				logging.error("Type mismatch keine ID '"+id_+"'")	
				brauchbar=False
			if len(titel)<11:
				logging.warning("Type mismatch keine Titel '"+titel+"'")
				titel=""	 
			if self.reNum.fullmatch(num)==None:
				logging.error("Type mismatch keine Geschäftsnummer '"+num+"'")
				brauchbar=False
			if self.reDatum.fullmatch(entscheiddatum)==None:
				logging.error("Type mismatch kein Entscheiddatum '"+entscheiddatum+"'")
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
				item = {
					'Kanton': self.KANTON,
					'Gerichtsbarkeit': self.GERICHTSBARKEIT,
					'Num':num ,
					'Kammer':kammer,
					'EDatum': entscheiddatum,
					'PDatum': publikationsdatum,
					'Titel': titel,
					'Leitsatz': leitsatz,
					'Rechtsgebiet': rechtsgebiet,
					'DocId':id_,
					'Raw': content
				}				
						
				if self.ENCRYPTED:
					body=self.DECRYPT_START+pfad+self.DECRYPT_END
					yield scrapy.Request(url=self.DECRYPT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.decrypt_path, errback=self.errback_httpbin, meta={"item":item})
				else:
					href = self.PDF_PATTERN.format(self.DOWNLOAD_URL, numstr, id_,self.PDF_PATH, id_, numstr)
					item['PDFUrl']=[href]
					yield item
			else:
				logging.error("Parse Fehler bei Treffer "+str(self.page_nr)+" String: "+content)

			if self.page_nr < min(self.trefferzahl, self.MAX_PAGES):
				body = self.get_next_request()
				yield scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)
		else:
			logging.error("ungültige Antwort")

	def decrypt_path(self, response):
		item=response.meta['item']
		logging.info("Decrypt-Path für DocID "+item['DocId'])
		if response.status == 200:
			logging.info("Rohergebnis Decrypt: "+response.body_as_unicode())
			code=self.reDecrypt.search(response.body_as_unicode())
			if code:
				numstr = item['Num'].replace(" ", "_")
				href=self.PDF_PATTERN.format(self.DOWNLOAD_URL,numstr,item['DocId'],code.group(),numstr)
				item['PDFUrl']=[href]
				yield item
			else:
				logging.error("Gecrypteter Pfad konnte nicht geparst werden.")
		else:
			logging.error("Keine Antwort für gecrypteten Pfad")
					
			
	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))

