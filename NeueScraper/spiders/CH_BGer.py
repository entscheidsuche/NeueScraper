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

class CH_BGer(BasisSpider):
	name = 'CH_BGer'
	TAGSCHRITTE = 20
	AUFSETZTAG = "01.01.2000"
	DELTA=datetime.timedelta(days=TAGSCHRITTE-1)
	EINTAG=datetime.timedelta(days=1)

	INITIAL_URL='/ext/eurospider/live/de/php/aza/http/index.php'
	SUCH_URL='/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=simple_query&query_words=&top_subcollection_aza=all&from_date={von}&to_date={bis}&x=22&y=14'
	HOST='https://www.bger.ch'
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

	def mache_request(self,jar_id, von="",bis="",seite=1):
		logger.info(f"mache_request von {von} bis {bis}")
		if seite:
			page="&page="+str(seite)
		else:
			page=""
		request = scrapy.Request(url=self.HOST+self.SUCH_URL.format(von=von,bis=bis)+page, headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, cookies={'powHash': '0000d05cb3cc07bd2ede4bfee13c80e587c6a816dd325afe2085f931b8d7c0a0', 'powNonce': '4553'}, meta={'cookiejar': jar_id, 'page': seite, 'von': von, 'bis': bis})
		return request		

	def request_generator(self,jar_id,ab=None):
		requests=[]
		if ab is None:
			requests=[self.mache_request("",self.AUFSETZTAG)]
			von=(datetime.datetime.strptime(self.AUFSETZTAG,"%d.%m.%Y")+self.EINTAG).date()
		else:
			von=datetime.datetime.strptime(ab,"%d.%m.%Y").date()
		heute=datetime.date.today()
		while von<heute:
			bis=von+self.DELTA
			logger.info(f"request_generator von {von} bis {bis}")		
			requests.append(self.mache_request(jar_id,von.strftime("%d.%m.%Y"),bis.strftime("%d.%m.%Y")))
			von=bis+self.EINTAG
		return requests
		
	def initial_request(self):
		requests=[scrapy.Request(url=self.HOST+self.INITIAL_URL, headers=self.HEADER, meta={'cookiejar': 0}, callback=self.parse_cookie)]
		return requests
	
	def __init__(self, ab=None, neu=None):
		super().__init__()
		# Hier stehen immer nur die neuen Entscheide. Daher nie gesamt holen und austauschen.
		self.ab=ab
		self.neu=neu
		self.request_gen = self.initial_request()
		
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


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_trefferliste Cookie Jar ID: {jar_id}")
	
		trefferstring=PH.NC(response.xpath("//div[@class='content']/div[@class='ranklist_header center']/text()").get(),info="Trefferzahl nicht gefunden in: "+antwort)
		if trefferstring=="":
			no_treffer=response.xpath("//div[@class='content']/div[@class='ranklist_content center']/text()").get()
			if no_treffer and "keine Urteile gefunden" in no_treffer:
				logger.info("keine Urteile im Zeitraum "+response.meta['von']+"-"+response.meta['bis'])
			else:
				logger.error("Weder Trefferzahl noch 'keine Treffer' gefunden in: "+response.url+": "+antwort)
		else:
			treffer=int(trefferstring.split(" ")[0])
			anfangsposition=int(response.xpath("//div[@class='ranklist_content']/ol/@start").get())
			urteile=response.xpath("//div[@class='ranklist_content']/ol/li")

			logger.info("Liste von {} Urteilen. Start bei {} von {} Treffer".format(len(urteile),anfangsposition, treffer))
		
			for entscheid in urteile:
				item={}
				text=entscheid.get()
				meta=entscheid.xpath("./span/a/text()").get()
				item['HTMLUrls']=[entscheid.xpath("./span/a/@href").get()]
				titel=entscheid.xpath("./div/div[3]/text()").get()
				if titel:
					item['Titel']=titel.strip()
				item['VKammer']=PH.NC(entscheid.xpath("./div/div[1]/text()").get(), warning="Kammerzeile nicht geparst: "+text)
				item['Rechtsgebiet']=PH.NC(entscheid.xpath("./div/div[2]/text()").get(), warning="Rechtsgebietszeile nicht geparst: "+text)
			
				if self.reDatumEinfach.search(meta) is None:
					logger.error("Konnte Datum in meta nicht erkennen: "+meta)
				else:
					item['EDatum']=self.norm_datum(meta)
					item['Num']=meta[11:]
					space=item['Num'].find(' ')
					if space>1 and space < 5:
						item['Num2']=item['Num'].replace(" ","_")
						logger.info("Ersetze Leerzeichen in "+item['Num']+": "+item['Num2'])
						
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])
					request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, cookies={'powHash': '0000d05cb3cc07bd2ede4bfee13c80e587c6a816dd325afe2085f931b8d7c0a0', 'powNonce': '4553'}, meta={'item': item})
					yield request
			if anfangsposition+len(urteile)<treffer:
				request=self.mache_request(jar_id, response.meta['von'],response.meta['bis'],response.meta['page']+1)
				yield request			

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
