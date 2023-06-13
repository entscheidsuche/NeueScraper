# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import datetime
import json
from NeueScraper.spiders.basis import BasisSpider

logger = logging.getLogger(__name__)

class ZH_OG(BasisSpider):
	name = 'ZH_Obergericht'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	#RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum}&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum_ab}&entscheiddatum_bis={datum_bis}&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	PDF_BASE='https://www.gerichte-zh.ch'
	TAGSCHRITTE = 500
	AUFSETZTAG = "01.01.1980"
	DELTA=datetime.timedelta(days=TAGSCHRITTE-1)
	EINTAG=datetime.timedelta(days=1)



	def mache_request(self, ab, bis):
		request = scrapy.Request(url=self.RESULT_PAGE_URL.format(datum_ab=ab, datum_bis=bis), callback=self.parse_page, errback=self.errback_httpbin)
		return request		

	def request_generator(self,ab=None):
		requests=[]
		if ab is None:
			requests=[self.mache_request("",self.AUFSETZTAG)]
			von=(datetime.datetime.strptime(self.AUFSETZTAG,"%d.%m.%Y")+self.EINTAG).date()
		else:
			von=datetime.datetime.strptime(ab,"%d.%m.%Y").date()
		heute=datetime.date.today()
		while von<heute:
			bis=von+self.DELTA
			requests.append(self.mache_request(von.strftime("%d.%m.%Y"),bis.strftime("%d.%m.%Y")))
			von=bis+self.EINTAG
		return requests

	def __init__(self,ab=None,neu=None):
		super().__init__()
		self.ab = ab
		self.neu = neu
		self.request_gen = self.request_generator(ab)

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logging.debug("Rohergebnis "+str(len(response.body))+" Zeichen")
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
						vkammer = details.xpath(""".//p[span/text()="Abteilung/Kammer"]/span[2]/text()""").get()
						if vkammer is None:
							vkammer = ""
							logging.warning("keine Kammer gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						EDatum = details.xpath(""".//p[span/text()="Entscheiddatum"]/span[2]/text()""").get()
						if EDatum is None:
							brauchbar = False
							logging.error("keine Entscheiddatum gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						Titel = entscheid.xpath("./p/strong/text()").get()
						if Titel is None:
							Titel = ""
							logging.warning("kein Titel gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
						vgericht = details.xpath(""".//p[span/text()="Gericht/Behörde"]/span[2]/text()""").get()
						if vgericht is None:
							vgericht=""
							logging.warning("kein Gericht / keine Gerichtsbarkeit gefunden für Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
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
							signatur, gericht, kammer=self.detect(vgericht,vkammer,Num)
				
							vgericht=gericht
							if vkammer=='':
								vkammer=kammer
							if vgericht=='':
								vgericht=gericht
							edatum=self.norm_datum(EDatum)
							item = {
								'Kanton': self.kanton_kurz,
								'Num': Num ,
								'Kammer': kammer,
								'VKammer': vkammer,
								'Gericht': gericht,
								'VGericht': vgericht,
								'EDatum': edatum,
								'Titel': Titel,
								'DocId': idE,
								'Weiterzug': Weiterzug,
								'Entscheidart': Entscheidart,
								'Raw': Raw,
								'PDFUrls': [PDFUrl],
								'Signatur': signatur
							}
							logger.info("Eintrag: "+json.dumps(item))
							if self.check_blockliste(item):
								yield(item)
						else:
							logging.error("Entscheid wird wegen fehlender Angaben ignoriert, Dokument-ID: "+idE+" Geschäftsnummer: "+Num+" Raw: "+Raw)
							
