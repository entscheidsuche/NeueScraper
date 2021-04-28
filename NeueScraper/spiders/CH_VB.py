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

	URL="/execQuery.do?context=results&searchMode=simple&queryString=&daterange_from={von}&daterange_to={bis}&selectedDruckschrifttypen=VPB&selectAll=false&selectedDruckschrifttypen=false&fetchCount=1000"
	HOST="https://www.amtsdruckschriften.bar.admin.ch"
	STARTDATE="01.01.1982"
	ENDDATE="31.12.2016"
	TAGSCHRITTE = 15
	DELTA=datetime.timedelta(days=TAGSCHRITTE-1)
	EINTAG=datetime.timedelta(days=1)
	
	reTreffer = re.compile(r'(?P<von>\d+)\s+à\s+(?P<bis>\d+)\s+sur\s+(?P<toomany>les\s+)?(?P<gesamt>\d+)')
	reZiffer = re.compile(r'\d+')

	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		self.ab=ab
		if ab is None:
			ab=self.STARTDATE
		
		self.request_gen = self.request_generator(ab, self.ENDDATE)

	def request_generator(self, start, ende):
		logger.info("Generiere Requests von "+start+" bis "+ende)
		von=datetime.datetime.strptime(start,"%d.%m.%Y").date()
		fertig=datetime.datetime.strptime(ende,"%d.%m.%Y").date()
		requests=[]
		while von<=fertig:
			bis=von+self.DELTA
			bisstring=bis.strftime("%d.%m.%Y")
			vonstring=von.strftime("%d.%m.%Y")
			requests.append(scrapy.Request(url=self.HOST+self.URL.format(von=vonstring, bis=bisstring), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={"range": vonstring+"-"+bisstring}))
			von=bis+self.EINTAG
		return requests

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" für "+response.request.url)
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		noresult=response.xpath("//span[@class='docsNone']")
		if noresult:
			logger.info("kein Treffer im Zeitraum "+response.meta['range'])
		else:
			Cookie=""
			if 'Set-Cookie' in response.headers:
				logger.info("parse_trefferliste Cookie erhalten: "+response.headers['Set-Cookie'].decode('UTF-8'))
				Cookie=response.headers['Set-Cookie'].decode('UTF-8').split(";")[0]
			else:
				logger.info("In der Trefferlistenresponse gibt es keine Cookies.")

			urteile=response.xpath("//tr[@class='docsRow']")
			oneresult=response.xpath("//nav[@class='pagination-container clearfix']/span/text()[contains(.,'1 Résultat')]")
			if oneresult:
				trefferVon=1
				trefferBis=1
				trefferGesamt=1
			else:
				resulttext=response.xpath("//div[preceding-sibling::table]/nav[@class='pagination-container clearfix']/span/a[@href='showPrefs.do']/text()")[0].get()
				resultmatch=self.reTreffer.search(resulttext)
				if resultmatch:
					trefferVon=int(resultmatch.group("von"))
					trefferBis=int(resultmatch.group("bis"))
					trefferGesamt=int(resultmatch.group("gesamt"))
					if resultmatch.group("toomany"):
						logger.error("Nicht alle Entscheide bei Zeitraum "+response.meta['range']+". Meldung "+resulttext)
				else:
					logger.error("Konnte resultstring nicht matchen für "+response.meta['range']+". Meldung "+resulttext)				
			if not(len(urteile)==trefferBis-trefferVon+1):
				logger.error("Trefferzahlen passen nicht: Ergebnisse in Liste: "+str(len(urteile))+" für "+resulttext+" und Zeitraum "+response.meta['range'])
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				detailurl=entscheid.xpath(".//a[@class='docsTitleLink']/@href").get()
				pdfurl=entscheid.xpath(".//a[img[@src='images/icons/c_launch_pdf.gif']]/@href").get()
				item['PDFUrls']=[self.HOST+"/"+pdfurl]
				item['VKammer']=PH.NC(entscheid.xpath(".//td[a[@target='_blank']]/preceding-sibling::td[1]/text()").get(),error="Keine Kammer gefunden")
				request=scrapy.Request(url=self.HOST+"/"+detailurl, callback=self.parse_detail, errback=self.errback_httpbin, meta={"item": item})
				if Cookie:
					request.headers['Cookie']=Cookie.encode('UTF-8')
					logger.info("Cookie gesetzt: "+Cookie)
				yield request

	def parse_detail(self, response):
		logger.info("parse_detail response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_detail Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_detail Rohergebnis: "+antwort[:200000])
	
		item=response.meta['item']

		metabereich=response.xpath("//table[@class='metadataTable']")
		if metabereich:
			metas=metabereich.xpath("./tr[@class='docsRow']/td[@class='metadataCell']")
			item['Title']=PH.NC(metas[0].xpath("./text()").get(),error="Kein Titel gefunden")
			item['VGericht']=PH.NC(metas[1].xpath("./text()").get(),error="Kein Gericht gefunden")
			item['EDatum']=self.norm_datum(PH.NC(metas[6].xpath("./a[@class='high']/text()").get(),error="Kein Datum gefunden"))
			pretext=PH.NC(response.xpath("//pre/text()").get(), error="Kein pre-Text gefunden")
			logger.info("pretext-Beginn: "+pretext[:100])
			nums=pretext.split("\n",5)
			for num in nums:
				if len(num)>=4 or len(num)<=20:
					if self.reZiffer.search(num):
						break
	
			if len(num)<4 or len(num)>20:
				num=PH.NC(metas[9].xpath("./text()").get(),error="keine Ersatznum gefunden")
			item['Num']=num
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],item['VKammer'],item['Num'])
			logger.info("gelesen Item: "+json.dumps(item))
			yield item
