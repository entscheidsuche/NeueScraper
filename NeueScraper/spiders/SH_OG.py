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


class SH_OG(BasisSpider):
	custom_settings = {
        'COOKIES_ENABLED': True
    }
	name = 'SH_OG'

	START_URL='/CMS/json_list.jsp?filter_customposttypeid_int=10300&listtype=repository&status=published&filter_approvedpaths_string=*%2F8527%2F9005%2F*&rows=-1'
	HOST ="https://obergerichtsentscheide.sh.ch"
	COOKIE_URL="/CMS/Webseite/Obergerichtsentscheide-2272928-DE.html"
	STUB_URL="/CMS/json_list.jsp?filter_generic_parent_repository_string="
	STUB_A_URL="/CMS/lists/list.jsp?rows=100&sort=sortable_datetime+desc&filter_customposttypeid_int=402&filter_published_string=published&filter_approvedpaths_string=*%2F8527%2F9005%2F2272923%2F2272926%2F"
	STUB_B_URL="%2F*&filter_text=*&filter_language_string=DE&status=&start=0&kioskid=066df47d-46e9-72e0-5902-aa4d05b81cbc&mode=portrait&slider=false&language=DE&colclass=false&domainpath=%2F8527%2F9005%2F&kiosktype=kioskWidget"
	STUB_DOC_A="/CMS/content.jsp?contentid="
	STUB_DOC_B="&language=DE"
	STUB_FILE_A="/CMS/lists/list.jsp?rows=1&filter_contentid_int="
	STUB_FILE_B="&status=published&start=0&kioskid=41d82fe3-73d3-15cb-7560-9ba0da22dd84&mode=portrait&slider=false&language=DE&colclass=false&domainpath=%2F8527%2F9005%2F&kiosktype=singleContent"
	GET_FILE="/CMS/get/file/"
	reTreffer=re.compile(r' contentid="(?P<contentid>[^"]+)"')
	rePDFID=re.compile(r'"contentid":"(?P<pdfid>[^"]+)"')
	reFilename=re.compile(r'\\"fileName\\":\\"(?P<filename>[^\\]+)\\"')
	reDatum=re.compile(r'[0-9B] vom (?P<datum>\d+\.\s*(?:'+r'|'.join(BasisSpider.MONATEde)+r')\s(?:19|20)\d\d)<')
	reLeerzeile=re.compile(r'<p class="post_text">&nbsp;</p>')
	reUmbruch=re.compile(r'(<br ?/?>)*\s*(</p>\s+<p class="post_text">\s*)+(<br ?/?>)*')
	reAnfang=re.compile(r'^Nr\.\s[0-9\/]+\s.{1,4}<br>')
	
	def get_next_request(self):
		request=scrapy.Request(url=self.HOST+self.COOKIE_URL, callback=self.parse_step0, errback=self.errback_httpbin)
		return request
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.get_next_request()]

	def parse_step0(self, response):
		logger.debug("parse_step1 response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_step1 Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_step1 Rohergebnis: "+antwort[:30000])
		request=scrapy.Request(url=self.HOST+self.START_URL, callback=self.parse_step1, errback=self.errback_httpbin)
		yield request
		

	def parse_step1(self, response):
		logger.debug("parse_step1 response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_step1 Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_step1 Rohergebnis: "+antwort[:30000])
		struktur=json.loads(antwort)
		weiter=struktur[0]['contentid']
		logger.info("ID (step1): "+weiter)
		request=scrapy.Request(url=self.HOST+self.STUB_URL+weiter, callback=self.parse_step2, errback=self.errback_httpbin)
		yield request
		
	def parse_step2(self, response):
		logger.debug("parse_step2 response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_step2 Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_step2 Rohergebnis: "+antwort[:30000])
		struktur=json.loads(antwort)
		weiter=struktur[0]['contentid']
		logger.info("ID (step2): "+weiter)
		request=scrapy.Request(url=self.HOST+self.STUB_URL+weiter, callback=self.parse_step3, errback=self.errback_httpbin)
		yield request
		
	def parse_step3(self, response):
		logger.debug("parse_step3 response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_step3 Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_step3 Rohergebnis: "+antwort[:30000])
		struktur=json.loads(antwort)
		for r in struktur:
			weiter=r['contentid']
			jahr=r['label']
			url=self.HOST+self.STUB_A_URL+weiter+self.STUB_B_URL
			logger.info("ID (step3): "+weiter+" Jahr "+jahr+" ("+url+")")
			request=scrapy.Request(url=url, callback=self.parse_jahr, errback=self.errback_httpbin, meta={'jahr': jahr})
			yield request
		
	def parse_jahr(self, response):
		logger.debug("parse_jahr response.status "+str(response.status))
		antwort=response.body_as_unicode()
		jahr=response.meta['jahr']
		logger.info("parse_jahr "+jahr+": "+response.url+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_jahr Rohergebnis: "+antwort[:30000])
		
		treffer=self.reTreffer.findall(antwort)
		zahl=len(treffer)
		if zahl==100: logger.error("100 Treffer in "+jahr+", weitere Treffer gehen ggf. verloren")
		else: logger.info(str(zahl)+" Treffer gefunden")
		for t in treffer:
			logger.info("parse_jahr "+jahr+" Contentid: "+t)
			url=self.HOST+self.STUB_DOC_A+t+self.STUB_DOC_B
			logger.info("ID (parse_jahr): "+t+" Jahr "+jahr+" ("+url+")")
			request=scrapy.Request(url=url, callback=self.parse_doc, errback=self.errback_httpbin, meta={'jahr': jahr, 'doc': t})
			yield request
			
	def parse_doc(self, response):
		logger.debug("parse_doc response.status "+str(response.status))
		antwort=response.body_as_unicode()
		jahr=response.meta['jahr']
		doc=response.meta['doc']
		logger.info("parse_doc "+jahr+": "+response.url+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_doc Rohergebnis: "+antwort[:30000])

		struktur=json.loads(antwort)
		num=PH.NC(struktur['data_kachellabel'],error="kein AZ"+antwort)
		if num[0:4]=="Nr. ": num=num[4:]
		item={}
		item['Num']=num
		pdatum=PH.NC(struktur['data_publication_date'],warning="kein Publikationsdatum in "+antwort)		
		item['PDatum']=self.norm_datum(pdatum, warning="Kein P-Datum identifiziert in "+pdatum)
		titel=PH.NC(struktur['data_listlabel'], warning="kein data_listlabel (Leitsatz) in "+antwort)
		titel2=self.reAnfang.sub("",titel)
		logger.info("Titel von "+titel+" zu "+titel2)
		item['Titel']=titel2
		abstract=PH.NC(struktur['data_post_content'], warning="kein data_post_content (Titel) in "+antwort)
		edatummatch=self.reDatum.search(abstract)
		if edatummatch:
			edatum=edatummatch.group('datum')
			logger.info("EDatum gefunden: "+edatum)
			item['EDatum']=self.norm_datum(edatum, warning="Kein E-Datum identifiziert in "+edatum)
		abstract=abstract.replace('<p class="post_text">&nbsp;</p>','') # Leerzeilen rauswerfen
		abstract=self.reUmbruch.sub("<br>",abstract) #Umbrüche durch br ersetzen
		abstract=abstract.replace('<p class="post_text">','') #einzelne Tags noch löschen
		abstract=abstract.replace('</p>','')
		
		item['Abstract']=abstract
		item['VGericht']=PH.NC(struktur['data_custom_author'], warning="kein data_custom_author (VGericht) in "+antwort)
		item['DocID']=doc
		pdfidstring=PH.NC(struktur['data_widget_data'], error="keine ID für das PDF gefunden in "+antwort)
		pdfidmatch=self.rePDFID.search(pdfidstring)
		if pdfidmatch:
			pdfid=pdfidmatch.group("pdfid")
			url=self.HOST+self.STUB_FILE_A+pdfid+self.STUB_FILE_B
			logger.info("ID (parse_doc): "+doc+" Jahr "+jahr+" ("+url+")")			
			request=scrapy.Request(url=url, callback=self.parse_file, errback=self.errback_httpbin, meta={'jahr': jahr, 'doc': doc, 'item': item})
			yield request
		else:
			logger.error("kein Match für pdfid in "+pdfidstring)
		
	def parse_file(self, response):
		logger.debug("parse_file response.status "+str(response.status))
		antwort=response.body_as_unicode()
		jahr=response.meta['jahr']
		doc=response.meta['doc']
		item=response.meta['item']
		logger.info("parse_file "+doc+": "+response.url+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_file Rohergebnis: "+antwort[:30000])
		
		filename=self.reFilename.search(antwort)
		if filename:
			item['PDFUrls']=[self.HOST+self.GET_FILE+filename.group('filename')]
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			yield item
		else:
			logger.error("Konnte keine PDF-Datei für "+doc+" aus "+jahr+" finden.")
