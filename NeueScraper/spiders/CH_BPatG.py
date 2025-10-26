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


class CH_BPatG(BasisSpider):
	name = 'CH_BPatG'

	URL="/rechtsprechung/datenbankabfrage/?tx_iscourtcases_entscheidesuche[action]=suche&tx_iscourtcases_entscheidesuche[controller]=Entscheide&cHash=51983dbfa80eb8fd29d1420cc573e72c"
	BODY={ 'tx_iscourtcases_entscheidesuche[__referrer][@extension]': 'IsCourtcases',
		'tx_iscourtcases_entscheidesuche[__referrer][@controller]': 'Entscheide',
		'tx_iscourtcases_entscheidesuche[__referrer][@action]': 'suche',
		'tx_iscourtcases_entscheidesuche[__referrer][arguments]': 'YToyOntzOjY6ImFjdGlvbiI7czo1OiJzdWNoZSI7czoxMDoiY29udHJvbGxlciI7czoxMDoiRW50c2NoZWlkZSI7fQ==34f3c6454ebbcf14c77c24f9fce4c741960727ed',
		'tx_iscourtcases_entscheidesuche[__referrer][@request]': '{"@extension":"IsCourtcases","@controller":"Entscheide","@action":"suche"}176dd2db7e68517d648f8483d6068ac8c0851bf6',
		'tx_iscourtcases_entscheidesuche[__trustedProperties]': '{"match-fall_nummer":1,"match-titel_kurz":1,"match-gegenstand_long":1,"match-pdfinhalt":1,"range-urteils_datum-from":1,"range-urteils_datum-to":1,"multi-verfahren_typ":[1,1,1],"multi-verfahren_art":[1,1],"multi-status":[1,1,1,1,1,1,1,1],"join-gegenstand":[1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],"join-technischesgebiet":[1,1,1,1,1,1,1,1],"formsearch":1}9fa7fcf9cd1e11cd51064bfc182432d6aaa39f81',
		'tx_iscourtcases_entscheidesuche[match-fall_nummer]': '',
		'tx_iscourtcases_entscheidesuche[match-titel_kurz]': '',
		'tx_iscourtcases_entscheidesuche[match-pdfinhalt]': '',
		'tx_iscourtcases_entscheidesuche[range-urteils_datum-from]': '',
		'tx_iscourtcases_entscheidesuche[range-urteils_datum-to]': '',
		'tx_iscourtcases_entscheidesuche[multi-verfahren_typ]': '',
		'tx_iscourtcases_entscheidesuche[multi-verfahren_art]': '',
		'tx_iscourtcases_entscheidesuche[multi-status]': '',
		'tx_iscourtcases_entscheidesuche[join-gegenstand]': '',
		'tx_iscourtcases_entscheidesuche[join-technischesgebiet]': '',
		'tx_iscourtcases_entscheidesuche[formsearch]': '1'}
	HOST="https://www.bundespatentgericht.ch"

	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.FormRequest(url=self.HOST+self.URL,formdata=self.BODY,callback=self.parse_trefferliste, errback=self.errback_httpbin)]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		urteile=response.xpath("//ul[@class='results']/li")
		if len(urteile)==0:
			logger.warning("Keine Entscheide gefunden für "+response.meta['Gericht'])
		else:
			for entscheid in urteile:
				logger.info("Verarbeite nun: "+entscheid.get())
				url=entscheid.xpath("./a/@href").get()
				request = scrapy.Request(url=self.HOST+url, callback=self.parse_entry, errback=self.errback_httpbin)
				yield request


	def parse_entry(self, response):
		logger.info("parse_entry response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_entry Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_entry Rohergebnis: "+antwort[:20000])
		
		item={}
		item['PDFUrls']=[PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Entscheid als PDF')]/following-sibling::td/a/@href").get(),warning="kein PDF gefunden")]
		item['Num']=PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Prozessnummer')]/following-sibling::td/text()").get(),warning="kein Geschäftsnummer")
		item['EDatum']=self.norm_datum(PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Entscheiddatum')]/following-sibling::td/text()").get(),warning="kein Entscheiddatum"))
		item['Entscheidart']=PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Art des Verfahrens')]/following-sibling::td/text()").get(),info="keine Verfahrensart")
		wz1=PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Status')]/following-sibling::td/text()").get(),info="kein Status")
		wz2=PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Art des Entscheids')]/following-sibling::td/text()").get(),info="keine Entscheidart")
		item['Weiterzug']=(wz1+' '+wz2).strip()
		wz3=PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Link Bundesgericht')]/following-sibling::td/a/text()").get(),info="kein folgendes Bundesgerichtsurteil")
		if wz3:
			item['Weiterzug']+=' '+wz3
		item['Titel']=PH.NC(response.xpath("//div[@class='klassifizierung']/h2[contains(.,'Stichwort')]/following-sibling::p/text()").get(),info="kein Stichwort")
		gegenstand=response.xpath("//div[@class='klassifizierung']/h2[contains(.,'Gegenstand')]/following-sibling::*[1]/li/text()").getall()
		if len(gegenstand)>0:
			gstrip=[g.strip() for g in gegenstand]
			item['Leitsatz']=", ".join(gstrip)
		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])

		yield(item)

