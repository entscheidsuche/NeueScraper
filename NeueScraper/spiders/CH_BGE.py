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

class CH_BGE(BasisSpider):
	name = 'CH_BGE'
	TAGSCHRITTE = 20
	AUFSETZJAHR = 1954


	SUCH_URL='/ext/eurospider/live/de/php/clir/http/index.php?lang=de&type=simple_query&query_words=&lang=de&top_subcollection_clir=bge&from_year={von}&to_year={bis}&x=27&y=18'
	HOST='https://www.bger.ch'
	
	SPRACHEN={"de": "D","fr": "F","it": "I"}
	
	reMeta=re.compile(r"^\d+\.\s+(?P<formal>.+(?:Urteil der|arrêt (?:de la|du)) (?P<VKammer>.+) (?:i\.S\.|dans la cause) [^_]+ (?P<Num2>\d+[A-F]?_\d+/(?:19|20)\d\d) (?:[^_]+ )?(?:vom|du) (?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr)+r")\s+(?:19|20)\d\d))$")
	reMetaSimple=re.compile(r"^\d+\.\s+(?P<Rest>.+)$")
	reRemoveDivs=re.compile(r"(</(div|span|a)>)|(<(div|span|a)[^>]+>)|(?:^<br>)|(?:<br>(?:(?=<br>)|$))")
	reDoubleSpaces=re.compile(r"\s\s+")

	def mache_request(self,jahr,seite=1):
		if seite:
			page="&page="+str(seite)
		else:
			page=""
		request = scrapy.Request(url=self.HOST+self.SUCH_URL.format(von=jahr, bis=jahr)+page, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite, 'Jahr': jahr})
		return request		

	def request_generator(self,ab=None):
		requests=[]
		bis=datetime.date.today().year
		if ab is None:
			von=self.AUFSETZJAHR
		else:
			von=int(ab)
		for jahr in range(von,bis+1):
			requests.append(self.mache_request(jahr))
		return requests
	
	def __init__(self, ab=None):
		super().__init__()
		# Hier stehen immer nur die neuen Entscheide. Daher nie gesamt holen und austauschen.
		self.ab=ab
		self.request_gen = self.request_generator(ab)


	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" URL: "+response.url)
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		jahr=response.meta['Jahr']
	
		treffer_match=response.xpath("//div[@class='content']/div[@class='ranklist_header center']/text()").get()
		if treffer_match is None:
			if response.xpath("//div[@class='content']/div[@class='ranklist_content center']/text()[contains(.,'keine Leitentscheide gefunden')]"):
				logger.info("keine Leitentscheide für "+str(jahr))
			else:
				logger.error("weder Treffer noch Meldung über keine Treffer gefunden in "+response.url)
		else:
			treffer=int(treffer_match.strip().split(" ")[0])
		
			anfangsposition=int(response.xpath("//div[@class='ranklist_content']/ol/@start").get())
			urteile=response.xpath("//div[@class='ranklist_content']/ol/li")

			logger.info("Liste von {} Urteilen. Start bei {} von {} Treffer".format(len(urteile),anfangsposition, treffer))
		
			for entscheid in urteile:
				text=entscheid.get()
				item={}
				item['Num']="BGE "+entscheid.xpath("./span/a/text()").get()
				item['HTMLUrls']=[entscheid.xpath("./span/a/@href").get()]
				meta=PH.NC(entscheid.xpath("./div[@class='rank_data']/div[@class='urt small normal']/text()").get(),error="keine Metadaten gefunden für "+item['Num']+": "+text)
				meta_parse=self.reMeta.search(meta)
				if meta_parse is None:
					meta_simple=self.reMetaSimple.search(meta)
					if meta_simple is None:
						logger.error("Eintrag nicht matchbar "+item['Num']+": "+meta+"\nin: "+text)
					else:
						logger.warning("Eintragsdetails nicht parsbar "+item['Num']+": "+meta+"\nin: "+text)
						item['Formal_org']=meta_simple.group('Rest')
				else:
					item['EDatum']=self.norm_datum(meta_parse.group('Datum'))
					item['VKammer']=meta_parse.group('VKammer')
					item['Num2']=meta_parse.group('Num2')
						
				subrequestliste=[]
				for sprache in self.SPRACHEN:
					url=entscheid.xpath("./div[@class='rank_data']/div[@class='regeste small normal']/a[text()='"+self.SPRACHEN[sprache]+"']/@href").get()
					if url:
						subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, meta={'item': item, 'Sprache': sprache}))
				if len(subrequestliste)==0:
					logger.info("Keine Links auf Regesten gefunden in "+text)
					item['Leitsatz']=PH.NC(entscheid.xpath("./div[@class='rank_data']/div[@class='regeste small normal']/text()").get(),warning="keine Regeste gefunden bei "+item['Num']+": "+text)
					
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'] if 'VKammer' in item else "",item['Num'])
				request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
				yield request
			if anfangsposition+len(urteile)<treffer:
				request=self.mache_request(jahr,response.meta['page']+1)
				yield request			

	def parse_regeste(self, response):
		logger.info("parse_regeste response.status "+str(response.status)+": "+response.url)
		antwort=response.body_as_unicode()
		logger.info("parse_regeste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_regeste Rohergebnis: "+antwort[:10000])
		
		item=response.meta['item']
		sprache=response.meta['Sprache']
		text_parse=response.xpath("//div[@id='highlight_content']")
		if text_parse:
			text=text_parse.get()
			text=self.reRemoveDivs.sub("",text).strip()
			text=self.reRemoveDivs.sub("",text).strip()
			text=self.reDoubleSpaces.sub(" ",text)
			item['Abstract_'+sprache]=text
		else:
			logger.warning("Content der Regeste ("+sprache+") nicht erkannt in "+antwort)
		subrequestliste=response.meta['requestliste']
		request=subrequestliste[0]
		del subrequestliste[0]
		request.meta['item']=item
		request.meta['requestliste']=subrequestliste
		yield(request)

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
