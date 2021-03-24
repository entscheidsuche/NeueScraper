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

logger = logging.getLogger(__name__)

# Noch im Entwurfsstadium
# Standardmäßig nur 25 pro Seite und 100 insgesamt. Kann auf 50 pro Seite und 999 insgesamt hochgesetzt werden (Einstellungen)

class CH_VB(BasisSpider):
	name = 'CH_VB'

	URL="/execQuery.do?context=results&searchMode=simple&queryString=&daterange_from={von}&daterange_to={bis}&selectedDruckschrifttypen=VPB,false&selectAll=false"
	HOST="https://www.amtsdruckschriften.bar.admin.ch"
	STARTDATE="01.01.1982"
	ENDDATE="31.12.2016"
	TAGSCHRITTE = 15
	DELTA=datetime.timedelta(days=TAGSCHRITTE-1)
	EINTAG=datetime.timedelta(days=1)

	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		if ab==None:
			ab=self.STARTDATE
		
		self.request_gen = self.gen_requests(ab, self.ENDDATE)

	def gen_requests(self, start, ende):
		von=datetime.datetime.strptime(start,"%d.%m.%Y").date()
		fertig=datetime.datetime.strptime(ende,"%d.%m.%Y").date()
		requests=[]
		while von<fertig:
			bis=von+self.DELTA
			bisstring=bis.strftime("%d.%m.%Y")
			vonstring=von.strftime("%d.%m.%Y")
			requests.append(scrapy.Request(url=self.HOST+self.URL.format(von=vonstring, bis=bisstring), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={"range": vonstring+"-"+bisstring}))
			von=bis+self.EINTAG
		return requests

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		urteile=response.xpath("//div[@class='mod mod-download']/p")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['range'])
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./a/@href").get()
				item['PDFUrls']=[self.HOST+url]
				meta=entscheid.xpath("./a/@title").get()
				metas=meta.split(": ",1)
				if len(metas)>1:
					metas2=metas[1].split(" vom ")
					if len(metas2)>1:
						edatum=self.norm_datum(metas2[1], warning="Kein Datum identifiziert")
						item['Entscheidart']=metas2[0]
					else:
						edatum=self.norm_datum(metas[1], warning="Kein Datum identifiziert")
					item['Titel']=metas[0]
					item['Num']=metas[0]
				else:
					metas2=meta.split(" vom ")
					if len(metas2)>1:
						edatum=self.norm_datum(metas2[1], warning="Kein Datum identifiziert")
						item['Num']=metas2[0]
					else:
						edatum=self.norm_datum(meta, warning="Kein Datum identifiziert")
						item['Num']="unbekannt"					
				if edatum!="nodate":
					item['EDatum']=edatum
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				yield item
