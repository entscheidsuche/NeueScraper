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
	name = 'SH_OG'

	SUCH_URL='/index.php?id=89'
	HOST ="http://obergerichtsentscheide.sh.ch"
	FORMDATA = {
		"s": "",
		"suche": "Suchen",
		"u": ""
	}
	
	reTreffer=re.compile(r"</b>\sde\s(?P<Treffer>\d+)\sfiche\(s\)\strouvée\(s\)")
	reNum2=re.compile(r"\((?P<Num2>[^)]+)\)")
	
	def get_next_request(self):
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin)
		return request
	
	def __init__(self):
		super().__init__()
		self.request_gen = [self.get_next_request()]


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])

		entscheide=response.xpath("//table[@class='contenttable']/tbody/tr[td/p/a[@class='PDF']]")
		logger.info("Anzahl der gefundenen Entscheide: "+str(len(entscheide)))

		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			logger.debug("Eintrag: "+text)
			pdf=PH.NC(entscheid.xpath("./td/p/a/@href").get(),error="kein PDF gefunden in "+text)
			if pdf:
				item['PDFUrls']=[self.HOST+"/"+pdf]
			item['Leitsatz']=PH.NC(entscheid.xpath("./td[2]/p[2]/text()").get(),info="keinen Leitsatz gefunden in "+text)
			num=PH.NC(entscheid.xpath("./td/p/a/text()").get(),error="keine Geschäftsnummer gefunden in "+text)
			if num[:4]=="Nr. ":
				item['Num']=num[4:]
			else:
				logger.warning("Ungewöhnliche Geschäftsnummer: "+num)
				item['Num']=num
			edatum=PH.NC(entscheid.xpath("./td/p[2]").get(),warning="kein EDatum gefunden in "+text)
			if edatum:
				item['EDatum']=self.norm_datum(edatum)
			item['Titel']=PH.NC(entscheid.xpath("./td[2]/p[1]/strong/text()").get(),info="keinen Titel gefunden in "+text)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
			logger.info("Entscheid: "+json.dumps(item))
			yield item
