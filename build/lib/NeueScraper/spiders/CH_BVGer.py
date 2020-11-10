# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
import random
from NeueScraper.spiders.basis import BasisSpider
import datetime

logger = logging.getLogger(__name__)

#Hier wird jessionid benötigt
#COOKIES_ENABLED=True

class CH_BVGer(BasisSpider):
	name = 'CH_BVGer'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	START_JAHR = 2007

	START_URL='https://www.bvger.ch/bvger/de/home/rechtsprechung/entscheiddatenbank-bvger.html'
	SUCH_URL='https://jurispub.admin.ch/publiws/block/send-receive-updates;jsessionid='
	JSESSION_URL='https://jurispub.admin.ch/publiws/?lang=de'
	DOKUMENT_URL='https://jurispub.admin.ch/publiws/pub/cache.jsf;jsessionid='
	#ice.submit.partial=true&ice.event.target=form%3AsearchSubmitButton&ice.event.captured=form%3AsearchSubmitButton&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=80&ice.event.y=251&ice.event.left=false&ice.event.right=false&form%3A_idform%3AcalTosp=&form%3A_idform%3AcalFromsp=&form%3A_idcl=&form%3Aform%3Atree_idtn=&form%3Aform%3Atree_idta=&form%3AcalTo=&form%3AcalFrom=&form%3AsearchQuery=&javax.faces.RenderKitId=ICEfacesRenderKit&javax.faces.ViewState=1&icefacesCssUpdates=&form=form&form%3AsearchSubmitButton=suchen&ice.session=iDUJZrABHum-W5vwI3oEVQ&ice.view=1&ice.focus=form%3AsearchSubmitButton&rand=0.4180500971223393
	
	HEADERS = {	b'Connection': b'keep-alive',
				b'Pragma': b'no-cache',
				b'Cache-Control': b'no-cache',
				b'User-Agent': b'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36 OPR/71.0.3770.284',
				b'DNT': b'1',
				b'Content-Type': b'application/x-www-form-urlencoded; charset=UTF-8',
				b'Accept': b'*/*',
				b'Origin': b'https://jurispub.admin.ch',
				b'Sec-Fetch-Site': b'same-origin',
				b'Sec-Fetch-Mode': b'cors',
				b'Sec-Fetch-Dest': b'empty',
				b'Referer': b'https://jurispub.admin.ch/publiws/publiws/?lang=de',
				b'Accept-Language': b'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7' }
				
	
	reTreffer=re.compile('return iceSubmitPartial\(form,this,event\);" onfocus="setFocus\(this.id\);">(?P<Raw>(?P<Num>[^<]+)</a>[^C]+C[^<]+<a class="iceOutLnk" href="(?P<PDFUrl>[^"]+jsessionid=[0-9A-F]+\?decisionId=(?P<DocId>[0-9a-f-]+))" id="form:resultTable:(?P<Pos>[^"]+):[^C]+Col1">[^>]+>(?P<EDatum>[^<]+)[^O]+[^>]+>(?P<VKammer>[^<]+)<[^O]+O[^>]+>(?P<Titel>[^<]+)[^G]+G[^O]+O[^>]+>(?P<LeitsatzKurz>[^<]*)<[^O]+O[^>]+>(?P<Leitsatz>[^<]*))')
	reCookie=re.compile('^([^=]+)=([^;]+)')
	reJsession=re.compile('(?<=JSESSIONID=)[0-9A-F]+(?=;)')
	reICEsession=re.compile('(?<=script id=")[^:]+(?=:1:configuration-script)')
	reTrefferzahl=re.compile('<span class="iceOutFrmt standard">([0-9]+(?:,[0-9]+)?) Entscheide gefunden, zeige ([0-9]+(?:,[0-9]+)?) bis ([0-9]+(?:,[0-9]+)?)\. Seite ([0-9]+(?:,[0-9]+)?) von ([0-9]+(?:,[0-9]+)?)\. Resultat sortiert')
	reNext=re.compile('j_id[0-9]+next')
	PDF_BASE='https://jurispub.admin.ch'
	AB_DEFAULT=''

	def request_generator(self, ab):
		""" Generates scrapy frist request
		"""
		requests=[]
		if ab:
			requests.append(scrapy.Request(url=self.JSESSION_URL, callback=self.parse_suchform, errback=self.errback_httpbin, meta={'ab':ab, 'bis':''}))
		else:
			jahr=datetime.date.today().year
			jahre=range(self.START_JAHR,jahr)
			for j in jahre:
				if j == self.START_JAHR:
					ab=""
				else:
					ab="01.01."+str(j)
				if j == jahr:
					bis=""
				else:
					bis="31.12."+str(j)
				req=scrapy.Request(url=self.JSESSION_URL+"&"+str(j), callback=self.parse_suchform, errback=self.errback_httpbin, meta={'ab':ab, 'bis':bis})
				req.meta['dont_cache']=True	
				requests.append(req)
		return requests
		
	def __init__(self,ab=AB_DEFAULT):
		super().__init__()
		self.ab = ab
		self.request_gen = self.request_generator(ab)

	def parse_suchform(self,response):
		ab=response.meta['ab']
		bis=response.meta['bis']
		logger.info("Suchanfrage_von_bis "+ab+"-"+bis+" Rohergebnis: "+str(len(response.body))+" Zeichen")
		logger.info("Body: "+response.body_as_unicode())
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			ergebnis=self.reICEsession.search(response.body_as_unicode())
			iceSession=''
			jSession=''
			if ergebnis:
				iceSession=ergebnis.group(0)
				logger.info('ICEsession: '+iceSession)
			else:
				logger.info('ICEsession nicht gefunden.')

			for entry in response.headers:
				for subentry in response.headers.getlist(entry):
					logger.debug("Header '"+entry.decode('ascii')+"': "+subentry.decode('ascii'))
					if entry.decode('ascii') == 'Set-Cookie':
						ergebnis=self.reCookie.search(subentry.decode('ascii'))
						if ergebnis:
							logger.debug("Cookie: '"+ergebnis.group(1)+"'='"+ergebnis.group(2)+"'")
							# cookie[ergebnis.group(1).encode('ascii')]=ergebnis.group(2).encode('ascii')
						ergebnis=self.reJsession.search(subentry.decode('ascii'))
						if ergebnis:
							jSession=ergebnis.group(0)
							logger.info("JsessionId: "+ jSession)
						
			if iceSession and jSession:  
				req_body='ice.submit.partial=true&ice.event.target=form%3AcalFrom&ice.event.captured=form%3AcalFrom&ice.event.type=onblur&form%3A_idform%3AcalTosp=&form%3A_idform%3AcalFromsp=&form%3A_idcl=&form%3Aform%3Atree_idtn=&form%3Aform%3Atree_idta=&form%3AcalTo='+bis+'&form%3AcalFrom='+ab+'&form%3AsearchQuery=&javax.faces.RenderKitId=&javax.faces.ViewState=1&icefacesCssUpdates=&form=&ice.session='+iceSession+'&ice.view=1&ice.focus=&rand=0.'+str(random.randint(1000000000000000,9999999999999999))
				req=scrapy.Request(url=self.SUCH_URL+jSession, method='POST', headers=self.HEADERS, body=req_body, callback=self.intermediate_trefferliste, errback=self.errback_httpbin, meta={'ab':ab, 'bis':bis, 'jSession':jSession, 'iceSession':iceSession})
			yield(req)
					
	def intermediate_trefferliste(self,response):
		logger.debug("Intermediate Trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		antwort=response.body_as_unicode()
		logger.debug("Body: "+antwort)
		jSession=response.meta['jSession']
		iceSession=response.meta['iceSession']
		ab=response.meta['ab']
		bis=response.meta['bis']
		
		req_body='ice.submit.partial=true&ice.event.target=form%3AsearchSubmitButton&ice.event.captured=form%3AsearchSubmitButton&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=72&ice.event.y=252&ice.event.left=false&ice.event.right=false&form%3A_idform%3AcalTosp=&form%3A_idform%3AcalFromsp=&form%3A_idcl=&form%3Aform%3Atree_idtn=&form%3Aform%3Atree_idta=&form%3AcalTo='+bis+'&form%3AcalFrom='+ab+'&form%3AsearchQuery=&javax.faces.RenderKitId=&javax.faces.ViewState=1&icefacesCssUpdates=&form=&form%3AsearchSubmitButton=suchen&ice.session='+iceSession+'&ice.view=1&ice.focus=form%3AsearchSubmitButton&rand=0.'+str(random.randint(1000000000000000,9999999999999999))
		req=scrapy.Request(url=self.SUCH_URL+jSession, method='POST', headers=self.HEADERS, body=req_body, callback=self.trefferliste, errback=self.errback_httpbin, meta=response.meta)
		yield(req)


	def trefferliste(self,response):
		logger.debug("Trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		antwort=response.body_as_unicode()
		logger.debug("Body: "+antwort)
		#Antwort HTML kommt als CDATA daher kein XPATH hier
		
		trefferzahl=self.reTrefferzahl.search(antwort)
		if trefferzahl:
			logger.info(trefferzahl[1]+" Treffer, Treffer "+trefferzahl[2]+"-"+trefferzahl[3]+", Seite "+trefferzahl[4]+" von "+trefferzahl[5])
			seite=int(trefferzahl[4].replace(',',''))
			seiten=int(trefferzahl[5].replace(',',''))
		else:
			logger.error("Konnte keine Trefferzahl erkennen: "+antwort)

		treffer=[m.groupdict() for m in self.reTreffer.finditer(antwort)]
		if treffer:
			logger.debug(str(len(treffer))+" Treffer auf der Trefferliste")
			for item in treffer:
				logger.debug("Erkannte Bestandteile: "+json.dumps(item))
				item['PDFUrls']=[self.PDF_BASE+item['PDFUrl']]
				del item['PDFUrl']
				Pos=item['Pos']
				item['EDatum']=item['EDatum'][6:]+"-"+item['EDatum'][3:5]+"-"+item['EDatum'][:2]
				vkammer=item['VKammer']
				Leitsatz_kurz=item['LeitsatzKurz']
				vgericht=""
				Num=item['Num']
				signatur, gericht, kammer=self.detect(vgericht,vkammer,Num)
				item['Gericht']=gericht
				item['Kammer']=kammer	
				item['Kanton']=self.kanton_kurz
				item['Signatur']=signatur
				vgericht=gericht
				if vkammer=='':
					item['VKammer']=kammer
				if vgericht=='':
					item['VGericht']=gericht
					
				# body='ice.submit.partial=true&ice.event.target=form%3AresultTable%3A#%3Aj_id36&ice.event.captured=form%3AresultTable%3A#%3Aj_id36&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=86&ice.event.y=195&ice.event.left=false&ice.event.right=false&form%3A_idcl=form%3AresultTable%3A#%3Aj_id36&form%3Aj_id63=&javax.faces.RenderKitId=ICEfacesRenderKit&javax.faces.ViewState=1&icefacesCssUpdates=&form=form&ice.session='+iceSession+'&ice.view=1&ice.focus=form%3AresultTable%3A#%3Aj_id36&rand=0.'+str(random.randint(1000000000000000,9999999999999999))
				# body.replace('#',Pos)
				# HTML nicht holen, da das die Session durcheinander bringt
				# req=scrapy.Request(url=htmlUrl, method='POST', headers=self.HEADERS, body=body.encode('ascii'), callback=self.parse_page_intermediate, errback=self.errback_httpbin, meta = {'item':item})
				yield(item)
				
			if(seite<seiten):
				jSession=response.meta['jSession']
				iceSession=response.meta['iceSession']
				
				body='ice.submit.partial=true&ice.event.target=form%3Aj_id67&ice.event.captured=form%3Aj_id63next&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=171&ice.event.y=502&ice.event.left=false&ice.event.right=false&form%3A_idcl=&form%3Aj_id63next&form%3Aj_id63=next&javax.faces.RenderKitId=&javax.faces.ViewState=1&icefacesCssUpdates=&form=form&ice.session='+iceSession+'&ice.view=1&ice.focus=form%3Aj_id63next&rand=0.'+str(random.randint(1000000000000000,9999999999999999))
				logger.debug('body: '+body)
				req=scrapy.Request(url=self.SUCH_URL+jSession, method='POST', headers=self.HEADERS, body=body.encode('ascii'), callback=self.trefferliste, errback=self.errback_httpbin, meta=response.meta)
				yield(req)
			else:
				logger.debug("Fertig!")
				
		else:
			logger.error("kein Treffer gematched")



	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))
