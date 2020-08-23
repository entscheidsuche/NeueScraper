# -*- coding: utf-8 -*-
import scrapy
import re
import logging

class ZurichOGSpider(scrapy.Spider):
	name = 'zurich_og'
	KANTON = 'Zürich'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	#RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum}&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum}&entscheiddatum_bis=31.12.2100&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	PDF_BASE='https://www.gerichte-zh.ch'
	AB_DEFAULT='01.01.1900'

	def request_generator(self):
		""" Generates scrapy frist request
		"""
		return [scrapy.Request(url=self.RESULT_PAGE_URL.format(datum=self.ab), callback=self.parse_page, errback=self.errback_httpbin)]

	def __init__(self,ab=AB_DEFAULT):
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
		logging.info("Rohergebnis "+str(len(response.body))+" Zeichen")
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			# construct and download document links
			anzahl=int(response.xpath("//div[@id='entscheideText']/strong/text()").get())
			logging.info(str(anzahl)+" Entscheide")
			entscheide=response.xpath("//div[starts-with(@class,'entscheid ')]")
			entscheiddetails=response.xpath("//div[starts-with(@class,'entscheidDetails ')]")
			if anzahl != len(entscheide) or anzahl != len(entscheiddetails):
				logging.error("Inkonsistente Zahl von Ergebnissen: "+str(len(entscheide))+" Entscheid-Elemente und "+str(len(entscheiddetails))+" Entscheiddetails.")
			else:
				for (entscheid, details) in zip(entscheide, entscheiddetails):
					idE=entscheid.xpath("substring-after(@class,'entscheid entscheid_nummer_')").get()
					idD=details.xpath("substring-after(@class,'entscheidDetails container_')").get()
					if idE != idD:
						logging.error("Entscheid und Entscheiddetails passen nicht zuammen. "+idE+", "+idD)
					else:
						logging.info("Dokument-ID: "+idE)
						Raw = entscheid.get()+details.get()
						brauchbar = True
						Num = details.xpath(""".//p[span/text()="Geschäftsnummer"]/span[2]/text()""").get()
						if Num is None:
							Num="undefined"
							logging.warning("keine Geschäftsnummer gefunden für Dokument-ID: "+idE+" Raw: "+Raw)
						Kammer = details.xpath(""".//p[span/text()="Abteilung/Kammer"]/span[2]/text()""").get()
						if Kammer is None:
							Kammer = ""
							logging.warning("keine Kammer gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						EDatum = details.xpath(""".//p[span/text()="Entscheiddatum"]/span[2]/text()""").get()
						if EDatum is None:
							brauchbar = False
							logging.error("keine Entscheiddatum gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						Titel = entscheid.xpath("./p/strong/text()").get()
						if Titel is None:
							Titel = ""
							logging.warning("kein Titel gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						Gerichtsbarkeit = details.xpath(""".//p[span/text()="Gericht/Behörde"]/span[2]/text()""").get()
						if Gerichtsbarkeit is None:
							Gerichtsbarkeit=""
							logging.warning("keine Gerichtsbarkeit gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						Weiterzug = details.xpath(""".//p[span/text()="Verweise"]/span[2]/text()""").get()
						if Weiterzug is None:
							Weiterzug = ""
							logging.info("kein Weiterzug gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						Entscheidart = details.xpath(""".//p[span/text()="Entscheidart"]/span[2]/text()""").get()
						if Entscheidart is None:
							Entscheidart = ""
							logging.warning("keine Entscheidart gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						PDFUrl=details.xpath(""".//a[@class="pdf-icon"]/@href""").get()
						if PDFUrl is None:
							brauchbar = False
							logging.error("keine PDFUrl gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						else:
							PDFUrl=self.PDF_BASE+PDFUrl
						
						if brauchbar:
							item = {
								'Kanton': self.KANTON,
								'Gerichtsbarkeit': Gerichtsbarkeit,
								'Num': Num ,
								'Kammer': Kammer,
								'EDatum': EDatum,
								'Titel': Titel,
								'DocId': idE,
								'Weiterzug': Weiterzug,
								'Entscheidart': Entscheidart,
								'Raw': Raw,
								'PDFUrl': [PDFUrl]
							}
							yield(item)
						else:
							logging.error("Entscheid wird wegen fehlender Angaben ignoriert, Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
							


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))
