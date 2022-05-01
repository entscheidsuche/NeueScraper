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
		'tx_iscourtcases_entscheidesuche[__referrer][@vendor]': 'INSOR',
		'tx_iscourtcases_entscheidesuche[__referrer][@controller]': 'Entscheide',
		'tx_iscourtcases_entscheidesuche[__referrer][@action]': 'suche',
		'tx_iscourtcases_entscheidesuche[__referrer][arguments]': 'YTowOnt9d1832fe8c68d48e2f4886424ba6600e672c8155d',
		'tx_iscourtcases_entscheidesuche[__referrer][@request]': 'a:4:{s:10:"@extension";s:12:"IsCourtcases";s:11:"@controller";s:10:"Entscheide";s:7:"@action";s:5:"suche";s:7:"@vendor";s:5:"INSOR";}24882d019518e3fcac6c345c8da7ae719b1534a4',
		'tx_iscourtcases_entscheidesuche[__trustedProperties]': 'a:12:{s:17:"match-fall_nummer";i:1;s:16:"match-titel_kurz";i:1;s:21:"match-gegenstand_long";i:1;s:15:"match-pdfinhalt";i:1;s:24:"range-urteils_datum-from";i:1;s:22:"range-urteils_datum-to";i:1;s:19:"multi-verfahren_typ";a:3:{i:0;i:1;i:1;i:1;i:2;i:1;}s:19:"multi-verfahren_art";a:2:{i:0;i:1;i:1;i:1;}s:12:"multi-status";a:8:{i:0;i:1;i:1;i:1;i:2;i:1;i:3;i:1;i:4;i:1;i:5;i:1;i:6;i:1;i:7;i:1;}s:15:"join-gegenstand";a:68:{i:0;i:1;i:1;i:1;i:2;i:1;i:3;i:1;i:4;i:1;i:5;i:1;i:6;i:1;i:7;i:1;i:8;i:1;i:9;i:1;i:10;i:1;i:11;i:1;i:12;i:1;i:13;i:1;i:14;i:1;i:15;i:1;i:16;i:1;i:17;i:1;i:18;i:1;i:19;i:1;i:20;i:1;i:21;i:1;i:22;i:1;i:23;i:1;i:24;i:1;i:25;i:1;i:26;i:1;i:27;i:1;i:28;i:1;i:29;i:1;i:30;i:1;i:31;i:1;i:32;i:1;i:33;i:1;i:34;i:1;i:35;i:1;i:36;i:1;i:37;i:1;i:38;i:1;i:39;i:1;i:40;i:1;i:41;i:1;i:42;i:1;i:43;i:1;i:44;i:1;i:45;i:1;i:46;i:1;i:47;i:1;i:48;i:1;i:49;i:1;i:50;i:1;i:51;i:1;i:52;i:1;i:53;i:1;i:54;i:1;i:55;i:1;i:56;i:1;i:57;i:1;i:58;i:1;i:59;i:1;i:60;i:1;i:61;i:1;i:62;i:1;i:63;i:1;i:64;i:1;i:65;i:1;i:66;i:1;i:67;i:1;}s:22:"join-technischesgebiet";a:8:{i:0;i:1;i:1;i:1;i:2;i:1;i:3;i:1;i:4;i:1;i:5;i:1;i:6;i:1;i:7;i:1;}s:10:"formsearch";i:1;}8a74b1708a99f8cfee2993c245dc03b4325848d8',
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
		antwort=response.body_as_unicode()
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
		antwort=response.body_as_unicode()
		logger.info("parse_entry Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_entry Rohergebnis: "+antwort[:20000])
		
		item={}
		item['PDFUrls']=[self.HOST+PH.NC(response.xpath("//table[@class='tx-is-courtcases']/tr/td[contains(.,'Entscheid als PDF')]/following-sibling::td/a/@href").get(),warning="kein PDF gefunden")]
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

