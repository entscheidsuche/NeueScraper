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


class SO_Omni(BasisSpider):
	name = 'SO_Omni'
	#Solothurn benötigt Cookies aber die scrapy-Cookies funktionieren nicht. Daher selber machen.

	custom_settings = {
        'COOKIES_ENABLED': True
    }

	SUCH_URL='/cgi-bin/nph-omniscgi.exe'
	HOST ="https://gerichtsentscheide.so.ch"
	TREFFER_PRO_SEITE = 50
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "https://gerichtsentscheide.so.ch",
		"WebServerScript": "/cgi-bin/nph-omniscgi.exe",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "7001",
		"Schema": "JGWEB",
		"Parametername": "WEB",
		"Aufruf": "validate",
		"cTemplate": "/simple/search_resulttable.html",
		"cTemplate_ValidationError": "search.html",		
		"cSprache": "DE",
		"nSeite": "1",
		"cHerausgabejahr": "",
		"cHerausgabenummer": "",
		"bSOGOnly": "0",
		"dEntscheiddatum": "",
		"dEntscheiddatumBis": "",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"cSuchstringZiel": "F37_HTML",
		"cSuchstring": "",
		"bInstanzInt": "true",
		"bInstanzInt_AK": "AK",
		"bInstanzInt_BK": "BK",
		"bInstanzInt_JK": "JK",
		"bInstanzInt_OG": "OG",
		"bInstanzInt_SC": "SC",
		"bInstanzInt_SK": "SK",
		"bInstanzInt_SG": "SG",
		"bInstanzInt_ST": "ST",
		"bInstanzInt_VS": "VS",
		"bInstanzInt_VW": "VW",
		"bInstanzInt_ZK": "ZK",
		"bInstanzInt_#NULL": "#NULL",	
		"evSubmit": "",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE)
	}
	
	reTreffer=re.compile(r"</b>\svon\s(?P<Treffer>\d+)\sgefundenen\sGeschäft")
	reNum2=re.compile(r"\((?P<Num2>[^)]+)\)")
	
	def get_next_request(self):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 1})
		return request
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
			self.FORMDATA['dEntscheiddatum']=ab
			self.FORMDATA['dEntscheiddatumBis']=datetime.date.today().strftime("%d.%m.%Y")
			self.FORMDATA['bHasEntscheiddatumBis']="1"
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.info(f"<X>Request-URL: '{response.request.url}', Headers: {json.dumps({ k.decode('UTF-8'): response.request.headers[k].decode('UTF-8') for k in response.request.headers})}, Body: '{response.request.body}'")
		logger.info("parse_trefferliste response.status "+str(response.status))
		Cookie=""
		if 'Cookie' in response.request.headers:
			logger.info("parse_trefferliste Cookie gesendet: "+response.request.headers['Cookie'].decode('UTF-8'))	
		else:
			logger.info("Im Trefferlistenrequest gibt es keine Cookies.")
		if 'Set-Cookie' in response.headers:
			logger.info("parse_trefferliste Cookie erhalten: "+response.headers['Set-Cookie'].decode('UTF-8'))
			Cookie=response.headers['Set-Cookie'].decode('UTF-8').split(";")[0]
		else:
			logger.info("In der Trefferlistenresponse gibt es keine Cookies.")
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort)
	
		treffer=PH.NC(response.xpath("//table[@width='100%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td[@width='50%']").get(),error="keine Trefferzahl erkannt!")
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
			item['HTMLUrls']=[self.HOST+PH.NC(entscheid.xpath("./tr/td/a/@href").get(),error="keine URL in "+text)]
			item['Rechtsgebiet']=PH.NC(entscheid.xpath("./tr[2]/td[@colspan='2']/b/text()").get(), info="kein Rechtsgebiet in "+text)
			abstract=entscheid.xpath("./tr[3]/td[@colspan='3']/text()").getall()
			if len(abstract)>0:
				item['Titel']=abstract[0]
			elif len(abstract)>1:
				del abstract[0]
				del abstract[0]
				item['Leitsatz']="<br>".join(abstract)
			item['Num']=PH.NC(entscheid.xpath("./tr/td/a/span/text()[contains(.,'.')]").get(), error="keine Geschäftsnummer in "+text)
			num2=PH.NC(entscheid.xpath("./tr/td[2]/text()[contains(.,'(')]").get(), info="keine zweite Geschäftsnummer in "+text)
			if self.reNum2.search(num2):
				item['Num2']=self.reNum2.search(num2).group("Num2")
			edatum_roh=PH.NC(entscheid.xpath("./tr/td[@align='right']/text()[contains(.,'Entscheiddatum:')]").get(), info="kein Entscheiddatum in "+text)
			if self.reDatumEinfach.search(edatum_roh):
				item['EDatum']=self.norm_datum(edatum_roh)
			pdatum_roh=PH.NC(entscheid.xpath("./tr/td[@colspan='2' and @align='right']/text()[contains(.,'Erstpublikationsdatum:')]").get(), info="kein Publikationsdatum in "+text)
			if self.reDatumEinfach.search(pdatum_roh):
				item['PDatum']=self.norm_datum(pdatum_roh)
			item['Signatur'], item['	'], item['Kammer'] = self.detect("",item['Num'][:2],item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item, 'org': item['HTMLUrls'][0]})
			if Cookie:
				request.headers['Cookie']=Cookie.encode('UTF-8')
				logger.info("Cookie gesetzt: "+request.headers['Cookie'].decode("utf-8"))
			yield request
	
		if seite*self.TREFFER_PRO_SEITE < trefferzahl:
			href=self.HOST+response.xpath("//table[@width='100%' and @border='0' and @cellspacing='0' and @cellpadding='0']/tr/td/table[@width='100%' and @cellspacing='0' and @cellpadding='0']/tr/td[@align='right']/a[last()-1]/@href").get()
			if href=="":
				logger.error("Blätterlink nicht gefunden: "+antwort)
			else:
				request=scrapy.Request(url=href, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1})
				if Cookie:
					request.headers['Cookie']=Cookie.encode('UTF-8')
					logger.info("Cookie gesetzt: "+request.headers['Cookie'].decode("utf-8"))
				yield request
								
	def parse_document(self, response):
		logger.info(f"<X>Request-URL: '{response.request.url}', Org-URL: '{response.meta['org']}', Headers: {json.dumps({ k.decode('UTF-8'): response.request.headers[k].decode('UTF-8') for k in response.request.headers})}, Body: '{response.request.body}'")
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort)
		if 'Cookie' in response.request.headers:
			logger.debug("parse_document Cookie gesendet: "+response.request.headers['Cookie'].decode('UTF-8'))	
		else:
			logger.debug("Im Documentrequest komme keine Cookies an.")
		if 'Set-Cookie' in response.headers:
			logger.debug("parse_document Cookie erhalten: "+response.headers['Set-Cookie'].decode('UTF-8'))
		else:
			logger.debug("In der Documentresponse gibt es keine Cookies.")
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
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
