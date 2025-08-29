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
import codecs

logger = logging.getLogger(__name__)


class SH_OG(BasisSpider):
	custom_settings = {
        'COOKIES_ENABLED': True
    }
	name = 'SH_OG'

	HOST ="https://obergerichtsentscheide.sh.ch"
	START_CONTENT_ID="2272928"
	START_URL="/CMS/Webseite/Obergerichtsentscheide-{content_id}-DE.html"
	LIST_URL="/CMS/lists/list?rows=300&sort=sortable_datetime%20desc&filter_customposttypeid_int=402&filter_published_string=published&filter_approvedpaths_string=*%2F8527%2F9005%2F2272923%2F2272926%2F{content_id}%2F*&rows=300&filter_text=()&filter_language_string=DE&status=&start=0&mode=portrait&slider=false&language=DE&colclass=false&domainpath=%2F8527%2F9005%2F&kiosktype=kioskWidget"
	DOC_URL="/CMS/Webseite/Obergerichtsentscheide/{jahr}-{content_id}-DE.html"
	DOC_PDF_URL="/CMS/lists/list?rows=1&filter_contentid_int={content_id}&status=published&start=0&mode=portrait&slider=false&language=DE&colclass=false&domainpath=%2F8527%2F9005%2F&kiosktype=singleContent"
	
	reData=re.compile(r'window\.CONTENT_DATA\s*=\s*(?P<data>\{.*?\})\s*;')
	reTag=re.compile(r'<[^>]+>')
	reDocData=re.compile(r'var\s+wrapper\s+=\s+\$\(\'\#(?P<id>[0-9]+)_(?P<gid>(?:[0-9a-f-]+|null))\'\);\s+try\s+\{\s+var\s+kacheldata\s*=\s*JSON\.parse\("(?P<data>(?:\\.|[^"\\])*)"\);', re.DOTALL | re.MULTILINE | re.VERBOSE)
	reNumPre=re.compile(r'^Nr\.\s+')
	
	
	def get_next_request(self):
		request=scrapy.Request(url=self.HOST+self.START_URL.format(content_id=self.START_CONTENT_ID), callback=self.parse_jahre, errback=self.errback_httpbin,meta={"content_ids":[self.START_CONTENT_ID],"typ":"Jahre"})
		return request
	
	def __init__(self, neu=None):
		super().__init__()
		self.neu=neu
		self.request_gen = [self.get_next_request()]

	def parse_jahre(self, response):
		typ=response.meta["typ"]
		logger.info(f"parse_jahre {typ} url {response.url}, response.status {response.status}")
		antwort=response.text
		logger.info("parse_jahre "+typ+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_jahre "+typ+" Rohergebnis: "+antwort[:30000])
		content_ids=response.meta["content_ids"]
		script=response.xpath("//script[not(@*)][1]/text()")
		if script:
			scripttext=script.get()
			datamatch=self.reData.search(scripttext)
			if datamatch:
				data=datamatch.group("data")
				datastruct=json.loads(data)
				logger.info(f"parse_jahre {typ}: {len(datastruct)} Werte.")
				for entry in datastruct.values():
					logger.info(f"parse {typ}: contenttypeid {entry['contenttypeid']}")
					if entry['contenttypeid']=='499' or entry['contenttypeid']=='402':
						content_id=entry['data_repository_id']
						logger.info(f"content_id {content_id}")
						if content_id in content_ids:
							logger.info("parse_jahre "+typ+": Den Eintrag selbst gefunden.")
						else:
							jahr=entry["data_kachellabel"]
							data_overview_image=json.loads(entry['data_overview_image'])
							logger.info("parse_jahre "+typ+": gefunden: "+data_overview_image['text'])
							url=self.HOST+self.LIST_URL.format(content_id=content_id)
							request=scrapy.Request(url=url, callback=self.parse_liste, errback=self.errback_httpbin, meta={"content_ids": content_ids+[content_id],"jahr":jahr, "typ":"Liste"})
							yield request


	def parse_liste(self, response):
		typ=response.meta["typ"]
		jahr=response.meta["jahr"]
		logger.info(f"parse_liste {typ} ({jahr}), url {response.url}, response.status {response.status}")
		antwort=response.text
		logger.info("parse_liste "+typ+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_liste "+typ+" Rohergebnis: "+antwort[:30000])
		content_ids=response.meta["content_ids"]
		for m in self.reDocData.finditer(antwort):
			json_literal = m.group('data')          # der reine JSON-Text
			json_literal_clean=json_literal.replace("\\\\\"","\'")
			json_literal_clean=codecs.decode(json_literal_clean, "unicode_escape")
			json_literal_clean=json_literal_clean.replace("\\\"","\"")
			json_literal_clean=json_literal_clean.replace("&nbsp;"," ")
			
			content_id=m.group('id')
			content_gid=m.group('gid')
			logger.info(f"parse_liste: content_id:{content_id}, content_gid:{content_gid}, json:{json_literal}, json_clean:{json_literal_clean}")
			try:
				obj = json.loads(json_literal_clean)      # jetzt echtes Python-Dict
				item={}
				item['DocID']=content_gid
				titel=obj['text']
				item['Titel']=self.reTag.sub("",titel)
				num=obj['title']
				item['Num']=self.reNumPre.sub("",num)
				logger.info(f"Dokument {item['Num']}: {item['Titel']}")
				url=self.HOST+self.DOC_URL.format(jahr=jahr, content_id=content_id)
				request=scrapy.Request(url=url, callback=self.parse_doc, errback=self.errback_httpbin, meta={"content_ids": content_ids+[content_id],"jahr":jahr, "typ":"Doc", "item":item, "titel":titel})
				yield request
								
			except json.JSONDecodeError as err:
				logger.error(f'Fehler beim JSON-Parse: {err}')
		
	def parse_doc(self, response):
		typ=response.meta["typ"]
		logger.info(f"parse_doc {typ} url {response.url}, response.status {response.status}")
		antwort=response.text
		logger.info("parse_doc "+typ+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_doc "+typ+" Rohergebnis: "+antwort[:30000])
		content_ids=response.meta["content_ids"]
		item=response.meta['item']
		script=response.xpath("//script[not(@*)][1]/text()")
		jahr=response.meta['jahr']
		if script:
			scripttext=script.get()
			datamatch=self.reData.search(scripttext)
			if datamatch:
				data=datamatch.group("data")
				logger.info(f"parse_doc data: {data}")
				datastruct=json.loads(data)
				pdf_id=""
				for entry in datastruct.values():
					logger.info(f"parse_doc {typ}: contenttypeid {entry['contenttypeid']}")
					if entry['contenttypeid']=='402':
						leitsatz=entry["data_post_content"]
						leitsatz=leitsatz.replace("&lt;","<")
						leitsatz=leitsatz.replace("&gt;",">")						
						item["Leitsatz"]=self.reTag.sub("",leitsatz)
						item["PDatum"]=PH.NC(self.norm_datum(entry["data_publication_date"]),warning=item["Num"]+" hat kein PDatum in "+json.dumps(entry))
						pdf_id_string=PH.NC(entry['data_widget_data'],warning=item["Num"]+" hat kein data_widget_data in "+json.dumps(entry))
						pdf_id_struct=json.loads(pdf_id_string)
						if "contentid" in pdf_id_string:
							pdf_id=PH.NC(pdf_id_struct[0]["cols"][1]["fields"][0]["data"]["contentid"],error="keine Informationen zur id des requests für die PDF/filemeta für "+item["Num"]+" in "+pdf_id_string)
						else:
							logger.warning("Kein PDF für "+item["Num"])
					elif entry['contenttypeid']=='101':
						item["EDatum"]=PH.NC(self.norm_datum(entry["data_custom_publication_date_date"]),warning=item["Num"]+" hat kein PDatum in "+json.dumps(entry))					
						filemeta_string=PH.NC(entry["data_filemeta"],error="keine Informationen zu PDF/filemeta für "+item["Num"]+" in "+json.dumps(entry))
						filemeta=json.loads(filemeta_string)
						url=self.HOST+PH.NC(filemeta["url"],error="keine Informationen zur ULR in PDF/filemeta für "+item["Num"]+" in "+json.dumps(entry))
						item["PDFUrls"]=[url]
				if "PDFUrls" not in item:
					if pdf_id:
						url=self.HOST+self.DOC_PDF_URL.format(content_id=pdf_id)
						request=scrapy.Request(url=url, callback=self.parse_doc_pdf, errback=self.errback_httpbin, meta={"content_ids": content_ids,"jahr":jahr, "typ":"Doc_Pdf", "item":item})
						yield request
					else:
						if "Leitsatz" in item and "Titel" in item:
							item["html"]=response.meta["titel"]+leitsatz
							item["HTMLUrls"]=[response.url]
						else:
							logger.error("kein PDF und kein HTML text für Dokument "+item["Num"]+" gefunden.")

						logger.error("kann keinen Weg zum PDF finden für "+item["Num"]+" in "+json.dumps(entry))
				else:
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item["Num"])
					logger.info(f"parse_doc Item: {json.dumps(item)}")
					yield item
					
	def parse_doc_pdf(self, response):
		typ=response.meta["typ"]
		logger.info(f"parse_doc_pdf {typ} url {response.url}, response.status {response.status}")
		antwort=response.text
		logger.info("parse_doc_pdf "+typ+" Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_doc_pdf "+typ+" Rohergebnis: "+antwort[:30000])
		content_ids=response.meta["content_ids"]
		item=response.meta['item']
		script=response.xpath("//script[not(@*)][1]/text()")
		if script:
			scripttext=script.get()
			datamatch=self.reData.search(scripttext)
			if datamatch:
				data=datamatch.group("data")
				logger.info(f"parse_doc data: {data}")
				filemeta=json.loads(data)
				url=self.HOST+PH.NC(filemeta["url"],error="keine Informationen zur ULR in PDF/filemeta für "+item["Num"]+" in "+data)
				item["PDFUrls"]=[url]
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item["Num"])
				logger.info(f"parse_doc Item: {json.dumps(item)}")
				yield item


