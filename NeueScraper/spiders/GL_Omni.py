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

class GL_Omni(BasisSpider):
	name = 'GL_Omni'
	custom_settings = {
		"CONCURRENT_REQUESTS_PER_DOMAIN": 1,
		"DOWNLOAD_DELAY": 2
	}


	SUCH_URL='/cgi-bin/nph-omniscgi.exe'
	HOST ="https://findinfo.gl.ch"
	TREFFER_PRO_SEITE = 10
	BLAETTERN_URL="/cgi-bin/nph-omniscgi.exe?OmnisPlatform=WINDOWS&WebServerUrl=findinfo.gl.ch&WebServerScript=/cgi-bin/nph-omniscgi.exe&OmnisLibrary=JURISWEB&OmnisClass=rtFindinfoWebHtmlService&OmnisServer=JURISWEB,7000&Parametername=WEB&Schema=GLWEB&Source=&Aufruf=search&cTemplate=simple%2Fsearch_result.fiw&cTemplate_ValidationError=simple%2Fsearch.fiw&cSprache=DE&nSeite={Seite}&nAnzahlTrefferProSeite="+str(TREFFER_PRO_SEITE)+"&W10_KEY={W10}&nAnzahlTreffer={Trefferzahl}"
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "findinfo.gl.ch",
		"WebServerScript": "/cgi-bin/nph-omniscgi.exe",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "JURISWEB,7000",
		"Schema": "GLWEB",
		"Parametername": "WEB",
		"Aufruf": "search",
		"cTemplate": "simple/search_result.fiw",
		"cTemplate_ValidationError": "simple/search.fiw",		
		"cSprache": "DE",
		"nSeite": "1",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"dEntscheiddatum": "",
		"dEntscheiddatumBis": "",
		"dPublikationsdatum": "",
		"dPublikationsdatumBis": "",
		"cSuchstring": "",
		"evSubmit": "",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE)
	}
	
	reTreffer=re.compile(r"</b>\svon\s(?P<Treffer>\d+)\sgefundenen\sEntscheid")
	reW10=re.compile(r"W10_KEY=(?P<Key>\d+)&")
	reNum2=re.compile(r"\((?P<Num2>[^)]+)\)")
	
	def get_next_request(self):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 1})
		return request
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
			self.FORMDATA['dPublikationsdatum']=ab
			self.FORMDATA['bHasPublikationsdatumBis']="1"
			self.FORMDATA['dPublikationsdatumBis']="01.01.2100"
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
			item['Rechtsgebiet']=PH.NC(entscheid.xpath("./tr[2]/td[@colspan='2']/b/text()").get(), info="kein Rechtsgebiet in "+text)
			abstract=entscheid.xpath("./tr[3]/td[@colspan='3']/text()").getall()
			if len(abstract)>0:
				item['Titel']=abstract[0]
			elif len(abstract)>1:
				del abstract[0]
				del abstract[0]
				item['Leitsatz']="<br>".join(abstract)
			item['Num']=PH.NC(entscheid.xpath("./tr/td/a/text()[contains(.,'.')]").get(), error="keine Geschäftsnummer in "+text)
			num2=PH.NC(entscheid.xpath("./tr/td[@nowrap='nowrap']/text()[contains(.,'(')]").get(), info="keine zweite Geschäftsnummer in "+text)
			if self.reNum2.search(num2):
				item['Num2']=self.reNum2.search(num2).group("Num2")
			edatum_roh=PH.NC(entscheid.xpath("./tr/td[@align='right']/text()[contains(.,'Entscheiddatum:')]").get(), info="kein Entscheiddatum in "+text)
			if self.reDatumEinfach.search(edatum_roh):
				item['EDatum']=self.norm_datum(edatum_roh)
			pdatum_roh=PH.NC(entscheid.xpath("./tr/td[@colspan='2' and @align='right']/text()[contains(.,'datum:')]").get(), info="kein Publikationsdatum in "+text)
			if self.reDatumEinfach.search(pdatum_roh):
				item['PDatum']=self.norm_datum(pdatum_roh)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['Num'][:2],item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			request=scrapy.Request(url=self.HOST+item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			yield request
	
		if seite*self.TREFFER_PRO_SEITE < trefferzahl:
			href=response.xpath("//table[@width='100%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0' and @border='0']/tr/td[@align='right']/a/@href")
			if href==[]:
				logger.error("Blätterlink nicht gefunden: "+antwort)
			else:
				href_string=href.get()
				W10=self.reW10.search(href_string)
				if W10:
					next_url=self.HOST+self.BLAETTERN_URL.format(W10=W10.group('Key'),Seite=str(seite+1),Trefferzahl=trefferzahl)
					request=scrapy.Request(url=next_url, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1})
					yield request
				else:
					logger.error("W10 für das Blättern nicht gefunden: "+antwort)

								
	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:40000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@class='WordSection1' or @class='Section1']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:40000])
		else:
			PH.write_html(html.get(), item, self)
		regeste=response.xpath("//td[@colspan='2']/table/tr/td[./b/text()='Résumé contenant:']/following-sibling::td/b/text()")
		if len(regeste)>0:
			item['Leitsatz']=regeste.get()
		yield(item)
		
