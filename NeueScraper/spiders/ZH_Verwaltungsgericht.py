# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
import json
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import MyFilesPipeline
from NeueScraper.pipelines import PipelineHelper


logger = logging.getLogger(__name__)

class ZurichVerwgerSpider(BasisSpider):
	name = 'ZH_Verwaltungsgericht'

	TREFFERLISTE_URL='https://vgrzh.djiktzh.ch/cgi-bin/nph-omniscgi.exe?OmnisPlatform=WINDOWS&WebServerUrl=https://vgrzh.djiktzh.ch&WebServerScript=/cgi-bin/nph-omniscgi.exe&OmnisLibrary=JURISWEB&OmnisClass=rtFindinfoWebHtmlService&OmnisServer=JURISWEB,127.0.0.1:7000&Parametername=WWW&Schema=ZH_VG_WEB&Source=&Aufruf=search&cTemplate=standard/results/resultpage.fiw&cTemplateSuchkriterien=standard/results/searchcriteriarow.fiw&cSprache=GER&W10_KEY=4004259&nSeite={page}'
	ab=None
	reDatum=re.compile('[0-9]{2}\\.[0-9]{2}\\.[0-9]{4}')
	reTyp=re.compile('.+(?= vom [0-9]{2}\\.[0-9]{2}\\.[0-9]{4})')

	SUCH_URL='/cgi-bin/nph-omniscgi.exe'
	HOST ="https://vgrzh.djiktzh.ch"
	TREFFER_PRO_SEITE = 100
	FORMDATA = {
		"OmnisPlatform": "WINDOWS",
		"WebServerUrl": "https://vgrzh.djiktzh.ch",
		"WebServerScript": "/cgi-bin/nph-omniscgi.exe",
		"OmnisLibrary": "JURISWEB",
		"OmnisClass": "rtFindinfoWebHtmlService",
		"OmnisServer": "JURISWEB,127.0.0.1:7000",
		"Schema": "ZH_VG_WEB",
		"Parametername": "WWW",
		"Aufruf": "search",
		"cTemplate": "standard/results/resultpage.fiw",
		"cTemplateSuchkriterien": "standard/results/searchcriteriarow.fiw",
		"cTemplate_SuchstringValidateError": "standard/results/resultpage.fiw",
		"cSprache": "GER",
		"cGeschaeftsart": "",
		"cGeschaeftsjahr": "",
		"cGeschaeftsnummer": "",
		"dEntscheiddatum": "",
		"bHasEntscheiddatumBis": "0",
		"dEntscheiddatumBis": "",
		"dPublikationsdatum": "",
		"bHasPublikationsdatumBis": "0",
		"dPublikationsdatumBis": "",
		"dErstPublikationsdatum": "",
		"bHasErstPublikationsdatumBis": "0",
		"dErstPublikationsdatumBis": "",
		"cSuchstringZiel": "F37_HTML",
		"cSuchstring": "",
		"nAnzahlTrefferProSeite": str(TREFFER_PRO_SEITE),
		"nSeite": "1" }




	def request_generator(self, seite=1, jahr=None):
		if jahr is None:
			jahr_s=""
		else:
			jahr_s=str(jahr)
		self.FORMDATA['nSeite']=str(seite)
		self.FORMDATA['cGeschaeftsjahr']=jahr_s
		logger.info("Request Formdata: "+json.dumps(self.FORMDATA))
		request=scrapy.FormRequest(url=self.HOST+self.SUCH_URL, formdata=self.FORMDATA, method="POST", callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': seite, 'jahr': jahr})
		return request


	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		if ab is None:
			self.request_gen=[self.request_generator()]
		else:
			ab_int=int(ab)
			bis_int=datetime.date.today().year
			self.request_gen=[self.request_generator(1,jahr) for jahr in range(ab_int, bis_int+1)]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode())
		
		treffer=response.xpath("(//table[@width='98%']//table[@width='100%']/tr/td/b/text())[2]").get()
		if treffer is None:
			keine_treffer=response.xpath("//table[@width='98%']//table[@width='100%']/tr/td/b/text()").get()
			if keine_treffer =="keine Treffer":
				logger.info("Meldung: keine Treffer gefunden")
			else:
				logger.error("Ergebnis konnte nicht erkannt werden")
		else:
			trefferZahl=int(treffer)
		
			entscheide=response.xpath("//table[@width='100%']/tr/td[@valign='top']/table")
			for entscheid in entscheide:
				logger.info("Verarbeite Entscheid: "+entscheid.get())
				url=entscheid.xpath(".//a/@href").get()
				logger.info("url: "+url)
				num=entscheid.xpath(".//a/font/text()").get()
				logger.info("num: "+num)
				vkammer=entscheid.xpath(".//tr[1]/td[4]/font/text()").get()
				if vkammer==None:
					vkammer=""
					logger.info("keine Kammer")
				else:
					logger.info("Kammer: "+vkammer)
				titel=entscheid.xpath(".//tr[2]/td[2]/b/text()").get()
				logger.info("Titel: "+titel)
				regesten=entscheid.xpath(".//tr[2]/td[2]/text()").getall()
				regeste=""
				for s in regesten:
					if not(s.isspace() or s==""):
						if len(regeste)>0:
							regeste=regeste+" "
						regeste=regeste+s
				datum=entscheid.xpath(".//td[@colspan='2']/i/text()").get()
				logger.info("Typ+Datum: "+datum)
				edatum=self.reDatum.search(datum).group(0)
				if self.reTyp.search(datum):
					typ= self.reTyp.search(datum).group(0)
				else:
					typ=""
				id=entscheid.xpath(".//td[a]/text()").get()
				logger.info("ID?: "+id)
				vgericht=''
				signatur, gericht, kammer=self.detect(vgericht,vkammer,num)
		
				item = {
					'Kanton': self.kanton_kurz,
					'Gericht' : gericht,
					'VGericht' : vgericht,
					'EDatum': self.norm_datum(edatum),
					'Titel': titel,
					'Leitsatz': regeste.strip(),
					'Num': num,
					'HTMLUrls': [url],
					'PDFUrls': [],
					'Kammer': kammer,
					'VKammer': vkammer,
					'Entscheidart': typ,
					'Signatur': signatur
				}
				request=scrapy.Request(url=url, callback=self.parse_page, errback=self.errback_httpbin, meta = {'item':item})
				yield(request)

			page=response.meta['page']
			jahr=response.meta['jahr']

			if page*self.TREFFER_PRO_SEITE < trefferZahl:
				logger.info("Hole Seite "+ str(page+1) +" von "+treffer+" Treffern.")
				request=self.request_generator(page+1,jahr)
				yield(request)
		

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.debug("parse_page response.status "+str(response.status))
		logger.info("parse_page Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.debug("parse_page Rohergebnis: "+response.body_as_unicode())
		item=response.meta['item']
		PipelineHelper.write_html(response.body_as_unicode(), item, self)
		yield(item)								


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
