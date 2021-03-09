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


class ZH_Steuerrekurs(BasisSpider):
	name = 'ZH_Steuerrekurs'

	URL='/site/themes/strg-theme/js/ruling-search.js'
	TREFFER_PRO_SEITE=20
	HOST='https://www.strgzh.ch'
	SEARCH="https://{}-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20vanilla%20JavaScript%20(lite)%203.32.0%3Binstantsearch.js%203.0.0%3BJS%20Helper%202.26.1&x-algolia-application-id={}&x-algolia-api-key={}"
	BODY1='{"requests":[{"indexName":"collections_rulings_date_priority","params":"query=&hitsPerPage='+str(TREFFER_PRO_SEITE)+'&page='
	BODY2='&restrictSearchableAttributes=%5B%5D&highlightPreTag=__ais-highlight__&highlightPostTag=__%2Fais-highlight__&facets=%5B%22ruling_date%22%5D&tagFilters=&numericFilters=%5B%22ruling_date%3E%3D'
	BODY3='%22%2C%22ruling_date%3C%3D'
	BODY4='.091%22%5D"},{"indexName":"collections_rulings_date_priority","params":"query=&hitsPerPage=1&page=0&restrictSearchableAttributes=%5B%5D&highlightPreTag=__ais-highlight__&highlightPostTag=__%2Fais-highlight__&attributesToRetrieve=%5B%5D&attributesToHighlight=%5B%5D&attributesToSnippet=%5B%5D&tagFilters=&analytics=false&clickAnalytics=false&facets=ruling_date"}]}'

	PDF_HOST='https://www.strgzh.ch'
	RE_ALIGOLIA=re.compile(r'algoliasearch\("(?P<URL>[^"]+)","(?P<APIKEY>[^"]+)"\)')
	AB_DEFAULT='01.01.2009'
	BIS='31.12.2030'
	ab=None
	url=None
	apikey=None
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+self.URL,callback=self.parse_first_request, errback=self.errback_httpbin)]

	def generate_request(self, page=0):
		searchurl=self.SEARCH.format(self.url,self.url,self.apikey)
		if self.ab:
			ab=self.ab
		else:
			ab=self.AB_DEFAULT
		body=(self.BODY1+str(page)+self.BODY2+datetime.datetime.strptime(ab,"%d.%m.%Y").strftime('%s')+self.BODY3+datetime.datetime.strptime(self.BIS,"%d.%m.%Y").strftime('%s')+self.BODY4)
		logger.info("Body: "+body)
		request= scrapy.Request(url=searchurl, method="POST", body=body.encode('UTF-8'), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': page})
		return request

	def parse_first_request(self, response):
		logger.info("parse_first_request response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_first_request Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_first_request Rohergebnis: "+antwort[:10000])
		aligolia=self.RE_ALIGOLIA.search(antwort)
		if aligolia:
			self.url=aligolia.group('URL')
			self.apikey=aligolia.group('APIKEY')
			request=self.generate_request()
			yield request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		daten=json.loads(antwort)
		trefferzahl=daten['results'][0]['nbHits']
		page=response.meta['page']+1		
		logger.info(f"Trefferzahl {trefferzahl}, Seite {page}, Treffer pro Seite {self.TREFFER_PRO_SEITE}")
		for entscheid in daten['results'][0]['hits']:
			logger.info("Bearbeite Entscheid: "+json.dumps(entscheid))
			item={}
			item['Titel']=entscheid['title']
			item['Leitsatz']=entscheid['summary']
			item['Num']=entscheid['citation_display']
			item['Num2']=entscheid['alt_citation_display']
			item['Normen']=entscheid['legal_foundation']
			item['Weiterzug']=entscheid['note']
			item['DocID']=entscheid['objectID']
			edatum=entscheid['ruling_date']
			pdatum=entscheid['date']
			item['EDatum']=datetime.datetime.fromtimestamp(int(edatum)).strftime("%Y-%m-%d")
			item['PDatum']=datetime.datetime.fromtimestamp(int(pdatum)).strftime("%Y-%m-%d")
			item['PDFUrls']=[self.PDF_HOST+entscheid['document_file']]
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect("","",item['Num'])
			if self.check_blockliste(item):
				yield item
		if page*self.TREFFER_PRO_SEITE < trefferzahl:
			request=self.generate_request(page)
			yield request
