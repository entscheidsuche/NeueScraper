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


class ZH_Baurekurs(BasisSpider):
	name = 'ZH_Baurekurs'

	HOST='https://www.baurekursgericht-zh.ch'
	URL='/rechtsprechung/entscheiddatenbank/volltextsuche/'
	FORM={ 'keywords': '', 'source': '2', 'datefrom': '', 'dateto': '', 'search_type':'2'}
	TREFFER_PRO_SEITE=10
	ab=None
	url=None
	apikey=None
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = [self.generate_request()]

	def generate_request(self, page=0):
		if self.ab:
			ab=self.ab
		else:
			ab=''
		form=copy.deepcopy(self.FORM)
		form['datefrom']=ab
		if page==0:
			form['search_type']='2'
		else:
			form['start']=str(self.TREFFER_PRO_SEITE*page)
		request= scrapy.FormRequest(url=self.HOST+self.URL, formdata=form, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': page})
		return request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		
		treffer=PH.NC(response.xpath('//div[@class="search-listing-head"]/div[@class="row"]/div[@class="col-6"][contains(.,"Entscheide")]/text()').get(),error="keine Trefferzahl in "+antwort)
		trefferzahl=int(treffer.split(" ")[0])
		page=response.meta['page']+1
		entscheide=response.xpath("//div[@class='search-listing']/div[@class='search-listing-items']/div[@class='search-listing-item']")
		logger.info(f"{len(entscheide)} Entscheide von {trefferzahl} auf Seite {page}")
		for entscheid in entscheide:
			text=entscheid.get()
			logger.info("Bearbeite Entscheid: "+text)
			item={}
			meta=PH.NC(entscheid.xpath("./div[@class='search-listing-item-number']/text()").get(),error="keine Metadaten in "+text)
			metas=meta.split(" vom ")
			if not(len(metas)==2):
				logger.error("Meta nicht zerlegbar: "+meta)
			else:
				item['Num']=metas[0]
				item['EDatum']=self.norm_datum(metas[1])
				item['Titel']=PH.NC(entscheid.xpath("./h4/text()").get(),warning="kein Titel bei: "+text)
				item['Leitsatz']=PH.NC(" ".join(entscheid.xpath("./div[@class='search-listing-item-summary']/p/text()").getall()),info="kein Leitsatz in "+text)
				item['Weiterzug']=PH.NC(entscheid.xpath("./div[@class='search-listing-item-legal']/text()").get(),info="kein Rechtszug in "+text)
				item['PDFUrls']=[self.HOST+PH.NC(entscheid.xpath("./div[@class='search-listing-item-download']/a/@href").get(),error="keine PDF-URL")]
				item['Signatur'], item['Gericht'], item['Kammer']=self.detect("","",item['Num'])
				if self.check_blockliste(item):
					yield item
		if page*self.TREFFER_PRO_SEITE < trefferzahl:
			request=self.generate_request(page)
			yield request
