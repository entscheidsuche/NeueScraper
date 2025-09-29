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
from urllib.parse import quote

logger = logging.getLogger(__name__)

class CH_BGE(BasisSpider):
	name = 'CH_BGE'
	AUFSETZJAHR = 1954


	INITIAL_URL='/bge_helper/request.php?stub=https%3A%2F%2Fsearch.bger.ch%2Fext%2Feurospider%2Flive%2Fde%2Fphp%2Fclir%2Fhttp%2Findex_atf.php&lang=de'
	SUCH_URL='/bge_helper/request.php?stub=https%3A%2F%2Fsearch.bger.ch%2Fext%2Feurospider%2Flive%2Fde%2Fphp%2Fclir%2Fhttp%2Findex_atf.php&lang=de&zoom=&system=clir'
	EGMR_URL='/bge_helper/request.php?stub=https%3A%2F%2Fsearch.bger.ch%2Fext%2Feurospider%2Flive%2Fde%2Fphp%2Fclir%2Fhttp%2Findex_cedh.php&lang=de'
	HOST="https://entscheidsuche.ch"
	HELPER="/bge_helper/request.php?stub="
	# SUCH_URL='/ext/eurospider/live/de/php/clir/http/index_atf.php?year={band}&volume={volume}&lang=de&zoom=&system=clir'
	# EGMR_URL='/ext/eurospider/live/de/php/clir/http/index_cedh.php?lang=de'
	# HOST="https://search.bger.ch"
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
		'Referer': 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index_atf.php?lang=de',
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


	def mache_requests(self,jar_id,jahr):
		requests=[]
		for volume in ["I","II","III","IV","V"]:
			requests.append(scrapy.Request(url=self.HOST+self.SUCH_URL.format(band=jahr-1874, volume=volume), headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id, 'Volume': volume, 'Jahr': jahr}))
		#EGMR-Request: dort immer alle Entscheide parsen
		requests.append(scrapy.Request(url=self.HOST+self.EGMR_URL, headers=self.HEADER, callback=self.parse_EGMR_trefferliste, errback=self.errback_httpbin, meta={'cookiejar': jar_id}))
		return requests		

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
			requests=requests+self.mache_requests(jar_id,jahr)
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
		volume=response.meta['Volume']
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_trefferliste Cookie Jar ID: {jar_id}")

		urteile=response.xpath("//ol/li[a]")
		if urteile is None:
			logger.info("keine Leitentscheide für "+str(jahr)+" Volume "+volume)
		else:
			logger.info("Liste von {} Urteilen.".format(len(urteile)))
		
			for entscheid in urteile:
				text=entscheid.get()
				item={}
				item['Num']="BGE "+entscheid.xpath("./a/text()").get()
				item['HTMLUrls']=[entscheid.xpath("./a/@href").get()]
				url=item['HTMLUrls'][0]
				before, sep, after = url.partition('?')
				encoded = quote(before, safe='') 
				url=self.HOST+self.HELPER+encoded+"&"+after

				
				request = scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, headers=self.HEADER, meta={'cookiejar': jar_id, 'item': item, 'Jahr': jahr})
				
				subrequestliste=[]
				basisurl=item['HTMLUrls'][0]
				for sprache in self.SPRACHEN:
					url=basisurl.replace("%3Ade&lang=de","%3A"+sprache+"%3Aregeste&lang=de")
					subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, headers=self.HEADER, meta={'cookiejar': jar_id, 'item': item, 'Jahr': jahr, 'Sprache': sprache}))
					before, sep, after = url.partition('?')
					encoded = quote(before, safe='') 
					url=self.HOST+self.HELPER+encoded+"&"+after
				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
				yield request

	def parse_EGMR_trefferliste(self, response):
		logger.info("parse_EGMR_trefferliste response.status "+str(response.status)+" URL: "+response.url)
		antwort=response.text
		logger.info("parse_EGMR_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_EGMR_trefferliste Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_trefferliste Cookie Jar ID: {jar_id}")

		urteile=response.xpath("//table[@width='75%' and @style='border: 0px; border-collapse: collapse;']/tr[td]")
		if urteile is None:
			logger.error("keine EGMR-Entscheide")
		else:
			logger.info("Liste von {} Urteilen.".format(len(urteile)))
		
			for entscheid in urteile:
				item={}
				text=entscheid.get()
				item['Num']=PH.NC(entscheid.xpath("./td[2]/a/text()").get(),error="keine Geschäftsnummer in "+text)
				item['Num2']=PH.NC(entscheid.xpath("./td[4]/text()").get(),warning="keine Fallname in "+text)
				datumstring=PH.NC(entscheid.xpath("./td[1]/text()").get(),error="Kein Entscheiddatum in "+text)
				item["EDatum"]=PH.NC(self.norm_datum(datumstring),error="Kein parsbares Entscheiddatum '"+datumstring+"' in "+text)
				item['HTMLUrls']=[PH.NC(entscheid.xpath("./td[2]/a/@href").get(),error="Keine HTML URL in "+text)]
				url=item['HTMLUrls'][0]
				before, sep, after = url.partition('?')
				encoded = quote(before, safe='') 
				url=self.HOST+self.HELPER+encoded+"&"+after
				
				request = scrapy.Request(url=url, callback=self.parse_EGMR_document, errback=self.errback_httpbin, headers=self.HEADER, meta={'cookiejar': jar_id, 'item': item})
				
				subrequestliste=[]
				basisurl=item['HTMLUrls'][0]
				logger.info("basisurl: "+basisurl)
				for sprache in self.SPRACHEN:
					url=basisurl.replace(":de&lang=de",":"+sprache+":regeste&lang=de")
					logger.info("angepasste basisurl: "+url)
					before, sep, after = url.partition('?')
					encoded = quote(before, safe='') 
					url=self.HOST+self.HELPER+encoded+"&"+after
					subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, headers=self.HEADER, meta={'cookiejar': jar_id, 'item': item, 'Sprache': sprache}))
					
				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
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
		jahr=response.meta['Jahr']
		
		item=response.meta['item']	
			
		meta=response.xpath("//div[@class='paraatf']/text()")
		item['VKammer']=''
		if meta:
			meta_string=meta.get()
			meta_parse=self.reMeta.search(meta_string)
			if meta_parse is None:
				meta_ohneGN=self.reMetaOhneGN.search(meta_string)
				if meta_ohneGN is None:
					meta_simple=self.reMetaSimple.search(meta_string)
					if meta_simple is None:
						logger.error("Eintrag nicht matchbar "+item['Num']+": "+meta_string+"\nin: "+antwort)
					else:
						logger.warning("Eintragsdetails nicht parsbar "+item['Num']+": "+meta_string+"\nin: "+antwort)
						item['Formal_org']=meta_simple.group('Rest')
						item['EDatum']=self.norm_datum(str(jahr))
				else:
					logger.warning("Eintrags-Geschäftsnummer nicht parsbar "+ item['Num']+": "+meta_string+"\nin: "+antwort)
					item['EDatum']=self.norm_datum(meta_ohneGN.group('Datum'))
					item['VKammer']=meta_ohneGN.group('VKammer')					
			else:
				item['EDatum']=self.norm_datum(meta_parse.group('Datum'))
				item['VKammer']=meta_parse.group('VKammer')
				item['Num2']=meta_parse.group('Num2').replace(".","_")

		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],"")

		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)

		yield(item)
		
		
	def parse_EGMR_document(self, response):
		logger.info("parse_EGMR_document response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_EGMR_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_EGMR_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']	
			
		item['VKammer']='EGMR'

		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])

		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)

		yield(item)
