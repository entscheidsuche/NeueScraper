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


class NE_Omni(BasisSpider):
	name = 'NE_Omni'

	custom_settings = {
        'COOKIES_ENABLED': True
    }

	SUCH_URL='/scripts/omnisapi.dll'
	HOST ="http://jurisprudence.ne.ch"
	TREFFER_PRO_SEITE = 50
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "jurisprudence.ne.ch",
		"WebServerScript": "/scripts/omnisapi.dll",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "JURISWEB,localhost:7000",
		"Schema": "NE_WEB",
		"Parametername": "NEWEB",
		"Aufruf": "validate",
		"cTemplate": "search_resulttable.html",
		"cTemplate_ValidationError": "search.html",		
		"cSprache": "FRE",
		"nSeite": "1",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"dEntscheiddatum": "",
		"dEntscheiddatumBis": "",
		"cPublikationsdetail": "",
		"dPublikationsdatum": "",
		"dPublikationsdatumBis": "",
		"cArtikel": "",
		"cTitelResumee": "",
		"cSuchstring": "",
		"bSelectAll": "true",
		"bInstanzInt_CC1": "CC1",
		"bInstanzInt_CC2": "CC2",
		"bInstanzInt_ARAN": "ARAN",
		"bInstanzInt_ARMC": "ARMC",
		"bInstanzInt_ARMP": "ARMP",
		"bInstanzInt_ASLP": "ASLP",
		"bInstanzInt_ASA": "ASA",
		"bInstanzInt_NOTA": "NOTA",
		"bInstanzInt_ASSLP": "ASSLP",
		"bInstanzInt_ATS": "ATS",
		"bInstanzInt_CHAC": "CHAC",
		"bInstanzInt_CHAR": "CHAR",
		"bInstanzInt_CCIV": "CCIV",
		"bInstanzInt_CC": "CC",
		"bInstanzInt_CACIV": "CACIV",
		"bInstanzInt_CA": "CA",
		"bInstanzInt_CCC": "CCC",
		"bInstanzInt_CCP": "CCP",
		"bInstanzInt_CDP": "CDP",
		"bInstanzInt_CMPEA": "CMPEA",
		"bInstanzInt_CPEN": "CPEN",
		"bInstanzInt_HR": "HR",
		"bInstanzInt_TA": "TA",
		"bInstanzInt_TARB": "TARB",
		"bInstanzInt_TR_CIVIL": "TR_CIVIL",
		"bInstanzInt_TR_PENAL": "TR_PENAL",
		"bInstanzInt_#NULL": "#NULL",
		"evSubmit": "",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE)
	}
	
	reTreffer=re.compile(r"</b>\sde\s(?P<Treffer>\d+)\sfiche\(s\)\strouvée\(s\)")
	reNum2=re.compile(r"\((?P<Num2>[^)]+)\)")
	
	def get_next_request(self):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 1})
		return request
	
	def __init__(self, ab=None):
		super().__init__()
		if ab:
			self.ab=ab
			self.FORMDATA['dPublikationsdatum']=ab
			self.FORMDATA['bHasPublikationsdatumBis']="1"
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])
	
		treffer=response.xpath("//table[@width='100%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td[@width='50%']").get()
		logger.info("Trefferzahl: "+treffer)
		treffers=self.reTreffer.search(treffer)
		if treffers:
			trefferzahl=int(treffers.group('Treffer'))
		else:
			logger.error("Trefferzahl nicht erkannt in: "+treffer)
		seite=response.meta['page']
		entscheide=response.xpath("//table[@width='100%' and @cellspacing='0' and @cellpadding='0' and @style='border-bottom: 1px solid #93a1f4; padding-bottom: 5px; margin-bottom: 5px;']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']")
		logger.info(str(len(entscheide))+" Entscheide in der Liste.")

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.debug("Eintrag: "+text)
			item['HTMLUrls']=[PH.NC(entscheid.xpath("./tr/td/a/@href").get(),error="keine URL in "+text)]
			item['Abstract']=PH.NC(entscheid.xpath("./tr[2]/td[@colspan='2']/b/text()").get(), info="kein Rechtsgebiet in "+text)
			abstract=entscheid.xpath("./tr[3]/td[@colspan='3']/text()").getall()
			if len(abstract)>0:
				item['Titel']=abstract[0]
			elif len(abstract)>1:
				del abstract[0]
				del abstract[0]
				item['Leitsatz']="<br>".join(abstract)
			item['Num']=PH.NC(entscheid.xpath("./tr/td/a/span/text()").get(), warning="keine Geschäftsnummer in "+text)
			num2=PH.NC(entscheid.xpath("./tr/td[2]/text()[contains(.,'(')]").get(), info="keine zweite Geschäftsnummer in "+text)
			if self.reNum2.search(num2):
				item['Num2']=self.reNum2.search(num2).group("Num2")
			if item['Num']=="":
				if 'Num2' in item and len(item["Num2"])>0:
					item['Num']=item['Num2']
					del item['Num2']
					logger.warning("Num nicht gesetzt, aber Num2 - daher nehme nun Num2 als Num")
				else:
					logger.error("Weder Num noch Num2 gefunden	")
				
			edatum_roh=PH.NC(entscheid.xpath("./tr/td[@align='right']/text()[contains(.,'Date décision:')]").get(), info="kein Entscheiddatum in "+text)
			if self.reDatumEinfach.search(edatum_roh):
				item['EDatum']=self.norm_datum(edatum_roh)
			pdatum_roh=PH.NC(entscheid.xpath("./tr/td[@colspan='2' and @align='right']/text()[contains(.,'Publié le:')]").get(), info="kein Publikationsdatum in "+text)
			if self.reDatumEinfach.search(pdatum_roh):
				item['PDatum']=self.norm_datum(pdatum_roh)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['Num'][:2],item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			yield request
	
		if seite*self.TREFFER_PRO_SEITE < trefferzahl:
			href=response.xpath("//table[@width='100%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td[@align='right']/a[last()-1]/@href").get()
			if href=="":
				logger.error("Blätterlink nicht gefunden: "+antwort)
			else:
				request=scrapy.Request(url=href, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1})
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
		
