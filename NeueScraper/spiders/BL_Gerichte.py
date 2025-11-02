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
from scrapy.http import JsonRequest

logger = logging.getLogger(__name__)


class BL_Gerichte(BasisSpider):
	name = 'BL_Gerichte'
	HOST="https://bl.swisslex.ch"
	SEARCH="/api/retrieval/postSearch?sourceDetails=search-button"
	DOC="/api/doc/getAsset?id={}&lang=de&queryLang=De&source=hitlist-search&transactionId={}"
	PDF="/api/Content/GetFacsimile?facsimileGuid="
	HEADER={
		"Accept": "application/json, text/plain, */*",
		"Accept-Language": "de-CH",
		"Content-Type": "application/json",
		"X-Application": "court",
		"Authenticated": "false",
		"Origin": "https://bl.swisslex.ch",
		"Referer": "https://bl.swisslex.ch/de/recherche/search/new",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0",
	}
	HITSPERPAGE=100

	# BODY={"paging":{"CurrentPage":1,"HitsPerPage":25},"searchFilter":{"searchText":"*","navigation":None,"searchLanguage":1,"law":None,"articleNumber":None,"paragraph":None,"subParagraph":None,"dateFrom":None,"dateUntil":None,"reference":None,"author":None,"practiceAreaGroupsCriteria":[],"assetTypeGroupsCriteria":[],"thesaurusType":1,"userSearchFilterId":None,"bookmarkSearchFilterId":None,"thesaurusInformation":None,"nSelected":0,"journalCriteria":[],"caseCollectionCriteria":[],"bookCriteria":[],"sourceDetails":"paging-359","paging":{"CurrentPage":359,"HitsPerPage":25},"drillDownFilter":{"sortOrder":0},"expandedFacettes":[],"filterAggregationQuery":False,"expandReferences":True,"selectedParts":31,"portalLanguage":"de"},"refineFilter":{"aggregationsFilter":[],"transformationFilter":[],"retrievalSortBy":0,"excludedDocumentIds":[]},"reRunTransactionID":None,"sourceTransactionID":None,"isLexCampus":False}
	# BODY=b'{"paging":{"CurrentPage":1,"HitsPerPage":25},"searchFilter":{"searchText":null,"navigation":null,"searchLanguage":1,"law":null,"articleNumber":null,"paragraph":null,"subParagraph":null,"dateFrom":null,"dateUntil":null,"reference":null,"author":null,"practiceAreaGroupsCriteria":[],"assetTypeGroupsCriteria":[],"thesaurusType":1,"userSearchFilterId":null,"bookmarkSearchFilterId":null,"thesaurusInformation":null,"nSelected":0,"journalCriteria":[],"caseCollectionCriteria":[],"bookCriteria":[],"paging":{"CurrentPage":1,"HitsPerPage":25},"drillDownFilter":{"sortOrder":0},"expandedFacettes":[],"filterAggregationQuery":false,"expandReferences":true,"selectedParts":31,"portalLanguage":"de"},"refineFilter":{"aggregationsFilter":[],"transformationFilter":[],"retrievalSortBy":0,"excludedDocumentIds":[]},"reRunTransactionID":null,"sourceTransactionID":null,"isLexCampus":false}'
	BODY = r'''{"paging":{"CurrentPage":1,"HitsPerPage":100},"searchFilter":{"searchText":null,"navigation":null,"searchLanguage":1,"law":null,"articleNumber":null,"paragraph":null,"subParagraph":null,"dateFrom":null,"dateUntil":null,"reference":null,"author":null,"practiceAreaGroupsCriteria":[],"assetTypeGroupsCriteria":[],"thesaurusType":1,"userSearchFilterId":null,"bookmarkSearchFilterId":null,"thesaurusInformation":null,"nSelected":0,"journalCriteria":[],"caseCollectionCriteria":[],"bookCriteria":[],"paging":{"CurrentPage":1,"HitsPerPage":25},"drillDownFilter":{"sortOrder":0},"expandedFacettes":[],"filterAggregationQuery":false,"expandReferences":true,"selectedParts":31,"portalLanguage":"de"},"refineFilter":{"aggregationsFilter":[],"transformationFilter":[],"retrievalSortBy":0,"excludedDocumentIds":[]},"reRunTransactionID":null,"sourceTransactionID":null,"isLexCampus":false}'''

	reKammer=re.compile(r", (?P<Kammer>(?:Abteilung|Aufsichtsbehörde|Anwaltskommission) .*) vom")

	def __init__(self, ab=None, neu=None):
		self.ab=ab
		self.neu=neu
		super().__init__()

	def generate_request(self, seite):
		body=json.loads(self.BODY)
		body["paging"]["HitsPerPage"]=self.HITSPERPAGE
		body["paging"]["CurrentPage"]=seite
		if self.ab:
			body["searchFilter"]["dateFrom"]=self.ab
		return JsonRequest(url=self.HOST+self.SEARCH, data=body, headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'seite': seite})
	

	def start_requests(self):
		# vor Super-Call Settings lesen / Defaults setzen
		self.cfg = self.crawler.settings.get('MY_GLOBAL', 'default')
		# self.request_gen = [scrapy.Request(url=self.HOST+self.LOGIN, headers=self.HEADER, method="POST", body=json.dumps(self.BODY_LOGIN), callback=self.parse_login, errback=self.errback_httpbin)]
		self.request_gen=[self.generate_request(1)]

		for req in super().start_requests():
			req.meta.setdefault('cfg', self.cfg)
			yield req
	
	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" für URL "+response.url)
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		
		seite=response.meta['seite']
		
		struktur=json.loads(antwort)
		treffer=struktur['numberOfDocuments']
		seitentreffer=len(struktur['hits'])
		logger.info(f"{treffer} Entscheide gefunden – {seitentreffer} übergeben.")
		transactionId=str(struktur['transactionId'])
		for entscheid in struktur["hits"]:
			item={}
			entscheidtext=json.dumps(entscheid)
			item['VGericht']=PH.NC(entscheid['courtDescription'],warning="kein Gericht in "+entscheidtext)
			item['Leitsatz']=PH.NC(entscheid['description'],warning="kein Abstract in "+entscheidtext)
			# Maximal 2 Geschäftsnummern übernehmen
			nums=PH.NC(entscheid['caseLawNumbers'],warning="keine Geschäftnummer in "+entscheidtext)
			num_array=nums.split(",")
			item['Num']=num_array[0].strip()
			if len(num_array)>1:
				item['Num2']=num_array[1].strip()
			item['EDatum']=self.norm_datum(PH.NC(entscheid['date'][0:10],warning="kein Entscheiddatum in "+entscheidtext))
			titel=PH.NC(entscheid['title'],warning="keine formale Titelzeile in "+entscheidtext)
			abteilungssuche=self.reKammer.search(titel)
			if abteilungssuche:
				item['VKammer']=abteilungssuche.group('Kammer')
			else:
				logger.warning(f"Keine Abteilung in {titel} erkannt.")
				item['VKammer']=''
			item['DocID']=PH.NC(entscheid['targetID'],error="keine ID in "+entscheidtext)
			docurl=self.HOST+self.DOC.format(item['DocID'],transactionId)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'], item['VKammer'], item['Num'])
			
			logger.info("Entscheid: "+json.dumps(item))
			headers=copy.deepcopy(self.HEADER)
			headers['Referer']='https://bl.swisslex.ch/de/recherche/search/'+transactionId
			item['PdfHeaders']=copy.deepcopy(headers)
			item['PdfHeaders']['Referer']='https://bl.swisslex.ch/de/doc/claw/'+item['DocID']+'/search/'+transactionId
			request=scrapy.Request(url=docurl, callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item}, headers=headers)
			yield request
		if seitentreffer==self.HITSPERPAGE:
			request=self.generate_request(seite+1)
			yield request
			
	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']
		struktur=json.loads(antwort)
		# Gibt es ein Original PDF?
		if 'facsimile' in struktur['content']:
			item['PDFUrls']=[self.HOST+self.PDF+struktur['content']['facsimile']['fileID']]
		else:
			logger.info(f"kein PDF vorhanden für {json.dumps(item)}")
		
		if 'assetContentAsHtml' in struktur['content']:
			logger.info(f"Auf jeden Fall auch HTML holen {item['Num']}")
			item['HTMLUrls']=[response.url]
			PH.write_html(struktur['content']['assetContentAsHtml'], item, self)
		else:
			logger.info(f"kein HTML vorhanden für {json.dumps(item)}")
		
		if 'facsimile' not in struktur['content'] and 'assetContentAsHtml' not in struktur['content']:
			logger.error(f"weder HTML noch PDF vorhanden für Entscheid {json.dumps(item)}")
		else:
			logger.info(f"Entscheid geholt: {json.dumps(item)}")

		yield(item)
