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

class VD_Omni(BasisSpider):
	name = 'VD_Omni'

	SUCH_URL='/scripts/nph-omniscgi.exe'
	HOST ="http://www.jurisprudence.vd.ch"
	BLAETTERN_URL="/scripts/nph-omniscgi.exe?OmnisPlatform=WINDOWS&WebServerUrl=www.jurisprudence.vd.ch&WebServerScript=/scripts/nph-omniscgi.exe&OmnisLibrary=JURISWEB&OmnisClass=rtFindinfoWebHtmlService&OmnisServer=7001&Parametername=WWW_V4&Schema=VD_TA_WEB&Source=search.fiw&Aufruf=search&cTemplate=search/standard/results/resultpage.fiw&cSprache=FRE&W10_KEY={W10}&nSeite={Seite}"
	TREFFER_PRO_SEITE = 50
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "www.jurisprudence.vd.ch",
		"WebServerScript": "/scripts/nph-omniscgi.exe",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "7001",
		"Schema": "VD_TA_WEB",
		"Parametername": "WWW_V4",
		"Source": "search.fiw",
		"Aufruf": "search",
		"cTemplate": "search/standard/results/resultpage.fiw",
		"cTemplate_SuchstringValidateError": "search/standard/search.fiw",		
		"cSprache": "FRE",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"cHerkunft": "",
		"dEntscheiddatum": "",
		"dEntscheiddatumBis": "",
		"dPublikationsdatum": "",
		"cPublikation": "",
		"cReferent": "",
		"cTitel": "",
		"cSekretaer": "",
		"cResume": "",
		"cSuchstringZiel": "F37_HTML",
		"cSuchstring": "",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE),
		"nSeite": "1",
	}
	
	custom_setting = { 'DOWNLOAD_DELAY': 1.0}
	
	HERKUNFT=["!","CCST","CDAP","JI","TA","CE","TC","TN"]
	
	reTreffer=re.compile(r"résultats:\s<b>\d+(?:\s-\s\d+)?</b>\sde\s(?P<Treffer>\d+)\sfiche\(s\)\strouvée\(s\)")
	reW10=re.compile(r"W10_KEY=(?P<Key>\d+)&")
	
	def get_next_request(self):
		request=None
		if len(self.HERKUNFT)>0:
			logger.info("Starte nun "+self.HERKUNFT[0])
			formdata=copy.deepcopy(self.FORMDATA)
			formdata['cHerkunft']=self.HERKUNFT[0]
			request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=formdata, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 1, 'herkunft': self.HERKUNFT[0]})
			del self.HERKUNFT[0]
		return request
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
			self.FORMDATA['dPublikationsdatum']=ab
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])
	
		treffer=response.xpath("//table[@width='98%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td/h5").get()
		logger.info("Trefferzahl: "+treffer)
		treffers=self.reTreffer.search(treffer)
		if treffers:
			trefferzahl=int(treffers.group('Treffer'))
		else:
			logger.error("Trefferzahl nicht erkannt in: "+treffer)
		seite=response.meta['page']
		entscheide=response.xpath("//table[@width='98%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%']")
		logger.info(str(len(entscheide))+" Entscheide in der Liste.")

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.debug("Eintrag: "+text)
			item['HTMLUrls']=[self.HOST+PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[1]/td/table/tr/td/a/@href").get(),error="keine URL in "+text).strip()]
			item['Titel']=PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[2]/td/table/tr[1]/td/b/text()").get(), info="keine Titelzeile in "+text).strip()
			item['Leitsatz']=PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[2]/td/table/tr[2]/td[@colspan='2']/text()").get(), info="keine Regeste in "+text).strip()
			item['Num']=PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[1]/td/table/tr/td/a/text()[2]").get(), error="keine Geschäftsnummer in "+text).strip()
			edatum_roh=PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[1]/td/table/tr/td[2]/text()").get(), error="kein Entscheiddatum in "+text).strip()
			item['EDatum']=self.norm_datum(edatum_roh)
			pdatum_roh=PH.NC(entscheid.xpath("./tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr[3]/td/table/tr/td[2]/text()").get(), error="kein Publikationsdatum in "+text).strip()
			item['PDatum']=self.norm_datum(pdatum_roh)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","#"+response.meta['herkunft']+"#",item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			if self.check_blockliste(item):
				yield request
	
		if seite*self.TREFFER_PRO_SEITE < trefferzahl:
			href=response.xpath("//table[@width='98%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td[@valign='top']/a/@href")
			if href==[]:
				logger.error("Blätterlink nicht gefunden: "+antwort)
			else:
				href_string=href.get()
				W10=self.reW10.search(href_string)
				if W10:
					next_url=self.HOST+self.BLAETTERN_URL.format(W10=W10.group('Key'),Seite=str(seite+1))
					request=scrapy.Request(url=next_url, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1, 'herkunft': response.meta['herkunft']})
					yield request
				else:
					logger.error("W10 für das Blättern nicht gefunden: "+antwort)
		else:
			# Die weiteren Quellen aufrufen (nun sequentiell machen, da parallel geblockt wird)
			request=self.get_next_request()
			yield request

								
	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@class='WordSection1' or @class='Section1']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		regeste=response.xpath("//td[@colspan='2']/table/tr/td[./b/text()='Résumé contenant:']/following-sibling::td/b/text()")
		if len(regeste)>0:
			item['Leitsatz']=regeste.get()
		yield(item)
		
