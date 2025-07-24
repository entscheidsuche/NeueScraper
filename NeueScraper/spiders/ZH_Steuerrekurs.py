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


class ZH_Steuerrekurs(BasisSpider):
	name = 'ZH_Steuerrekurs'

	HOST='https://www.strgzh.ch'
	SEARCH="/entscheide/datenbank/verfahrensnummersuche?subject=&year=&number=&submit=Suchen&page="
	# Trefferzahl pro Seite, wie sie kommen
	TREFFER_PRO_SEITE = 10	
	
	RE_meta=re.compile(r"^(?P<Num>[A-Z][^/,]+[0-9, +-]*)(?:,\s+(?P<Num2>[A-Z][^/,]+[0-9, +-]*))?(?:,\s+(?P<Num3>[A-Z][^/,]+[0-9, +-]*))?(?:,\s+(?P<Num4>[A-Z][^/,]+[0-9, +-]*))?\s+/\s+(?P<Datum>\d+\.\s+(?:"+"|".join(BasisSpider.MONATEde)+")\s+\d\d\d\d)$")
	
	def __init__(self, ab=None, neu=None):
		self.neu=neu
		self.ab=ab
		super().__init__()
		self.request_gen = [self.generate_request()]

	def generate_request(self, page=1):
		request= scrapy.Request(url=self.HOST+self.SEARCH+str(page), callback=self.parse_trefferliste, errback=self.errback_httpbin, meta={'page': page})
		return request

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:10000])
		trefferzahlstring=PH.NC(response.xpath("substring-before(//div[@class='box ruling']/p[contains(.,' Entscheide gefunden')]/text(),' Entscheide gefunden')").get(),error='Trefferzahl nicht gefunden.')
		trefferzahl=int(trefferzahlstring)
		page=response.meta['page']+1
		entscheide=response.xpath("//div[@class='box ruling'][p[@class='cit-title']]")
		logger.info(f"Trefferzahl {trefferzahl}, Seite {page}, Treffer pro Seite {self.TREFFER_PRO_SEITE}, Treffer diese Seite {len(entscheide)}")
		for entscheid in entscheide:
			text=entscheid.get()
			logger.info("Bearbeite Entscheid: "+text)
			item={}
			meta=PH.NC(entscheid.xpath("./p[@class='cit-title']/text()").get(),error="kein cit-title in "+text)
			metaexp=self.RE_meta.search(meta)
			if metaexp:
				item['EDatum']=PH.NC(self.norm_datum(metaexp.group('Datum')),error="kein Datum in: "+meta)
				item['Num']=PH.NC(metaexp.group('Num'),error="keine Geschäftsnummer in: "+meta)
				if metaexp.groupdict().get('Num2'):
					item['Nums']=[item['Num']]
					item['Nums'].append(PH.NC(metaexp.group('Num2'),error="doch keine 2. Geschäftsnummer in: "+meta))
					if metaexp.groupdict().get('Num3'):
						item['Nums'].append(PH.NC(metaexp.group('Num3'),error="doch keine 3. Geschäftsnummer in: "+meta))
						if metaexp.groupdict().get('Num4'):
							item['Nums'].append(PH.NC(metaexp.group('Num4'),error="doch keine 4. Geschäftsnummer in: "+meta))
				
				url=PH.NC(entscheid.xpath("./h2[@class='ruling__title']/a/@href").get(),error="keine PDF-URL in "+text)
				item['PDFUrls']=[self.HOST+url]
				item['Titel']=PH.NC(entscheid.xpath("./h2[@class='ruling__title']/a/text()").get(),error="kein Titel in "+text)
				item['Normen']=PH.NC(entscheid.xpath("./p[@class='legal_foundation']/text()").get(),warning="keine Normenkette in "+text)
				item['Leitsatz']=PH.NC(entscheid.xpath("./p[@class='legal_foundation']/following-sibling::p[not(@class)][1]/text()").get(), warning="kein Leitsatz")
				item['Weiterzug']=PH.NC(entscheid.xpath("./p[@class='note']/text()").get(),warning="kein Rechtskraftvermerk in "+text)	
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
			
				if self.check_blockliste(item):
					yield item
			else:
				logger.error("Metadaten matchen nicht: '"+meta+"'")
		if page*self.TREFFER_PRO_SEITE < trefferzahl:
			request=self.generate_request(page)
			yield request
