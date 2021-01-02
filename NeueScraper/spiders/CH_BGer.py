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

class CH_BGer(BasisSpider):
	name = 'CH_BGer'
	TAGSCHRITTE = 20
	AUFSETZTAG = "01.01.2000"
	DELTA=datetime.timedelta(days=TAGSCHRITTE-1)
	EINTAG=datetime.timedelta(days=1)

	SUCH_URL='/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=simple_query&query_words=&top_subcollection_aza=all&from_date={von}&to_date={bis}&x=22&y=14'
	HOST='https://www.bger.ch'
	

	def mache_request(self,von="",bis="",seite=1):
		if seite:
			page="&page="+str(seite)
		else:
			page=""
		request = scrapy.Request(url=self.HOST+self.SUCH_URL.format(von=von,bis=bis)+page, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite, 'von': von, 'bis': bis})
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
	
	def __init__(self, ab=None):
		super().__init__()
		# Hier stehen immer nur die neuen Entscheide. Daher nie gesamt holen und austauschen.
		self.ab=ab
		self.request_gen = self.request_generator(ab)


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
	
		treffer=int(response.xpath("//div[@class='content']/div[@class='ranklist_header center']/text()").get().strip().split(" ")[0])
		anfangsposition=int(response.xpath("//div[@class='ranklist_content']/ol/@start").get())
		urteile=response.xpath("//div[@class='ranklist_content']/ol/li")

		logger.info("Liste von {} Urteilen. Start bei {} von {} Treffer".format(len(urteile),anfangsposition, treffer))
		
		for entscheid in urteile:
			item={}
			text=entscheid.get()
			meta=entscheid.xpath("./span/a/text()").get()
			item['HTMLUrls']=[entscheid.xpath("./span/a/@href").get()]
			titel=entscheid.xpath("./div/div[3]/text()").get()
			if titel:
				item['Titel']=titel.strip()
			item['VKammer']=PH.NC(entscheid.xpath("./div/div[1]/text()").get(), warning="Kammerzeile nicht geparst: "+text)
			item['Rechtsgebiet']=PH.NC(entscheid.xpath("./div/div[2]/text()").get(), warning="Rechtsgebietszeile nicht geparst: "+text)
			
			if self.reDatum.search(meta) is None:
				logger.error("Konnte Datum in meta nicht erkennen: "+meta)
			else:
				item['EDatum']=self.norm_datum(meta)
				item['Num']=meta[11:]
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])
				request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
				yield request
		if anfangsposition+len(urteile)<treffer:
			request=self.mache_request(response.meta['von'],response.meta['bis'],response.meta['page']+1)
			yield request			

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
