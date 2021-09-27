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


class AG_Weitere(BasisSpider):
	name = 'AG_Weitere'

	HOST='https://www.ag.ch'
	URLS=['/de/gerichte/gesetze_entscheide/weitere_entscheide_1/weitere_entscheide_2.jsp', '/de/dvi/grundbuch_vermessung/grundbuch/rechtliche_grundlagen_1/entscheide_2/entscheide.jsp']
	
	reMeta=re.compile(r"(?P<Typ>[^ ]+) de(?:s|r)\s+(?P<Gericht>.+)\s+vom\s+(?P<Datum>\d+\.\s+(?:"+"|".join(BasisSpider.MONATEde)+")\s+\d\d\d\d)")
	reMetaTable=re.compile(r"(?P<Titel>^[^\(]+)\s+\((?P<K1>[^\(]+)\)\s+\((?P<K2>[^\(]+)\)")
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = self.generate_request()

	def generate_request(self):
		return [scrapy.Request(url=self.HOST+u, callback=self.parse_page, errback=self.errback_httpbin, meta={'pfad':""}) for u in self.URLS]

	# Unklar ob es sich um eine Menüseite oder eine Trefferliste handelt
	def parse_page(self, response):
		logger.info("parse_page response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.body_as_unicode()
		logger.info("parse_page Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_page Rohergebnis: "+antwort[:40000])
		
		pfad=response.meta['pfad']
		subpages=response.xpath("//article[@class='teaser']")
		# Eine Menüseite
		if subpages:
			for s in subpages:
				text=s.get()
				url=PH.NC(s.xpath(".//a[@class='teaser__link']/@href").get(),error="Link für Submenü nicht gefunden in "+text)
				titel=PH.NC(s.xpath(".//span[@class='teaser__title']/text()").get(),error="Titel für Submenü nicht gefunden in "+text)
				request=scrapy.Request(url=url, callback=self.parse_page, errback=self.errback_httpbin, meta={'pfad':pfad+"/"+titel})
				yield request
		# Eine Listenseite
		else:
			struktur=response.xpath("//div[@class='accordion js-accordion js-accordion--multi']/div[@class='accordion__content']")
			if struktur:
				struktur_da=True
			else:
				struktur=response.xpath("//section[@class='contentcol__section' and p]")
				struktur_da=False
				titel="keine Struktur"
			if struktur:
				for i in struktur:
					text=i.get()
					if struktur_da:
						titel=PH.NC(i.xpath(".//h2[@id='firstsection']/text()").get(),error="Bereichstitel nicht gefunden in: "+text)
					entscheide=i.xpath("./p[a]")
					if not entscheide:
						logger.warning("Keine Entscheide im Bereich: "+titel)
					for e in entscheide:
						itext=e.get()
						item={}
						item['PDFUrls']=[self.HOST+PH.NC(e.xpath("./a[@class='mime-pdf']/@href").get(),error="Url für PDF des Entscheids nicht gefunden in "+itext)]
						meta=PH.NC(e.xpath("./a[@class='mime-pdf']/span[@class='link__text']/text()").get(),error="Linktext des Entscheids nicht gefunden in "+itext)
						item['Leitsatz']=PH.NC(e.xpath("./text()").get(),warning="Leitsatz des Entscheids nicht gefunden in "+itext)
						if struktur_da:
							item['Rechtsgebiet']=pfad+"/"+titel
						else:
							item['Rechtsgebiet']=pfad					
						metas=self.reMeta.search(meta)
						if metas:
							item['Entscheidart']=metas.group('Typ')
							item['VGericht']=metas.group('Gericht').replace('\ufeff','')
							item['EDatum']=self.norm_datum(metas.group('Datum'))
							item['Num']=""
							rechtskraft=e.xpath("following-sibling::p[position()=1][not(a)]/text()")
							if rechtskraft:
								item['Rechtskraft'] = rechtskraft[1:-1] if rechtskraft[0]=='(' and rechtskraft[-1]==')' else rechtskraft							
							item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
							yield item
						else:
							logger.error("Metadaten nicht erkannt für "+meta+" in "+itext)
			else: # Tabellenstruktur
				vgericht=pfad=PH.NC(response.xpath("//table[@class='table js-table-sortable table--scrollable js-table-filterable table--filterable']/@summary").get(),error="tablesummary konnte nicht gelesen werden")
				entscheide=response.xpath("//table[@class='table js-table-sortable table--scrollable js-table-filterable table--filterable']//tbody/tr")
				if not entscheide:
					logger.warning("Keine Entscheide im Bereich: "+titel)
				else:
					for e in entscheide:
						itext=e.get()
						item={}
						item['PDFUrls']=[self.HOST+PH.NC(e.xpath("./td/a[@class='mime-pdf']/@href").get(),error="Url für PDF des Entscheids nicht gefunden in "+itext)]
						meta=PH.NC(e.xpath("./td/a[@class='mime-pdf']/span[@class='link__text']/text()").get(),error="Linktext des Entscheids nicht gefunden in "+itext)
						metas=self.reMetaTable.search(meta)
						if metas:
							item['Leitsatz']=metas.group('Titel')
							num=metas.group('K1')
							if 'AGVE' in num:
								item['Num']=num
							else:
								item['Num']=""
								item['Titel']=num
							item['Rechtsgebiet']=pfad
							item['VGericht']=vgericht
							item['EDatum']=self.norm_datum(PH.NC(e.xpath("./td[@data-table-columntitle='Datum']/text()").get(),error="kein Datum in "+itext))
							item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],"",item['Num'])
							yield item
						else:
							logger.error("Metadaten nicht erkannt für "+meta+" in "+itext)	
