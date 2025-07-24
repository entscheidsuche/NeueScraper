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
	suchseiten={ "BE_VB_002": ['https://www.bkd.be.ch','https://www.bkd.be.ch/de/start/ueber-uns/die-organisation/bkd-generalsekretariat/rechtsdienst-bkd/ausgewaehlte-beschwerdeentscheide.html','table'],
				"BE_VB_003": ['https://www.gsi.be.ch','https://www.gsi.be.ch/de/start/ueber-uns/generalsekretariat/rechtsabteilung/rechtsprechung.html','table'],
				"BE_VB_004": ['https://www.gba.dij.be.ch/content','https://ktbe.jaxforms.com/formservice/services/rest/generic/json?handler=jaxGenericDataPoolHandler&language=de&paging=false&id=77e7438e-f9c8-4e73-9302-bbfec0ad04b3&displayID=standard','list1']}

	reMeta=re.compile(r"(?P<art>[^\s]+)\s(?P<num>[A-Z0-9\.\-\s]+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	reMetaOhne=re.compile(r"(?P<art>.+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	reMetaZusatz=re.compile(r"vgl\.\s(?P<art>[^\s]+)\s(?P<num>[A-Z0-9\.\- ]+)\svom\s(?P<datum>\d+\.\s(?:"+"|".join(BasisSpider.MONATEde)+")\s(?:19|20)\d\d)")
	
	
# https://ktbe.jaxforms.com/formservice/services/rest/generic/json?handler=jaxGenericDataPoolHandler&language=de&paging=false&id=77e7438e-f9c8-4e73-9302-bbfec0ad04b3&displayID=standard
# https://ktbe.jaxforms.com/formservice/services/rest/generic/json;jsessionid=A6A98D460DC0A3B70AB4B29CB17AF10C.4000patc2?handler=jaxGenericDataPoolHandler&language=de&paging=false&id=77e7438e-f9c8-4e73-9302-bbfec0ad04b3&displayID=standard
# https://www.gba.dij.be.ch/content/dam/gba_dij/dokumente/de/entscheide/Beschwerdeentscheid%202021.DIJ.4477%2022.09.2022.pdf
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		request_liste=[]
		for g in self.suchseiten:
			request_liste.append(scrapy.Request(url=self.suchseiten[g][1], callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'signatur': g, 'host': self.suchseiten[g][0], 'typ': self.suchseiten[g][2]}))		
		return request_liste

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" URL:"+response.request.url)
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		
		signatur=response.meta['signatur']
		host=response.meta['host']
		typ=response.meta['typ']
		if typ=="table":
			entscheide=response.xpath("//div[@data-testid='table']/table[@cellspacing='1']/tbody/tr[th[not(@scope='col')] and not(th[2])]")
		elif typ=="list1":
			struktur=json.loads(antwort)
			entscheide=struktur['results']
		else:
			logger.error("Unbekannter typ: "+typ+", Host: "+host)

		trefferzahl=len(entscheide)
		logger.info(str(trefferzahl)+" Entscheide für "+signatur)
		for e in entscheide:
			item={}
			if typ=="table":
				text=e.get()
				logger.info("Treffertext: "+text)
				edatum=PH.NC(e.xpath("string(./th[1])").get(), error="Kein E-Datum gefunden in ("+signatur+"): "+text)
				item['EDatum']=self.norm_datum(edatum)
				item['Num']=PH.NC(e.xpath("normalize-space(string(./td[1]//a[1]))").get(),error="Keine Geschäftsnummer in ("+signatur+"): "+text)
				url=PH.NC(e.xpath("./td[1]//a[1]/@href").get(), error="Keine URL zu PDF-Dokument in ("+signatur+"): "+text)
				item['Titel']=PH.NC(e.xpath("normalize-space(string(./td[2]//text()))").get(), warning="kein Titel in ("+signatur+"): "+text)
			elif typ=="list1":
				text=json.dumps(e)
				logger.info("Treffertext: "+text)
				url=PH.NC(host+e['DateiName'], error="Keine URL zu PDF-Dokument in ("+signatur+"): "+text)
				edatum=PH.NC(e['Datum'], error="Kein E-Datum gefunden in ("+signatur+"): "+text)
				item['EDatum']=self.norm_datum(edatum)
				item['Num']=PH.NC(e['EntscheidNr'],error="Keine Geschäftsnummer in ("+signatur+"): "+text)
				item['Rechtsgebiet']=e['Thema_de']
				item['Abstract_de']=e['Kurzbeschrieb_de']
				item['Abstract_fr']=e['Kurzbeschrieb_fr']

			if url[:4]=="http":
				item['PDFUrls']=[url]
			else:
				item['PDFUrls']=[host+url]
			item['Signatur']=signatur
			item['Gericht'], item['Kammer']=self.detect_by_signatur(signatur)
			logger.info("Item gelesen: "+json.dumps(item))
			yield item
