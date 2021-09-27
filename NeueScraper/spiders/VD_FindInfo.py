# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
import json
import urllib3
from urllib.parse import quote, unquote
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import MyFilesPipeline
from NeueScraper.pipelines import PipelineHelper


logger = logging.getLogger(__name__)

class ZurichVerwgerSpider(BasisSpider):
	name = 'VD_FindInfo'
	
	custom_settings = {
        'COOKIES_ENABLED': True
    }

	HOST ="https://www.findinfo-tc.vd.ch"
	SUCH_URL='/justice/findinfo-pub/internet/SimpleSearch.action'
	HTML_URL='/justice/findinfo-pub/html/'
	PAGE_URL='/justice/findinfo-pub/internet/SimpleSearch.action?showPage=&page='
	ab=None
	reMeta=re.compile(r'<b>Cour</b>:\s<acronym title=\"(?P<VKammer>[^\"]+)\">(?P<Kurz>[^<]+)</acronym><br><b>Date\s(?:décision</b>:\s(?:<span class="highlight">)?(?P<EDatum>[^<]+)(?:</span>)?(?:<br><b>Date\s)?)?(?:publication</b>:\s(?:<span class="highlight">)?(?P<PDatum>[^<]+)(?:</span>)?)?<br>(?:<b>N°\sdécision</b>:\s+(?P<Num>[^<]+)<br>)?(?P<Rest>.+)$')
	#reMeta=re.compile(r'<b>Cour</b>:\s<acronym title=\"(?P<VKammer>[^\"]+)\">(?P<Kurz>[^<]+)</acronym><br>(?:<b>Date\s(?:décision</b>:\s(?P<EDatum>[^<]+)<br>(?:<b>Date\s)?)?(?:publication</b>:\s(?P<PDatum>[^<]+)<br>(?:<b>N°\sdécision</b>:\s+(?P<Num>[^<]+)<br>)?(?P<Rest>.+)$')
	reURL=re.compile(r'/justice/findinfo-pub/internet/search/result.jsp\?path=(?P<URL>[^&]+)')

	TREFFER_PRO_SEITE = 50
	FORMDATA = {
		"search.criteria.dossierNr": "",
		"search.criteria.decisionDateSearchRange.dateFrom": "",
		"search.criteria.decisionDateSearchRange.dateTo": "",
		"search.criteria.publicationFirstPublDateSearchRange.dateFrom": "",
		"search.criteria.publicationFirstPublDateSearchRange.dateTo": "",
		"search.criteria.orgUnitIds": "",
		"search.criteria.fulltextKeywordString": "",
		"search": "Rechercher",
		"search.pageSize": str(TREFFER_PRO_SEITE),
		"_sourcePage": "/internet/dossiers_overview.jsp",
		"__fp": "aqHRlcbSe8VaRFthDeaYjpuTT61vfqJdAI9qSW6J3qc="
	}

	def request_generator(self, ab=None):
		if ab:
			self.FORMDATA['search.criteria.publicationFirstPublDateSearchRange.dateFrom']=ab
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 1})
		return request


	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		self.request_gen=[self.request_generator(ab)]

	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode()[:20000])
	
		treffer=response.xpath("//table[@style='padding: 0px; margin: 0px;' and @width='100%']/tr/td[@class='resultNavigation']/div[@style='padding-bottom: 4px;']/div[@style='text-align: right;']/b[3]/text()").get()
		if treffer:
			logger.info("Insgesamt "+treffer+" Treffer.")
		else:
			logger.error("Trefferzahl nicht erkannt.")
		trefferZahl=int(treffer)
		
		entscheide=response.xpath("//tr[td[@id='big' and @class='resultValue']/a]")
		logger.info("Entscheide in Trefferliste: "+str(len(entscheide)))
		
		for entscheid in entscheide:
			item={}
			logger.info("Verarbeite Entscheid: "+entscheid.get())
			url=entscheid.xpath(".//a/@href").get()
			urls=self.reURL.search(url)
			if urls is None:
				logger.error("Url '"+url+"' konnte nicht erkannt werden")
			else:
				logger.debug("URL Anfangs: "+urls.group("URL"))
				url_unq=unquote(urls.group("URL"))
				logger.debug("Unquote: "+url_unq)				
				url_iso=url_unq.encode("iso-8859-1")
				logger.debug(b"ISO: "+url_iso)
				url=self.HOST+self.HTML_URL+quote(url_iso)
				logger.debug("URL Ende: "+url)
				
			item['HTMLUrls']=[url]
			item['Num']=entscheid.xpath(".//a/acronym/text()").get()
			meta=entscheid.xpath("./following-sibling::tr/td[@class='resultValue' and b/text()='Cour']").get()
			if meta:
				logger.debug("Metastring: "+meta)
			else:
				logger.error("Metastring nicht gefunden.")
			metas=self.reMeta.search(meta)
			if metas is None:
				logger.error("Metainformation nicht erkannt in: "+meta)
			else:
				item['VKammer']=metas.group("VKammer")
				kurz=metas.group("Kurz")
				pdatum_roh=metas.group("PDatum")
				if pdatum_roh:
					item['PDatum']=self.norm_datum(pdatum_roh)
				edatum_roh=metas.group("EDatum")
				if edatum_roh:
					item['EDatum']=self.norm_datum(edatum_roh)
				if metas.group("Num") and len(metas.group("Num"))>5:
					item['Num']=metas.group("Num")
				rest=metas.group("Rest")
				if len(rest)>10:
					logger.warning("Long_Restmeta: "+rest)
				else:
					logger.info("Restmeta: "+rest)
			normen=entscheid.xpath(".//td[@class='keywords' and div/text()='Article']/div[@class='odd' or @class='even']/text()").getall()
			if len(normen)>0:
				item['Normen']=", ".join([n.strip() for n in normen])
			leitsatz=entscheid.xpath(".//td[@class='keywords' and div/text()='Jurivoc']/div[@class='odd' or @class='even']/text()").getall()
			if len(leitsatz)>0:
				item['Leitsatz']=", ".join([l.strip() for l in leitsatz])
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect("","#"+kurz+"#",item['Num'])
			logger.debug("Item bislang: "+json.dumps(item))
			logger.info("Hole nun "+url)
			request=scrapy.Request(url=url, callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item})
			if self.check_blockliste(item):
				yield(request)
		seite=response.meta['page']
		if seite*self.TREFFER_PRO_SEITE<trefferZahl:
			request=scrapy.Request(url=self.HOST+self.PAGE_URL+str(seite+1), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta = {'page':seite+1})
			yield request
		

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.debug("parse_page response.status "+str(response.status))
		logger.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_page Rohergebnis: "+response.body_as_unicode()[:5000])
		item=response.meta['item']

		PipelineHelper.write_html(response.body_as_unicode(), item, self)
		yield(item)						
