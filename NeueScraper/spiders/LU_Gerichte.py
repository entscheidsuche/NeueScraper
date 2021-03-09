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

class LU_Gerichte(BasisSpider):
	name = 'LU_Gerichte'
	HOST = 'https://gerichte.lu.ch'
	START_URL = '/recht_sprechung/lgve'
	TREFFER_PRO_SEITE = 50
	
	def get_request(self, ab=None):
		request=scrapy.Request(url=self.HOST+self.START_URL, callback=self.parse_form, errback=self.errback_httpbin)
		return request
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		self.request_gen = [self.get_request(ab)]


	def parse_form(self, response):
		logger.info("parse_form response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_form Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_form Rohergebnis: "+antwort[:30000])
		request = scrapy.FormRequest.from_response(response, formxpath=('//*[@id="maincontent_1_btnSearch"]'), callback=self.parse_weiter, meta={'Seite': 1})
		yield request

	def parse_weiter(self, response):
		logger.info("parse_weiter response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_weiter Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_weiter Rohergebnis: "+antwort[:30000])
		seite=response.meta['Seite']
		if seite>1:
			trefferzahl=response.meta['Trefferzahl']
		else:
			trefferzahl_string=PH.NC(response.xpath("//p/span[@id='maincontent_1_lblCountInfo' and contains(.,'Anzahl Treffer: ')]/text()").get(),error="keine Trefferzahl gefunden in: "+antwort)
			logger.info("Trefferzahlstring: "+trefferzahl_string)
			trefferzahl=int(trefferzahl_string[16:])
		entscheide=response.xpath("//tr[td/a[contains(@id,'maincontent_1_lstJurisdictions_hypCaseNr_') and contains(@href, 'lgve')]]")
		logger.info(str(len(entscheide))+" Entscheide auf dieser Seite")
		for entscheid in entscheide:
			item = {}
			text=entscheid.get()
			url=self.HOST+PH.NC(entscheid.xpath('.//a/@href').get(),error="keine URL gefunden in "+text)
			item['HTMLUrls']=[url]
			item['Leitsatz']=PH.NC(entscheid.xpath("./td[@style='width: 40%']/text()").get(), warning="kein Leitsatz in "+text)
			item['Num']=PH.NC(entscheid.xpath("./td/a/text()").get(), error="keine Geschäftsnummer in "+text)
			num2=PH.NC(entscheid.xpath("./td[@style='width: 20%'][3]/text()").get(), info="keine zweite Geschäftsnummer in "+text)
			if num2:
				item['Num2']=num2
			edatum_roh=PH.NC(entscheid.xpath("./td[@style='width: 20%'][1]/text()").get(), info="kein Entscheiddatum in "+text)
			item['EDatum']=self.norm_datum(edatum_roh)
			logger.info("Entscheid: "+json.dumps(item))
			request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
			yield request

		if trefferzahl>self.TREFFER_PRO_SEITE*seite:
			if len(entscheide)<self.TREFFER_PRO_SEITE:
				logger.error(f"Gehe von {self.TREFFER_PRO_SEITE} Treffer pro Seite aus. Insgesamt sind es {trefferzahl}. Dies ist Seite {seite} mit nur {len(entscheide)} Treffern.")
			request=scrapy.FormRequest.from_response(response, formdata={'maincontent_1$dprJurisdictions$ctl02$ctl00': ''}, callback = self.parse_weiter, dont_click = True, meta={'Seite': seite+1, "Trefferzahl": trefferzahl})
			yield request

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		textteile=response.xpath("//div[@id='JurisdictionPrintArea']")
		text=textteile.get()
		item['VGericht']=PH.NC(textteile.xpath(".//th[.='Gericht/Verwaltung:']/following-sibling::td/text()").get(),error="Gericht nicht gefunden in "+item['Num']+": '"+text+"'")
		vkammer=PH.NC(textteile.xpath(".//th[.='Abteilung:']/following-sibling::td/text()").get(),info="Kammer nicht gefunden in "+item['Num']+": '"+text+"'")
		if len(vkammer)>3:
			item['VKammer']=vkammer
		else:
			vkammer=""
		item['Rechtsgebiet']=PH.NC(textteile.xpath(".//th[.='Rechtsgebiet:']/following-sibling::td/text()").get(),info="Rechtsgebiet nicht gefunden in "+item['Num']+": '"+text+"'")
		item['Normen']=PH.NC(textteile.xpath(".//th[.='Gesetzesartikel:']/following-sibling::td/text()").get(),info="Normen nicht gefunden in "+item['Num']+": '"+text+"'")
		item['Weiterzug']=PH.NC(textteile.xpath(".//th[.='Rechtskraft:']/following-sibling::td/text()").get(),info="Rechtskraft/Weiterzug nicht gefunden in "+item['Num']+": '"+text+"'")
		html=text
		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],vkammer,item['Num'])
		PH.write_html(text, item, self)
		yield(item)
