# -*- coding: utf-8 -*-
import scrapy
import re
import logging


class BernStrkSpider(scrapy.Spider):
	name = 'bern_steuerrekurs'
	allowed_domains = ['www.strk-entscheide.apps.be.ch']
	start_urls = ['https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable']
	
	RESULT_PAGE_URL = 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	RESULT_QUERY_TPL = r'''7|0|62|https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|StRK|0;false|5;true|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Reports\\Export_1596162913203|reportname|Export_1596162913203|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Sachgebiet|shortText|Vorschautext|department|Spruchkörper|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|-17|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|10|62|10|10|11|11|0|'''
	RESULT_QUERY_TPL_AB = ''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '1ABD52BDF54ACEC06A4E0EEDA12D4178'
			  , 'X-GWT-Module-Base': 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/'
			  }
	MINIMUM_PAGE_LEN = 148
	DOWNLOAD_URL = 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/ServletDownload/'
	MAX_PAGES = 1000
	reVor=re.compile('//OK\\[[0-9,\\.]+\\[')
	reAll=re.compile('(?<=,\\")[^\\"]*(?:\\\\\\"[^\\"]*)*(?=\\",)')
	reID=re.compile('[0-9a-f]{32}')
	reNum=re.compile('\d{1,3}\s(19|20)\d\d\s\d+')
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
				path_ = 'E%3A%5C%5Cwebapps%5C%5Ca2y%5C%5Ca2ya-www-trbpub700web%5C%5Cpdf%5C'
				href = "{}{}_{}.pdf?path={}{}.pdf&dossiernummer={}".format(self.DOWNLOAD_URL, numstr, id_,path_, id_, numstr)
				yield {
					'Kanton': 'Bern',
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

 