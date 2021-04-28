# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class BE_Weitere(BasisSpider):
	name = 'BE_Weitere'

	HOST ="https://www.gef.be.ch"
	suchseiten={ "BE_VB_002": ['https://www.erz.be.ch','/erz/de/index/direktion/organisation/generalsekretariat/rechtsdienst_dererziehungsdirektion/Beschwerdeentscheide.html','table'],
				"BE_VB_003": ['https://www.gef.be.ch','/gef/de/index/direktion/organisation/ra/RechtsprechungGEF.html','table'],
				"BE_VB_004": ['https://www.jgk.be.ch','/jgk/de/index/direktion/organisation/gba/entscheide/grundbuchrecht_im_engeren_sinne.html','list1'],
				"BE_VB_005": ['https://www.jgk.be.ch','/jgk/de/index/direktion/organisation/gba/entscheide/grundbuchgebuehren.html','list1'],
				"BE_VB_006": ['https://www.jgk.be.ch','/jgk/de/index/direktion/organisation/gba/entscheide/handaenderungssteuern.html','list1'],
				"BE_NAB_001": ['https://www.jgk.be.ch','/jgk/de/index/aufsicht/notariat/Entscheide/Administrativentscheide.html','list2'],
				"BE_NAB_002": ['https://www.jgk.be.ch','/jgk/de/index/aufsicht/notariat/Entscheide/Moderationsentscheide.html','list2'],
				"BE_NAB_003": ['https://www.jgk.be.ch','/jgk/de/index/aufsicht/notariat/Entscheide/Disziplinarentscheide.html','list1']}
		
	reMeta=re.compile(r"(?P<art>[^\s]+)\s(?P<num>[A-Z0-9\.\-\s]+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	reMetaOhne=re.compile(r"(?P<art>.+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	reMetaZusatz=re.compile(r"vgl\.\s(?P<art>[^\s]+)\s(?P<num>[A-Z0-9\.\- ]+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		request_liste=[]
		for g in self.suchseiten:
			request_liste.append(scrapy.Request(url=self.suchseiten[g][0]+self.suchseiten[g][1], callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'signatur': g, 'host': self.suchseiten[g][0], 'typ': self.suchseiten[g][2]}))		
		return request_liste

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" URL:"+response.request.url)
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		
		signatur=response.meta['signatur']
		host=response.meta['host']
		typ=response.meta['typ']
		if typ=="table":
			entscheide=response.xpath("//table[@cellspacing='0' and thead]/tbody/tr")
		elif typ=="list1":
			entscheide=response.xpath("//div[@class='textBild floatingComponent section']/ul/li")
		else:
			entscheide=response.xpath("//div[@class='linkliste parsys section']/ul/li")

		trefferzahl=len(entscheide)
		logger.info(str(trefferzahl)+" Entscheide für "+signatur)
		for e in entscheide:
			item={}
			text=e.get()
			if typ=="table":
				edatum=PH.NC(e.xpath("./td[1]/text()").get(), error="Kein E-Datum gefunden in ("+signatur+"): "+text)
				item['EDatum']=self.norm_datum(edatum)
				item['Num']=PH.NC(e.xpath("./td[2]/a/text()").get(),error="Keine Geschäftsnummer in ("+signatur+"): "+text)
				url=PH.NC(e.xpath("./td[2]/a/@href").get(), error="Keine URL zu PDF-Dokument in ("+signatur+"): "+text)
				item['Titel']=PH.NC(e.xpath("./td[3]//text()").get(), warning="kein Titel in ("+signatur+"): "+text)
				
			else:
				if typ=="list1":
					meta=PH.NC(e.xpath("./strong/text()").get(), warning="Metastring nicht gefunden in ("+signatur+"): "+text)
					item['Titel']=PH.NC(e.xpath(".//a/text()").get(), warning="kein Titel in ("+signatur+"): "+text)
				else:
					meta=PH.NC(e.xpath(".//h3/text()").get(), warning="Metastring nicht gefunden in ("+signatur+"): "+text)
					item['Titel']=PH.NC(e.xpath("./span[@class='info linkinfo']/text()[1]").get(), warning="Titel nicht gefunden in ("+signatur+"): "+text)
				metamatch=self.reMeta.match(meta)
				if metamatch:
					item['Num']=PH.NC(metamatch.group('num'), error="Keine Geschäftsnummer in meta: "+meta+", in ("+signatur+"): "+text)
					item['EDatum']=self.norm_datum(PH.NC(metamatch.group('datum'), error="Kein Datum in meta: "+meta+", in ("+signatur+"): "+text))
					item['Entscheidart']=PH.NC(metamatch.group('art'), warning="Keine Entscheidart in meta: "+meta+", in ("+signatur+"): "+text)
				else:
					zusatz=e.xpath("./text()")
					metamatchohne=self.reMetaOhne.search(meta)
					if metamatchohne is None:
						logger.error("Metastring '"+meta+"' matched nicht, und metastring matched auch nicht einfachen Regex in ("+signatur+") für: "+text)
					else:
						item['EDatum']=self.norm_datum(PH.NC(metamatchohne.group('datum'), error="Kein Datum in meta (ohne): "+meta+", in ("+signatur+"): "+text))
						item['Entscheidart']=PH.NC(metamatchohne.group('art'), warning="Keine Entscheidart in meta (ohne): "+meta+", in ("+signatur+"): "+text)
						if len(zusatz)>1:
							zusatztext=zusatz[len(zusatz)-1].get()
							zusatzmatch=self.reMetaZusatz.search(zusatztext)
							if zusatzmatch:
								item['Num']=PH.NC(zusatzmatch.group('num'), error="Keine Geschäftsnummer in zusatz: "+zusatztext+", in ("+signatur+"): "+text)
							else:
								logger.warning("Metastring '"+meta+"' matched nicht, Zusatz vorhanden, aber zusatzstring '"+zusatztext+"' matched auch nicht in ("+signatur+") für: "+text)
								item['Num']=''
						else:
							logger.warning("Metastring nicht gegen regexgematched: '"+meta+"' und kein Zusatzstring in ("+signatur+"): "+text)
							item['Num']=''
				url=PH.NC(e.xpath(".//a/@href").get(), error="Keine URL zu PDF-Dokument in ("+signatur+"): "+text)

			item['PDFUrls']=[host+url]
			item['Signatur']=signatur
			item['Gericht'], item['Kammer']=self.detect_by_signatur(signatur)
			logger.info("Item gelesen: "+json.dumps(item))
			yield item
