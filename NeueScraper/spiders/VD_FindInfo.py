# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
import json
import copy
import urllib3

from urllib.parse import quote, unquote
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import MyFilesPipeline
from NeueScraper.pipelines import PipelineHelper as PH
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware



logger = logging.getLogger(__name__)

class VD_FindInfoSpider(BasisSpider):
	name = 'VD_FindInfo'
	
	custom_settings = {
        'COOKIES_ENABLED': True,
		"COOKIES_DEBUG": True
	}


	HOST ="https://prestations.vd.ch"
	SUCH_URL='/pub/101623/api/search'
	COOKIE_URL="/pub/101623/"
	PDF_URL='/pub/101623/api/decision/download/'
	STARTJAHR=2009
	ab=None
	reMeta=re.compile(r'<b>Cour</b>:\s<acronym title=\"(?P<VKammer>[^\"]+)\">(?P<Kurz>[^<]+)</acronym>\s*<br>\s*(?:<b>Date\s(?:décision</b>:\s(?:<span class="highlight">)?(?P<EDatum>[^<]+)(?:</span>)?(?:<br><b>Date\s)?)?(?:publication</b>:\s(?:<span class="highlight">)?(?P<PDatum>[^<]+)(?:</span>)?)?\s*<br>)?\s*(?:<b>N°\sdécision</b>:\s+(?P<Num>[^<]+)<br>\s*)?(?P<Rest>(?:.|\s)+)$')
	#reMeta=re.compile(r'<b>Cour</b>:\s<acronym title=\"(?P<VKammer>[^\"]+)\">(?P<Kurz>[^<]+)</acronym><br>(?:<b>Date\s(?:décision</b>:\s(?P<EDatum>[^<]+)<br>(?:<b>Date\s)?)?(?:publication</b>:\s(?P<PDatum>[^<]+)<br>(?:<b>N°\sdécision</b>:\s+(?P<Num>[^<]+)<br>)?(?P<Rest>.+)$')
	reURL=re.compile(r'/justice/findinfo-pub/internet/search/result.jsp\?path=(?P<URL>[^&]+)')
	HEADERS={ 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', "Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "Cache-Control": "no-cache", "Pragma": "no-cache"}

	TREFFER_PRO_SEITE = 50
	FORMDATA = {"page":0,"pageSize":str(TREFFER_PRO_SEITE),"sortBy":"DATE_DE_DECISION","queryTarget":"ALL","modelesDecision":[],"resultatsDecision":None,"naturesAffaire":None,"compositionsCour":None,"autoritesDirectrice":None,"juges":None,"greffiers":[],"resultatsRecours":None,"jurivoc":{"inclusions":[],"exclusions":[]},"articlesDeLoi":{"inclusions":[],"exclusions":[]},"datePublication":{},"dateDecision":{},"query":"*","autoritePremiereInstance":None,"numAffaire":None,"numDecision":None}
	def request_generator(self, ab=None):
		aktjahr = datetime.date.today().year
		if ab:
			abjahr=int(ab.split("-")[0])
		else:
			abjahr=self.STARTJAHR
		
		requests=[]
		for jahr in range(abjahr,aktjahr+1):
			form=copy.deepcopy(self.FORMDATA)
			if jahr==abjahr and ab:
				form['datePublication']["from"]=ab.split('-') # ab muss Format YYYY-MM-DD haben
			else:
				form['datePublication']["from"]=[str(jahr),"1","1"] # ab muss Format YYYY-MM-DD haben
			form['datePublication']["to"]=[str(jahr),"12","31"]
			logger.info(f"Habe Request für {jahr} generiert: {json.dumps(form)}")
			
			# request=scrapy.Request(url=self.getProxyUrl(self.HOST+self.COOKIE_URL),method="GET", meta={'form':form, 'cookiejar': aktjahr-abjahr}, callback=self.parse_cookie, errback=self.errback_httpbin, headers=self.HEADERS)
			request=scrapy.Request(url=self.HOST+self.COOKIE_URL,method="GET", meta={'form':form, 'cookiejar': jahr-abjahr}, callback=self.parse_cookie, errback=self.errback_httpbin, headers=self.HEADERS, dont_filter=True)
			requests.append(request)
			
		return requests
		
	def parse_cookie(self, response):
		antwort=response.text
		logger.info("parse_cookie Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info(f"parse_cookie Headers: {response.headers.getlist('Set-Cookie')}")
		logger.info("parse_cookie Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"Cookie Jar ID: {jar_id}")
		jar = self.cookies_mw.jars[jar_id]
		cookies = { c.name: { "value": c.value, "domain": c.domain, "path": c.path, "expires": c.expires, "secure": c.secure, "rest": dict(getattr(c, "_rest", {}) or {})} for c in jar}
		logger.info(f"Cookie Jar Content: {json.dumps(cookies)}")
		headers=copy.deepcopy(self.HEADERS)
		headers['X-XSRF-TOKEN']=cookies['XSRF-TOKEN']['value']
		headers['Referer']="https://prestations.vd.ch/pub/101623/?page=0&pageSize=50&queryTarget=ALL&sortBy=DATE_DE_DECISION"
		headers['Origin']=self.HOST
		logger.info(f"Sende headers: {json.dumps(headers)} mit body {json.dumps(response.meta['form'])}")
		# request=scrapy.Request(url=self.getProxyUrl(self.HOST+self.SUCH_URL), body=json.dumps(response.meta['form']), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 0, 'cookiejar': response.meta['cookiejar'], 'body': json.dumps(response.meta['form'])}, headers=headers)
		request=scrapy.Request(url=self.HOST+self.SUCH_URL, body=json.dumps(response.meta['form']), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': 0, 'cookiejar': response.meta['cookiejar'], 'body': response.meta['form']}, headers=headers)
		yield(request)


	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab=ab
		self.neu=neu



	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.text[:20000])

		resultdict=json.loads(response.text)
		treffer=resultdict['response']['totalElements']
		entscheide=resultdict['response']['content']
		trefferZahl=len(entscheide)
		seite=response.meta['page']
		body=copy.deepcopy(response.meta['body'])
		logger.info(f"Insgesamt {treffer} Treffer, Seite {seite}, Treffer auf der Seite {trefferZahl}")
		if treffer==10000:
			logger.error(f"Treffermenge zu groos {treffer}")
		if treffer==0:
			logger.warning("kein Treffer")
		
		logger.info("Entscheide in Trefferlistenseite: "+str(len(entscheide)))
		
		for entscheid in entscheide:
			item={}
			logger.info("Verarbeite Entscheid: "+json.dumps(entscheid))
			item['DocID']=PH.NC(entscheid['decisionHit']['id'],error=f"keine DocID in {json.dumps(entscheid)}")
			item['Num']=PH.NC(entscheid['decisionHit']['affaireHit']['numero'],error=f"keine Geschäftsnummer in {json.dumps(entscheid)}")
			if entscheid['decisionHit']['resume']:
				item['Leitsatz']=PH.NC(entscheid['décisionHit']['resume'],warning=f"Fehler beim Abstract in {json.dumps(entscheid)}")
			item['EDATUM']=PH.NC(entscheid['decisionHit']['dateDecision'],warning=f"kein Entscheiddatum in {json.dumps(entscheid)}")
			item['PDATUM']=PH.NC(entscheid['decisionHit']['datePublication'],warning=f"kein Publikationsdatum in {json.dumps(entscheid)}")
			item['Titel']=PH.NC(entscheid['decisionHit']['natureAffaire'],warning=f"kein Titel in {json.dumps(entscheid)}")
			item['PDFUrls']=[self.HOST+self.PDF_URL+item['DocID']]
			kurz=PH.NC(entscheid['decisionHit']['affaireHit']['autoriteDirectrice'],warning=f"keine Kammer erkannt in {json.dumps(entscheid)}")
			item['Signatur'], item['Gericht'], item['Kammer']=self.detect("","#"+kurz+"#",item['Num'])
			yield(item)
		seite=response.meta['page']
		if (seite+1)*self.TREFFER_PRO_SEITE<treffer:
			headers=response.request.headers
			jar_id=response.meta['cookiejar']
			jar = self.cookies_mw.jars[jar_id]
			cookies = { c.name: { "value": c.value, "domain": c.domain, "path": c.path, "expires": c.expires, "secure": c.secure, "rest": dict(getattr(c, "_rest", {}) or {})} for c in jar}
			logger.info(f"parse_trefferliste Cookie Jar Content: {json.dumps(cookies)}")
			if not headers['X-XSRF-TOKEN'].decode("utf-8") == cookies['XSRF-TOKEN']['value']:
				logger.info(f"XSRF-Token hat gewechselt von {headers['X-XSRF-TOKEN']} auf {cookies['XSRF-TOKEN']['value']}")
				headers=copy.deepcopy(headers)
				headers['X-XSRF-TOKEN']=cookies['XSRF-TOKEN']['value']
			body['page']=seite+1
			logger.info(f"Lade nun Seite {seite+1} von {treffer} für {trefferZahl} Treffer bei {self.TREFFER_PRO_SEITE} Treffer pro Seite.")
			# request=scrapy.Request(url=self.getProxyUrl(self.HOST+self.SUCH_URL), body=body, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1, 'cookiejar': response.meta['cookiejar'], 'body': body}, headers=response.request.headers)
			request=scrapy.Request(url=self.HOST+self.SUCH_URL, body=json.dumps(body), method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite+1, 'cookiejar': jar_id, 'body': body}, headers=headers)
			yield request
		
