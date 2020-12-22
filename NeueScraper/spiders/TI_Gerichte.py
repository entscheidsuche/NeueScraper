# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class TessinSpider(BasisSpider):
	name = 'TI_Gerichte'
	custom_settings = {
        'COOKIES_ENABLED': True
    }

	SUCH_URL='/cgi-bin/nph-omniscgi'
	HOST ="https://www.sentenze.ti.ch"
	INIT_PARAMETER = "?OmnisPlatform=WINDOWS&WebServerUrl=www.sentenze.ti.ch&WebServerScript=/cgi-bin/nph-omniscgi&OmnisLibrary=JURISWEB&OmnisClass=rtFindinfoWebHtmlService&OmnisServer=JURISWEB,193.246.182.54:6000&Aufruf=loadTemplate&cTemplate=cerca.fiw&Schema=TI_WEB&cLanguage=ITA&Parametername=WWWTI&cSuchstringZiel=testo"
	TREFFER_PRO_SEITE = 100
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "www.sentenze.ti.ch",
		"WebServerScript": "/cgi-bin/nph-omniscgi",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "JURISWEB,193.246.182.54:6000",
		"Schema": "TI_WEB",
		"Parametername": "WWWTI",
		"Aufruf": "validate",
		"Template": "results/resultpage_ita.fiw",
		"nSeite": "1",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE),
		"cSprache": "ITA",
		"nMaxStiwos": "50",
		"nStiwosSchritt": "10",
		"nStiwosSeite": "1",
		"cSuchstring": "",
		"cSuchstringZiel": "testo",
		"cEntscheiddatumVonMonat": "",
		"cEntscheiddatumVonJahr": "",
		"cEntscheiddatumBisMonat": "",
		"cEntscheiddatumBisJahr": "",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"cButtonAction": "3.+Trova",
		"bInfoArt_Privatrecht1": "ICCA','IICCA','CCC','CDP','CEF",
		"bInfoArt_OeffentlichesRecht1": "TRAM','TPT','TCA','CDT','TE",
		"bInfoArt_Strafrecht1": "TPC','CCRP','CRP','GIAR','PP",
		"bInfoArt_ICCA1": "ICCA",
		"bInfoArt_IICCA1": "IICCA",
		"bInfoArt_IIICC1": "IIICC",
		"bInfoArt_CCR1": "CCR",
		"bInfoArt_CCC1": "CCC",
		"bInfoArt_CEF1": "CEF",
		"bInfoArt_CDP1": "CDP",
		"bInfoArt_TRAM1": "TRAM",
		"bInfoArt_TPT1": "TPT",
		"bInfoArt_TCA1": "TCA",
		"bInfoArt_CDT1": "CDT",
		"bInfoArt_TE1": "TE",
		"bInfoArt_PENAL1": "PENAL",
		"bInfoArt_CARP1": "CARP",
		"bInfoArt_CCRP1": "CCRP",
		"bInfoArt_CRPTI1": "CRPTI",
		"bInfoArt_CRP1": "CRP",
		"bInfoArt_GPC1": "GPC",
		"bInfoArt_GIAR1": "GIAR",
		"bInfoArt_PRPEN1": "PRPEN"
	}
	HEADERS = {
		'Origin': 'https://www.sentenze.ti.ch',
		'Referer': 'https://www.sentenze.ti.ch/cgi-bin/nph-omniscgi?OmnisPlatform=WINDOWS&WebServerUrl=www.sentenze.ti.ch&WebServerScript=/cgi-bin/nph-omniscgi&OmnisLibrary=JURISWEB&OmnisClass=rtFindinfoWebHtmlService&OmnisServer=JURISWEB,193.246.182.54:6000&Aufruf=loadTemplate&cTemplate=cerca.fiw&Schema=TI_WEB&cLanguage=DEU&Parametername=WWWTI&cSuchstringZiel=testo'
	}
	reMeta=re.compile(r"Autorità:\s+(?P<Kammer>[A-Z]+), data decisione:\s+(?P<EDatum>\d\d\.\d\d\.(?:19|20)\d\d)?, data pubblicazione:\s+(?P<PDatum>\d\d\.\d\d\.(?:19|20)\d\d)")
	
	
	def request_generator(self):
		request=scrapy.Request(url=self.HOST+self.SUCH_URL+self.INIT_PARAMETER, callback=self.parse_suchform, headers=self.HEADERS, errback=self.errback_httpbin)
		return [request]
	
	def __init__(self, ab=None):
		super().__init__()
		if ab:
			self.ab=ab
			self.FORMDATA['cEntscheiddatumVonJahr']=ab
		self.request_gen = self.request_generator()

	def parse_suchform(self, response):
		# Nur zum Cookie-setzen
		logger.info("parse_suchform response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_suchform Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_suchform Rohergebnis: "+antwort[:10000])
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, headers=self.HEADERS, errback=self.errback_httpbin, meta={'page': 1})
		yield request


	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		
		treffer=response.xpath("//table/tr/td[@colspan='2']/span[@class='p10bcolor']/text()[2]").get()
		logger.info("Trefferzahl: "+treffer)
		trefferzahl=int(treffer.split(" di ")[1])
		seite=response.meta['page']
		
		entscheide=response.xpath("//table[@width='750']/tr/td/table[@width='100%']/tr/td[@valign='top']/table[@cellpadding='0']")
		logger.info("Entscheide in dieser Liste: "+str(len(entscheide)))
		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			item['HTMLUrls']=[PH.NC(entscheid.xpath("./tr[1]/td[2]/a/@href").get(),error="keine URL in "+text).strip()]
			item['Titel']=PH.NC(entscheid.xpath("./tr[1]/td[2]/a/text()").get(), info="keine Regeste in "+text).strip()
			meta=PH.NC(entscheid.xpath("./tr[2]/td[2]/text()").get(), error="keine Meta in "+text).strip()
			item['Num']=PH.NC(entscheid.xpath("./tr[3]/td[2]/text()").get(), error="keine Geschäftsnummer in "+text).strip()
			item['Weiterzug']=PH.NC(entscheid.xpath("./tr[4]/td[2]/text()").get()).strip()
			metas=self.reMeta.search(meta)
			if metas is None:
				logger.error("Metainformation nicht erkannt in '"+meta+"' in '"+text+"'")
			else:
				item['EDatum']=self.norm_datum(metas.group('EDatum'))
				item['PDatum']=self.norm_datum(metas.group('PDatum'))
				kurz="#"+metas.group('Kammer')+"#"
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",kurz,item['Num'])
				logger.info("Entscheid: "+json.dumps(item))
				request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
				yield request
		if seite*self.TREFFER_PRO_SEITE < trefferzahl:
			self.FORMDATA['nSeite']=str(seite+1)
			request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, headers=self.HEADERS, errback=self.errback_httpbin, meta={'page': seite+1})
			yield request

								
	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:10000])
		
		item=response.meta['item']			
		html=response.xpath("//div[@class='WordSection1' or @class='Section1']")
		item['html']=html.get()
		item['HTMLFiles']=[{'url': item['HTMLUrls'][0]}]
		yield(item)
		
