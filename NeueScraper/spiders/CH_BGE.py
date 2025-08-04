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
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware

logger = logging.getLogger(__name__)

class CH_BGE(BasisSpider):
	name = 'CH_BGE'
	AUFSETZJAHR = 1954


	INITIAL_URL='/ext/eurospider/live/de/php/clir/http/index.php'
	SUCH_URL='/ext/eurospider/live/de/php/clir/http/index.php?lang=de&type=simple_query&query_words=&lang=de&top_subcollection_clir=bge&from_year={von}&to_year={bis}&x=27&y=18'
	HOST='https://www.bger.ch'
	# https://search.bger.ch/ext/eurospider/live/de/php/clir/http
	
	SPRACHEN={"de": "D","fr": "F","it": "I"}
	
	reMeta=re.compile(r"^\d+\.\s+(?P<formal>.+(?:Urteil der|arrêt (?:de la|du)) (?P<VKammer>.+) (?:i\.S\.|dans la cause) [^_]+ (?P<Num2>\d+[A-F]?(?:_|\.)\d+/(?:19|20)\d\d) (?:[^_]+ )?(?:vom|du)\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr)+r")\s+(?:19|20)\d\d))$")
	reMetaOhneGN=re.compile(r"^\d+\.\s+(?P<formal>.+(?:Urteil der|arrêt (?:de la|du)) (?P<VKammer>.+) (?:i\.S\.|dans la cause) [^_]+ (?:vom|du)\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr)+r")\s+(?:19|20)\d\d))$")
	reMetaSimple=re.compile(r"^\d+\s?\.\s+(?P<Rest>.+)$")
	reRemoveDivs=re.compile(r"(</(div|span|a|artref)>)|(<(div|span|a|artref)[^>]+>)|(?:^<br>)|(?:<br>(?:(?=<br>)|$))")
	reDoubleSpaces=re.compile(r"\s\s+")

	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Referer': 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index.php',
		'Upgrade-Insecure-Requests': '1',
		'Sec-Fetch-Dest': 'document',
		'Sec-Fetch-Mode': 'navigate',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-User': '?1',
		'Priority': 'u=0, i',
		'Pragma': 'no-cache',
		'Cache-Control': 'no-cache',
		'TE': 'trailers'
	}
	custom_settings = {
		"COOKIES_ENABLED": True,
		"COOKIES_DEBUG": True,   # optional
	}


	def mache_request(self,jar_id,jahr,seite=1):
		if seite:
			page="&page="+str(seite)
		else:
			page=""
		request = scrapy.Request(url=self.HOST+self.SUCH_URL.format(von=jahr, bis=jahr)+page, headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, cookies={'powHash': '0000d05cb3cc07bd2ede4bfee13c80e587c6a816dd325afe2085f931b8d7c0a0', 'powNonce': '4554'}, meta={'cookiejar': jar_id, 'page': seite, 'Jahr': jahr})
		return request		

	def initial_request(self):
		requests=[scrapy.Request(url=self.HOST+self.INITIAL_URL, headers=self.HEADER, meta={'cookiejar': 0}, callback=self.parse_cookie)]
		return requests

	def parse_cookie(self, response):
		antwort=response.text
		logger.info("parse_cookie Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_cookie Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_cookie Cookie Jar ID: {jar_id}")
		cm = next(mw for mw in self.crawler.engine.downloader.middleware.middlewares if isinstance(mw, CookiesMiddleware))
		cookies=json.dumps([{"name": c.name,"value": c.value,"domain": c.domain,"path": c.path,"expires": c.expires,"secure": c.secure,"discard": c.discard,"rest": getattr(c, "_rest", {})} for c in cm.jars[jar_id] ],ensure_ascii=False)
		logger.info("Cookies: "+cookies)
		requests = self.request_generator(jar_id,self.ab)
		logger.info(f"{len(requests)} Requests")
		for r in requests:
			yield r

	def request_generator(self,jar_id,ab=None):
		requests=[]
		bis=datetime.date.today().year
		if ab is None:
			von=self.AUFSETZJAHR
		else:
			von=int(ab)
		for jahr in range(von,bis+1):
			requests.append(self.mache_request(jar_id,jahr))
		return requests

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		self.ab=ab
		self.request_gen = self.initial_request()


	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" URL: "+response.url)
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		jahr=response.meta['Jahr']
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_trefferliste Cookie Jar ID: {jar_id}")


	
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
					meta_ohneGN=self.reMetaOhneGN.search(meta)
					if meta_ohneGN is None:
						meta_simple=self.reMetaSimple.search(meta)
						if meta_simple is None:
							logger.error("Eintrag nicht matchbar "+item['Num']+": "+meta+"\nin: "+text)
						else:
							logger.warning("Eintragsdetails nicht parsbar "+item['Num']+": "+meta+"\nin: "+text)
							item['Formal_org']=meta_simple.group('Rest')
							item['EDatum']=self.norm_datum(str(jahr))
					else:
						logger.warning("Eintrags-Geschäftsnummer nicht parsbar "+ item['Num']+": "+meta+"\nin: "+text)
						item['EDatum']=self.norm_datum(meta_ohneGN.group('Datum'))
						item['VKammer']=meta_ohneGN.group('VKammer')					
				else:
					item['EDatum']=self.norm_datum(meta_parse.group('Datum'))
					item['VKammer']=meta_parse.group('VKammer')
					item['Num2']=meta_parse.group('Num2').replace(".","_")
						
				subrequestliste=[]
				for sprache in self.SPRACHEN:
					url=entscheid.xpath("./div[@class='rank_data']/div[@class='regeste small normal']/a[text()='"+self.SPRACHEN[sprache]+"']/@href").get()
					if url:
						subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, headers=self.HEADER, cookies={'powHash': '0000d05cb3cc07bd2ede4bfee13c80e587c6a816dd325afe2085f931b8d7c0a0', 'powNonce': '4554'}, meta={'cookiejar': jar_id, 'item': item, 'Sprache': sprache}))
				if len(subrequestliste)==0:
					logger.info("Keine Links auf Regesten gefunden in "+text)
					item['Leitsatz']=PH.NC(entscheid.xpath("./div[@class='rank_data']/div[@class='regeste small normal']/text()").get(),warning="keine Regeste gefunden bei "+item['Num']+": "+text)
					
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'] if 'VKammer' in item else "",item['Num'])
				request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, headers=self.HEADER, cookies={'powHash': '0000d05cb3cc07bd2ede4bfee13c80e587c6a816dd325afe2085f931b8d7c0a0', 'powNonce': '4554'}, meta={'cookiejar': jar_id, 'item': item})
				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
				yield request
			if anfangsposition+len(urteile)<treffer:
				request=self.mache_request(jar_id,jahr,response.meta['page']+1)
				yield request			

	def parse_regeste(self, response):
		logger.info("parse_regeste response.status "+str(response.status)+": "+response.url)
		antwort=response.text
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
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
