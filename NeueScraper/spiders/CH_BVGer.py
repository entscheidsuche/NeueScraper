# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from NeueScraper.spiders.basis import BasisSpider

logger = logging.getLogger(__name__)

#Hier wird jessionid benötigt
#COOKIES_ENABLED=True

class CH_BVGer(BasisSpider):
	name = 'CH_BVGer'
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000

	START_URL='https://www.bvger.ch/bvger/de/home/rechtsprechung/entscheiddatenbank-bvger.html'
	SUCH_URL='https://jurispub.admin.ch/publiws/block/send-receive-updates;jsessionid='
	JSESSION_URL='https://jurispub.admin.ch/publiws/skins/css/bvger-web.css'
	#ice.submit.partial=true&ice.event.target=form%3AsearchSubmitButton&ice.event.captured=form%3AsearchSubmitButton&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=80&ice.event.y=251&ice.event.left=false&ice.event.right=false&form%3A_idform%3AcalTosp=&form%3A_idform%3AcalFromsp=&form%3A_idcl=&form%3Aform%3Atree_idtn=&form%3Aform%3Atree_idta=&form%3AcalTo=&form%3AcalFrom=&form%3AsearchQuery=&javax.faces.RenderKitId=ICEfacesRenderKit&javax.faces.ViewState=1&icefacesCssUpdates=&form=form&form%3AsearchSubmitButton=suchen&ice.session=iDUJZrABHum-W5vwI3oEVQ&ice.view=1&ice.focus=form%3AsearchSubmitButton&rand=0.4180500971223393
	
	HEADERS = {	'Host': 'jurispub.admin.ch',
				'Connection': 'keep-alive',
				'Content-Length': '486',
				'Pragma': 'no-cache',
				'Cache-Control': 'no-cache',
				'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36 OPR/71.0.3770.284',
				'DNT': '1',
				'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
				'Accept': '*/*',
				'Origin': 'https://jurispub.admin.ch',
				'Sec-Fetch-Site': 'same-origin',
				'Sec-Fetch-Mode': 'cors',
				'Sec-Fetch-Dest': 'empty',
				'Referer': 'https://jurispub.admin.ch/publiws/?lang=de',
				'Accept-Encoding': 'gzip, deflate, br',
				'Accept-Language': 'de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7' }	
	
	
	reJsession=re.compile('(?<=JSESSIONID=)[0-9A-F]+(?=;)')

	#RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum}&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	RESULT_PAGE_URL='https://www.gerichte-zh.ch/typo3conf/ext/frp_entscheidsammlung_extended/res/php/livesearch.php?q=&geschaeftsnummer=&gericht=gerichtTitel&kammer=kammerTitel&entscheiddatum_von={datum}&entscheiddatum_bis=31.12.2100&erweitert=1&usergroup=0&sysOrdnerPid=0&sucheErlass=Erlass&sucheArt=Art.&sucheAbs=Abs.&sucheZiff=Ziff./lit.&sucheErlass2=Erlass&sucheArt2=Art.&sucheAbs2=Abs.&sucheZiff2=Ziff./lit.&sucheErlass3=Erlass&sucheArt3=Art.&sucheAbs3=Abs.&sucheZiff3=Ziff./lit.&suchfilter=1'
	PDF_BASE='https://www.gerichte-zh.ch'
	AB_DEFAULT='01.01.1900'
	JsessionId=''

	def request_generator(self):
		""" Generates scrapy frist request
		"""
		return [scrapy.Request(url=self.JSESSION_URL, callback=self.parse_suchform, errback=self.errback_httpbin)]

	def __init__(self,ab=AB_DEFAULT):
		super().__init__()
		self.ab = ab
		self.request_gen = self.request_generator()

	def parse_suchform(self,response):
		logger.info("Rohergebnis: "+str(len(response.body))+" Zeichen")
		logger.info("Body: "+response.body_as_unicode())
		for entry in response.headers:
			for subentry in response.headers.getlist(entry):
				logger.debug("Header '"+entry.decode('ascii')+"': "+subentry.decode('ascii'))
				if entry.decode('ascii') == 'Set-Cookie':
					ergebnis=self.reJsession.search(subentry.decode('ascii'))
					if ergebnis:
						self.JsessionId=ergebnis.group(0)
						logger.info("JsessionId: "+ self.JsessionId)
						
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			req=scrapy.Request(url=self.SUCH_URL+self.JsessionId, method='POST', headers=self.HEADERS, body='ice.submit.partial=true&ice.event.target=form%3AsearchSubmitButton&ice.event.captured=form%3AsearchSubmitButton&ice.event.type=onclick&ice.event.alt=false&ice.event.ctrl=false&ice.event.shift=false&ice.event.meta=false&ice.event.x=80&ice.event.y=251&ice.event.left=false&ice.event.right=false&form%3A_idform%3AcalTosp=&form%3A_idform%3AcalFromsp=&form%3A_idcl=&form%3Aform%3Atree_idtn=&form%3Aform%3Atree_idta=&form%3AcalTo=&form%3AcalFrom=&form%3AsearchQuery=&javax.faces.RenderKitId=ICEfacesRenderKit&javax.faces.ViewState=1&icefacesCssUpdates=&form=form&form%3AsearchSubmitButton=suchen&ice.session=iDUJZrABHum-W5vwI3oEVQ&ice.view=1&ice.focus=form%3AsearchSubmitButton&rand=0.4184723907223393', callback=self.trefferliste, errback=self.errback_httpbin)
			yield(req)
					

	def trefferliste(self,response):
		logger.info("Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("Body: "+response.body_as_unicode())
		for entry in response.headers:
			for subentry in response.headers.getlist(entry):
				logger.info("Header "+entry.decode('ascii')+": "+subentry.decode('ascii'))




	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logging.error(repr(failure))
