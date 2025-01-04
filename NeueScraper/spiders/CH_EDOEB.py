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
import urllib

logger = logging.getLogger(__name__)


class CH_EDOEB(BasisSpider):
	name = 'CH_EDOEB'

	URLs=[{'URL':"/edoeb/de/home/kurzmeldungen.html",'Kammer':'Kurzmeldungen'},{'URL':"/edoeb/de/home/deredoeb/infothek/archiv-ds.html",'Kammer': 'Archiv'},{'URL':"/edoeb/de/home/deredoeb/infothek/infothek-ds.html", 'Kammer': "Infothek"},{'URL':"/edoeb/de/home/oeffentlichkeitsprinzip/bgoe_empfehlungen.html",'Kammer':'Oeffentlichkeitsgesetz'}]
	HOST="https://www.edoeb.admin.ch"
	
	def __init__(self, neu=None):
		self.neu=neu
		super().__init__()
		self.request_gen = [scrapy.Request(url=self.HOST+entry['URL'],callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={"Kammer":entry['Kammer']}) for entry in self.URLs]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+response.request.url+" "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:80000])
		urteile=response.xpath("//div[(@class='mod mod-teaser clearfix ' and h4[a]) or (@class='mod mod-download' and p[a])]")
		abschnitte=response.xpath('//div[@class="row" and div[div[div[ul[@class="list-unstyled " and li[a[@class="icon icon--before icon--pdf"]]]]]]]')
		logger.info(str(len(urteile))+" Abschnitte Pattern1 gefunden und "+str(len(abschnitte))+" Abschnitte Pattern2 gefunden für "+response.meta['Kammer']+" ("+response.url+")")
		if len(urteile)==0 and len(abschnitte)==0:
			logger.warning("Keine Entscheide gefunden für "+response.url)
		elif len(abschnitte)>0:
			for a in abschnitte:
				rubrik=PH.NC(a.xpath("//h3/text()").get(),replace="",warning="keine Rubrik")
				logger.info("Rubrik "+rubrik)
				texte=a.xpath('.//li/a[@class="icon icon--before icon--pdf"]')
				for t in texte:
					item={}
					logger.info("text Verarbeite nun: "+t.get())
					url=urllib.parse.unquote(t.xpath("./@href").get())
					logger.info("text URL: "+url)
					if url[-4:].lower()==".pdf":
						item['PDFUrls']=[self.HOST+url]
						logger.info("text PDF-URL: "+item['PDFUrls'][0])
					elif url[-4:].lower()==".htm" or url[-5:].lower()==".html":
						item['HTMLUrls']=[self.HOST+url]
						logger.info("text HTML-URL: "+item['HTMLUrls'][0])
					else:
						logger.error("text unbekannter Dokumenttyp bei "+url)
					titel=PH.NC(a.xpath("./@title").get(),replace="",warning="kein Titel")
					if titel:
						item['Titel']=titel
						item['Rechtsgebiet']=rubrik
					else:
						item['Titel']=rubrik
					if a.xpath("./span/text()"):
						datumstext=a.xpath("./span/text()").get()
						edatum=self.norm_datum(datumstext, warning="text Kein Datum identifiziert")
						if edatum!="nodate":
							item['EDatum']=edatum
					item['Num']=''
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",response.meta['Kammer'],item['Num'])
					if ('HTMLUrls' in item):
						logger.info("text Hole HTML")
						request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_html, errback=self.errback_httpbin, meta={'item': item})
						yield request
					else:
						logger.info("text Lege PDF-Dokument ab: "+json.dumps(item))
						yield item
		else:
			for entscheid in urteile:
				item={}
				logger.info("Verarbeite nun: "+entscheid.get())
				url=urllib.parse.unquote(entscheid.xpath("./*/a/@href").get())
				if url[-4:].lower()==".pdf":
					item['PDFUrls']=[self.HOST+url]
					logger.info("PDF-URL: "+item['PDFUrls'][0])
				elif url[-4:].lower()==".htm" or url[-5:].lower()==".html":
					item['HTMLUrls']=[self.HOST+url]
					logger.info("HTML-URL: "+item['HTMLUrls'][0])
				else:
					logger.error("unbekannter Dokumenttyp bei "+url)
							
				meta=entscheid.xpath("./*/a/@title").get()
				metas=meta.split(": ",1)
				edatum=self.norm_datum(metas[0], warning="Kein Datum identifiziert")
				if edatum!="nodate":
					item['EDatum']=edatum
				if len(metas)>1:
					item['Titel']=metas[1]
					item['Num']=metas[1]
				else:
					item['Num']=''
					item['Titel']=''
				if entscheid.xpath("./div[class='wrapper']/div"):
					item['Leitsatz']=entscheid.xpath("./div[class='wrapper']/div/text()").get()
					logger.info("Leitsatz gefunden: "+item['Leitsatz'])
				else:
					logger.info("keinen Leitsatz gefunden")
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",response.meta['Kammer'],item['Num'])
				if ('HTMLUrls' in item):
					logger.info("Hole HTML")
					request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_html, errback=self.errback_httpbin, meta={'item': item})
					yield request
				else:
					logger.info("Lege PDF-Dokument ab: "+json.dumps(item))
					yield item

	def parse_html(self, response):
		logger.info("parse_html response.status "+response.request.url+" "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_html Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_html Rohergebnis: "+antwort[:80000])
		
		item=response.meta['item']
		item['Titel']=PH.NC(response.xpath('//div[@class="mod mod-headline"]/h2/text()').get(),replace=item['Titel'],warning="Kein Titel in "+antwort)
		
		html=response.xpath('//div[@class="mod mod-headline"]/h2')
		html+=response.xpath('//div[@class="mod mod-text"]/article/*')
		html+=response.xpath('//div[@class="clearfix"]/p')
		html+=response.xpath('//div[@class="mod mod-link"]/p')
		if html == []:
			logger.error("Content nicht erkannt in "+antwort[:20000])
		else:
			htmltext=""
			for element in html:
				htmltext+=element.get()
			PH.write_html(htmltext, item, self)
			yield(item)
	