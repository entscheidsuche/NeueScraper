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


class CH_WEKO(BasisSpider):
	name = 'CH_WEKO'

	# URL="/weko/de/home/praxis/publizierte-entscheide.html"
	URL="/de/entscheide"
	HOST="https://www.weko.admin.ch"
	
	custom_settings = {
		"COOKIES_ENABLED": True,
		"COOKIES_DEBUG": True,   # optional
		"DOWNLOAD_DELAY": 4,
		"CONCURRENT_REQUESTS_PER_DOMAIN": 2,
		"AUTOTHROTTLE_ENABLED": True,
		"AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
	}
	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+self.URL,callback=self.parse_trefferliste, errback=self.errback_httpbin)]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		# urteile=response.xpath("//ul/li/a[@class='download-item']")
		urteile=response.xpath("//ul/li[a[@class='download-item']]")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['Gericht'])
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./a/@href").get()
				item['PDFUrls']=[url]
				meta=entscheid.xpath("./a/div/h4[@class='download-item__title']/text()").get()
				metas=meta.split(": ",1)
				if len(metas)>1:
					metas2=metas[1].split(" vom ")
					if len(metas2)==1:
						metas2=metas[1].split(" du ")
					if len(metas2)==1:
						metas2=metas[1].split(" del ")
					if len(metas2)>1:
						edatum=self.norm_datum(metas2[1], warning="Kein Datum identifiziert")
						item['Entscheidart']=metas2[0]
					else:
						edatum=self.norm_datum(metas[1], warning="Kein Datum identifiziert")
					item['Titel']=metas[0]
					item['Num']=metas[0]
				else:
					metas2=meta.split(" vom ")
					if len(metas2)==1:
						metas2=meta.split(" du ")
					if len(metas2)==1:
						metas2=meta.split(" del ")
					if len(metas2)>1:
						edatum=self.norm_datum(metas2[1], warning="Kein Datum identifiziert")
						item['Num']=metas2[0]
					else:
						edatum=self.norm_datum(meta, warning="Kein Datum identifiziert")
						item['Num']=meta
				publiziert=entscheid.xpath("./a/div/p/span[@class='meta-info__item'][last()]/text()")
				if publiziert:
					item['PDatum']=self.norm_datum(publiziert.get(), warning=f"Kein Publikationsdatum in {publiziert}")
				if edatum!="nodate":
					item['EDatum']=edatum
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				logger.info(f"Entscheid gelesen: {json.dumps(item)}")
				yield item
