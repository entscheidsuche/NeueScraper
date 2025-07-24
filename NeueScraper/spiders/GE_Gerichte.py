# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class GenfSpider(BasisSpider):
	name = 'GE_Gerichte'

	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	TREFFER_PRO_SEITE = 500
	SUCH_URL='/apps/decis/fr/{gericht}/search?search_meta=dt_decision%3A[{datum}+TO+{bis}]&decision_from={datum}&decision_to={bis}&sort_by=date&page_size={treffer_pro_seite}&page={seite}'
	HOST ="http://justice.ge.ch"
	suchseiten={ 'capj': "GE_CAPJ_001",
				'acjc': "GE_CJ_001",
				'sommaires': "GE_CJ_002",
				'caph': "GE_CJ_003",
				'cabl': "GE_CJ_004",
				'aj': "GE_CJ_005",
				'das': "GE_CJ_006",
				'dcso': "GE_CJ_007",
				'comtax': "GE_CJ_008",
				'parp': "GE_CJ_009",
				'cjp': "GE_CJ_010",
				'pcpr': "GE_CJ_011",
				'oca': "GE_CJ_012",
				'ata': "GE_CJ_013",
				'atas': "GE_CJ_014",
				'cst': "GE_CJ_015",
				'jtp': "GE_TP_001",
				'dccr': "GE_TAPI_001"}
				
	#reTreffer=re.compile(r'<span class=\"float_right txt_gras\">\s*(?P<num>[^<\s]+)\s+</span>\s+<b>\s+<a href=\"(?P<url>[^\"]+)(?:[^\s]|\s){10,80}du (?P<tag>\d\d?)\.(?P<monat>\d\d?)\.(?P<jahr>(?:19|20)\d\d)\s+,\s+(?P<ergebnis>[^ ]+)(?:[^\s]|\s){30,300}<div>\s+<b>Descripteurs</b> :\s+(?P<betreff>[^<]+[^\s<])\s+</div>\s+<div>\s+<b>Normes</b> :\s+(?P<normen>[^<]+[^\s<])\s+</div>\s+<div>\s+<b>Résumé</b> :\s+(?P<abstract>[^<]+[^<\s])')
	#reTreffer=re.compile(r'<span class=\"float_right txt_gras\">\s*(?P<num>[^<\s]+)\s+</span>\s+<b>\s+<a href=\"(?P<url>[^\"]+)(?:[^\s]|\s){10,80}du (?P<tag>\d\d?)\.(?P<monat>\d\d?)\.(?P<jahr>(?:19|20)\d\d)\s+(?:sur\s(?P<vorinstanz>[^ ]+)\s+)?(?:\([^\)]+\)\s+)?,\s+(?P<ergebnis>[^ ]+)\s+-- score: <em>[^<]+</em>\s+</div>\s+<div class=\"data\">\s+<div>\s+<b>(?:Descripteurs</b> :\s+(?P<betreff>[^<]+[^\s<])\s+</div>(?:\s+<div>\s+<b>)?)?(?:Normes</b> :\s+(?P<normen>[^<]+[^\s<])\s+</div>(?:\s+<div>\s+<b>)?)?(?:Résumé</b> :\s+(?P<abstract>[^<]+[^<\s]))?')
	#reTrefferzahl=re.compile(r'Votre requête : <strong>(?P<trefferzahl>\d+)</strong> enregistrement')
	reAngaben=re.compile(r'du (?P<tag>\d\d?)\.(?P<monat>\d\d?)\.(?P<jahr>(?:19|20)\d\d)\s+(?:sur\s(?P<vorinstanz>[^ ]+)\s+)?(?:\([^\)]+\)\s+)?(?:,\s+(?P<ergebnis>[^ ]+))?')
	
	def mache_request(self,gericht,start_datum,trefferseite=1):
		jahr=start_datum[-4:]
		end_datum='31.12.'+jahr
		request=scrapy.Request(url=self.HOST+self.SUCH_URL.format(datum=start_datum, bis=end_datum, gericht=gericht, seite=trefferseite, treffer_pro_seite=self.TREFFER_PRO_SEITE), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'subsite': gericht, 'page': trefferseite, 'start_datum': start_datum})
		return request
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen

		request_liste=[]
		start_datum=self.ab if self.ab else '01.01.1995'
		jahr=int(start_datum[-4:],10)
		akt_jahr=datetime.date.today().year
		while jahr <= akt_jahr:
			for g in self.suchseiten:
				request_liste.append(self.mache_request(g, start_datum))
			jahr+=1
			start_datum='01.01.'+str(jahr)
		return request_liste

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		if ab:
			self.ab=ab
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen für: "+response.request.url)
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		
		entscheide=response.xpath("//div[@class='list-block col-lg-12 mb-5']")
		subsite=response.meta['subsite']
		start_datum=response.meta['start_datum']
		trefferzahl=response.xpath("//div[@class='mb-3 mt-3']/strong[contains(following-sibling::text(),'resultats')]/text()").get()
		if trefferzahl:
			logger.info(subsite+": "+trefferzahl+" Treffer angegeben, auf der 1. Seite "+str(len(entscheide))+" identifiziert.")
			for entscheid in entscheide:
				item={}
				text=entscheid.get()
				item['Num']=PH.NC(entscheid.xpath(".//div[@class='decis-block__flag']/text()").get(),error="Keine Geschäftsnummer in "+text+" gefunden.")
				if item['Num']:
					item['HTMLUrls']=[self.HOST+PH.NC(entscheid.xpath("./div[@class='list-block__content row pb-3']/h3[@class='list-block__title col-lg-10' or @class='list-block__title col-lg-8']/a/@href").get(),error="keine URL in "+text+" gefunden.")]
					angaben=entscheid.xpath("./div[@class='list-block__content row pb-3']/h3[@class='list-block__title col-lg-10' or @class='list-block__title col-lg-8']/text()[contains(.,' du ')]").getall()
					if len(angaben)==1:
						angabenstring=angaben[0].replace("\n","")
						logger.info("Angabenstring: "+angabenstring)
						a=self.reAngaben.search(angabenstring)
						if a:
							item['EDatum']=a['jahr']+"-"+a['monat']+"-"+a['tag']
							item['Vorinstanz']=a['vorinstanz'] if a['vorinstanz'] else ""
							n=entscheid.xpath("substring-after(.//div[@class='col-lg-12']/div/b[.='Normes']/following-sibling::text(),':')").get()
							if n:
								item['Normen']=n.replace("\n","").strip()
							n=entscheid.xpath("substring-after(.//div[@class='col-lg-12']/div/b[.='Descripteurs']/following-sibling::text(),':')").get()
							if n:
								item['Titel']=n.replace("\n","").strip()
							n=entscheid.xpath("substring-after(.//div[@class='col-lg-12']/div/b[.='Résumé']/following-sibling::text(),':')").get()
							if n:
								item['Leitsatz']=n.replace("\n","").strip()
							subsite=response.meta['subsite']
							item['Signatur']=self.suchseiten[subsite]
							item['Gericht'], item['Kammer']=self.detect_by_signatur(item['Signatur'])
							logger.info("Item gelesen: "+json.dumps(item))
							request=scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'subsite': subsite, 'item': item})
							if self.check_blockliste(item):
								yield(request)
						else:
							logger.error("Für "+item['Num']+" Angabenstring "+angabenstring+" gefunden, regex aber nicht gefunden")
					else:
						logger.error("Für "+item['Num']+" falsche Anzahl Angaben gefunfen: "+str(len(angaben))+", "+text)
			akt_seite=response.meta['page']
			if akt_seite*self.TREFFER_PRO_SEITE<int(trefferzahl,10):
				request=self.mache_request(subsite,start_datum,akt_seite+1)
				yield(request)
		else:
			if response.xpath("//div[@class='module-title']/h2[contains(.,'Aucun résultat ne correspond aux termes de recherche spécifiés')]"):
				if self.ab:
					logger.info("keine Treffer für "+subsite+" ab "+self.ab+" Zeitraum: "+start_datum+" bis Ende Jahr")
				else:
					logger.info("keine Treffer bei Gesamtrecherche für "+subsite+" Zeitraum: "+start_datum+" bis Ende Jahr")
			else:
				logger.error("Weder Meldung keine Treffer noch Trefferzahl erkannt bei "+subsite+" ("+response.request.url+"): "+antwort[:50000])
						
	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:10000])
		
		item=response.meta['item']			
		html=response.xpath("//div[@class='list-block col-lg-12 mb-5']")

		pdf=html.xpath("//div[@class='col-lg-12 mt-4']/div[@style='float:right']/a[img]/@href")
		if pdf:
			item['PDFUrls']=[self.HOST+pdf.get()]
		else:
			logger.warning("kein PDF für "+item['Num'])

		PH.write_html(html.get(), item, self)
		yield(item)
		

			


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
