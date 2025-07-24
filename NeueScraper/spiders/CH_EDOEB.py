# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
import urllib

logger = logging.getLogger(__name__)


class CH_EDOEB(BasisSpider):
	name = 'CH_EDOEB'

	URLs=[{'URL':"/de/empfehlungen-nach-bgo",'Kammer':'BGÖ','Typ':'Liste'},{'URL':"/de/schlussberichte-empfehlungen-bis-31082023",'Kammer':'DSG','Typ':'Liste'},{'URL':'/de/weiterzuege-bis-31082023','Kammer':'Weiterzüge-DSG','Typ':'Liste'}]
	HOST="https://www.edoeb.admin.ch"
	custom_settings = {
		"CONCURRENT_REQUESTS_PER_DOMAIN": 1,
		"DOWNLOAD_DELAY": 2
	}

	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+entry['URL'],callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'entry':entry}) for entry in self.URLs]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+response.request.url+" "+str(response.status))
		antwort=response.text
		entry=response.meta['entry']
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen, Typ: "+entry['Typ']+", Kammer: "+entry['Kammer'])
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		if entry['Typ']=='Liste':
			strukturtext=PH.NC(response.xpath("//script[@id='__NUXT_DATA__']/text()").get(),error="keine Struktur NUXT_DATA gefunden")
			struktur=json.loads(strukturtext)
			findtext=entry['URL'][1:]+".json"

			logger.info("Array mit "+str(len(struktur))+" Elementen")

			startpunkte=[i for i, x in enumerate(struktur) if isinstance(x, dict) and findtext in x]

			logger.info("Gefundene mögliche Startpunkte: "+json.dumps(startpunkte))
			if not startpunkte:
				logger.error("keine Startpunkte gefunden für: "+findtext)
			else:
				startpunkt=startpunkte[0]
				weiter1=struktur[startpunkt][findtext]
				logger.info("weiter1: "+str(weiter1))
				weiter2=struktur[weiter1]["content"]
				logger.info("weiter2: "+str(weiter2))
				weiter3=struktur[weiter2][1]
				logger.info("weiter3: "+str(weiter3))
				weiter4=struktur[weiter3]['nestedContent']
				logger.info("weiter4: "+str(weiter4))
				for weiter5 in struktur[weiter4]:
					logger.info("weiter5 Variante: "+str(weiter5))
					if "nestedContent" in struktur[weiter5]:
						weiter6=struktur[weiter5]['nestedContent']
						logger.info("weiter6: "+str(weiter6))
						for weiter7 in struktur[weiter6]:
							logger.info("weiter7 Variante: "+str(weiter7))
							if "properties" in struktur[weiter7]:
								weiter8=struktur[weiter7]['properties']
								logger.info("weiter8: "+str(weiter8))
								if "listItems" in struktur[weiter8]:
									logger.info("weiter8: "+str(weiter8))
									weiter9=struktur[weiter8]['listItems']
									logger.info("weiter9: "+str(weiter9))
									liste=struktur[weiter9]
									logger.info("Liste gefunden: "+json.dumps(liste))
									for eintrag in liste:
										item={}
										item["Num"]=PH.NC(struktur[struktur[eintrag]["fileName"]],error="kein fileName gefunden für "+json.dumps(eintrag))
										if item['Num'].lower().endswith(".pdf"):
											item['Num']=item['Num'][:-4]
										item["noNumDisplay"]=True
										meta=struktur[eintrag]["metainfos"]
										for i in struktur[meta]:
											if "originalDate" in struktur[i]:
												item["EDatum"]=PH.NC(self.norm_datum(struktur[struktur[i]["info"]]),warning="kein gültiges Datumsformat gefunden")
										item["PDFUrls"]=[PH.NC(struktur[struktur[eintrag]["link"]],error="kein PDF-Link gefunden für: "+item["Num"])]
										item["Titel"]=PH.NC(struktur[struktur[eintrag]["text"]],error="kein Titel gefunden für: "+item["Num"])
										item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",entry['Kammer'],"")
										logger.info("Eintrag: "+json.dumps(item))
										yield item

"""
		elif entry['Typ']=='Berichte':
			strukturtext=PH.NC(response.xpath("//script[@id='__NUXT_DATA__']/text()").get(),error="keine Struktur NUXT_DATA gefunden")
			struktur=json.loads(strukturtext)
			doc_grid_indices = [i for i, x in enumerate(struktur) if isinstance(x, str) and x=="dynamic-file-teaser"]
			matching_dicts = [i for i, x in enumerate(struktur) if isinstance(x, dict) and x.get("identifier") in doc_grid_indices]
			logger.info("matching_dicts: "+json.dumps(matching_dicts))
			if len(matching_dicts)==0:
				logger.error("keine Berichtslite gefunden")
			elif len(matching_dicts)>1:
				logger.warning("mehr als eine Berichtsliste gefunden: "+str(len(matching_dicts)))
			else:
				berichte=struktur[struktur[struktur[matching_dicts[0]]['properties']]['listItems']]
				logger.info(str(len(berichte))+" Berichte ("+entry['Kammer']+") gefunden.")
				for bericht in berichte:
					item={}
					properties=struktur[bericht]
					item['Titel']=struktur[properties['text']].strip()
					logger.info("properties: "+json.dumps(struktur[properties]))
					metadaten=struktur[struktur[properties]['metainfos']]
					logger.info("Metadaten: "+json.dumps(metadaten))
					datumsstrings=[struktur[i]['originalDate'] for i in metadaten if 'originalDate' in struktur[i]]
					logger.info("datumsstrings: "+json.dumps(datumsstrings))
					item['PDatum']=self.norm_datum(datumsstrings[0][:10], warning="Kein EDatum identifiziert")
					item['EDatum']=self.norm_datum(struktur[properties['updatedAt']][:10], warning="Kein PDatum identifiziert")
					item['PDFUrls']=[struktur[properties['link']]]
					item['Num']=''
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",entry['Kammer'],"")
					logger.info("text Lege PDF-Dokument ab: "+json.dumps(item))
					yield item
		else:
			logger.error(entry['Typ']+" nicht verarbeitet")

	def parse_html(self, response):
		logger.info("parse_html response.status "+response.request.url+" "+str(response.status))
		antwort=response.text
		logger.info("parse_html Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_html Rohergebnis: "+antwort[:80000])
		
		item=response.meta['item']
		entry=response.meta['entry']
		html=""
		
		if entry['Typ']=="Presse":	
			item['Titel']=PH.NC(response.xpath('//div[@class="contentHead"]/h1/text()').get(),replace=item['Titel'],warning="Kein Titel in "+antwort)
		
			html=response.xpath('//div[@class="contentHead"]/h1')
			html+=response.xpath('//div[@class="mod mod-nsbnewsdetails"]/*')

		elif entry['Typ']=='Meldungen':
			html=response.xpath('//main[@id="main-content"]/*')

		else:			
			logger.error("unbekannter html-typ: "+entry['Typ'])
			
		if html == []:
			logger.error("Content nicht erkannt in "+antwort[:20000])
		else:
			htmltext=""
			for element in html:
				htmltext+=element.get()
			PH.write_html(htmltext, item, self)
			yield(item)
"""