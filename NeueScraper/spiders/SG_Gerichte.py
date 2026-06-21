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


class SG_Gerichte(BasisSpider):
	name = 'SG_Gerichte'

	SUCH_URL_GERICHTE='/rechtsprechung-gerichte/?filter%5BtimerangeType%5D=5&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D=&filter%5BtimerangeStop%5D=&filter%5Binstitution%5D=&searchQuery='
	SUCH_URL_GERICHTE_ab='/rechtsprechung-gerichte/?filter%5BtimerangeType%5D=6&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D={ab}&filter%5BtimerangeStop%5D=31.12.2099&filter%5Binstitution%5D=&searchQuery='
	SUCH_URL_DEPT='/rechtsprechung-departemente/?filter%5BtimerangeType%5D=5&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D=&filter%5BtimerangeStop%5D=&filter%5Binstitution%5D=&searchQuery='
	SUCH_URL_DEPT_ab='/rechtsprechung-departemente/?filter%5BtimerangeType%5D=6&filter%5BlandmarkRulings%5D=&filter%5BtimerangeStart%5D={ab}&filter%5BtimerangeStop%5D=31.12.2099&filter%5Binstitution%5D=&searchQuery='
	HOST ="https://publikationen.sg.ch"
	HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0'}

	# Opt-in fuer die wiederverwendbare OopsRetryMiddleware: bei kaputten
	# PDF-Antworten (kein '%PDF-'-Header oder kein '%%EOF' am Ende) wird mit
	# frischer Zyte-Session-ID und neuem Browser-Profil und 5s Backoff erneut
	# angefragt (max. 3 Versuche). Andere Spider werden davon nicht beruehrt.
	# Plus moderater Durchsatz-Boost: mit 10 rotierenden Sessions ist eine
	# hoehere Concurrency unproblematisch fuer publikationen.sg.ch.
	custom_settings = {
		'DOWNLOADER_MIDDLEWARES': {
			'NeueScraper.middlewares.OopsRetryMiddleware': 580,
		},
		'DOWNLOAD_DELAY': 0.3,
		'AUTOTHROTTLE_TARGET_CONCURRENCY': 4,
		'CONCURRENT_REQUESTS_PER_DOMAIN': 5,
	}

	# (Quelle, URL ohne ab-Parameter, URL mit ab-Parameter)
	QUELLEN = [
		('Gerichte', SUCH_URL_GERICHTE, SUCH_URL_GERICHTE_ab),
		('Verwaltungsbehörden', SUCH_URL_DEPT, SUCH_URL_DEPT_ab),
	]

	reURL=re.compile(r'^<a href="(?P<URL>[^"]+)">(?P<Num>\s*\d+/\d+ \d+)\s+(?P<Titel>[^\s(<][^(<]*[^<])?(?:</a>)?$')

	def get_next_request(self, quelle, base, base_ab, ab=None):
		url = self.HOST + (base_ab.format(ab=ab) if ab else base)
		# Browser/Session-Rotation auch fuer die HTML-Listings (Anti-Throttle),
		# aber NICHT die OopsRetryMiddleware aktivieren — die ist nur fuer
		# PDF-Downloads gedacht. Die Markierung wird ausschliesslich pro Item
		# (item['OopsRetry']) gesetzt und von MyFilesPipeline an die PDF-Request
		# weitergereicht.
		headers, meta = self.apply_rotation(meta={'gesehen': 0, 'quelle': quelle},
		                                    headers=dict(self.HEADERS))
		return scrapy.Request(url=url, headers=headers, callback=self.parse_trefferliste,
		                      errback=self.errback_httpbin, meta=meta)

	def __init__(self, ab=None, neu=None):
		super().__init__()
		# Spezialwert "zuletzt": heute minus 183 Tage als Startdatum verwenden
		if ab == "zuletzt":
			ab_datum = datetime.date.today() - datetime.timedelta(days=183)
			ab = ab_datum.strftime("%d.%m.%Y")
			logger.info("Parameter 'ab=zuletzt' -> berechnetes Startdatum: "+ab)
		self.ab=ab
		self.neu=neu
		# Pagination-Zustand pro Quelle, weil zwei parallele Stränge laufen
		self.next_link={}
		self.timer={}
		# 10 Zyte-Smart-Proxy-Sessions im Pool, kombiniert mit 10 Browser-Profilen
		# (in BasisSpider.BROWSER_PROFILES). Pro Request wird Profil und Session
		# zufaellig gezogen; bei Retry (OopsRetryMiddleware) wird beides erneuert.
		self._init_rotation(10)
		self.request_gen = [self.get_next_request(q, base, base_ab, ab) for q, base, base_ab in self.QUELLEN]


	def parse_trefferliste(self, response):
		quelle=response.meta['quelle']
		logger.debug("parse_trefferliste ["+quelle+"] response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste ["+quelle+"] Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste ["+quelle+"] Rohergebnis: "+antwort[:30000])

		gesehen=response.meta['gesehen']
		if gesehen==0:
			treffer=PH.NC(response.xpath("//div[@class='box box-large box-mainbox pb-3']/p[@class='mt-4 mb-0']/b/text()").get(),error='Trefferzahl nicht erkannt in '+response.url+': '+antwort)
			trefferzahl=int(treffer.split(" ")[0])
			self.timer[quelle]=int((datetime.datetime.now()-datetime.datetime(1970,1,1)).total_seconds()*1000)
			self.next_link[quelle]=PH.NC(response.xpath("//a[@class='control-pagebrowser__next-page']/@href").get(), error="Nextlink nicht gefunden in"+response.url+': '+antwort)
			page=2
			if 'page=2' in self.next_link[quelle]:
				pos=self.next_link[quelle].index('page=2')
				self.next_link[quelle]=self.next_link[quelle][:pos+5]+'{page}'+self.next_link[quelle][pos+6:]
			else:
				logger.error("page nicht gefunden in: "+self.next_link[quelle])
		else:
			trefferzahl=response.meta['trefferzahl']
			page=response.meta['page']+1
		next_link=self.next_link[quelle].format(page=page)+"&_="+str(self.timer[quelle])
		self.timer[quelle]+=1

		entscheide=response.xpath('//div[@class="publication-list__item publication-list__item--publication box box-large box-mainbox pb-5"]')
		logger.info("Treffer auf dieser Seite ["+quelle+"]: "+str(len(entscheide)))
		for entscheid in entscheide:
			text=entscheid.get()
			item={}
			item['Num']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Fall-Nr.')]/following-sibling::dd/text()").get(), error="Keine Geschäftsnummer erkannt in: "+text)
			if quelle=="Gerichte":
				item['VKammer']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Rubrik')]/following-sibling::dd/text()").get(), warning="keine Kammer: "+text)
				item['VGericht']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Publizierende Stelle')]/following-sibling::dd/text()").get(), error="Gericht nicht erkannt in: "+text)
			else:
				item['VKammer']=PH.NC(entscheid.xpath(".//dt[@class='pr-1'][contains(.,'Publizierende Stelle')]/following-sibling::dd/text()").get(), error="Departement nicht erkannt in: "+text)
				item['VGericht']=quelle
			item['PDatum']=self.norm_datum(PH.NC(entscheid.xpath(".//li/span/b[starts-with(.,'Publikationsdatum')]/text()").get(), error="kein Publikationsdatum erkannt in: "+text))
			item['EDatum']=self.norm_datum(PH.NC(entscheid.xpath(".//li/span/b[starts-with(.,'Entscheiddatum')]/text()").get(), error="kein Entscheiddatum erkannt in: "+text))
			item['Abstract']=PH.NC(entscheid.xpath(".//article[@class='publication-summary']/p/text()").get(), error="keinen Abstract gefunden in: "+text)
			url=self.HOST+PH.NC(entscheid.xpath(".//div[@class='publication-list__item-buttons d-flex main-box-btn-wrap justify-content-md-start align-items-center pt-2 flex-wrap flex-md-nowrap']/a/@href").get(),error="keine PDF-Url gefunden in: "+text)
			item['PDFUrls']=[url]
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'],item['VKammer'],item['Num'])
			# Pro Item Rotation: PDFHeaders + ZyteSession werden in
			# MyFilesPipeline.get_media_requests ausgewertet. OopsRetry aktiviert
			# die OopsRetryMiddleware fuer den PDF-Download.
			pdf_headers, pdf_meta = self.apply_rotation()
			item['PDFHeaders'] = pdf_headers
			item['ZyteSession'] = pdf_meta['session_id']
			item['OopsRetry'] = True

			yield item

		gesehen+=len(entscheide)
		# Pagination beenden, sobald eine Seite leer zurueckkommt. Sonst entstehen
		# Endlos-Schleifen, weil der Server fuer Seiten jenseits des Endes mit einer
		# leeren Trefferliste antwortet, ohne die Trefferzahl nach unten zu korrigieren.
		if len(entscheide) == 0:
			logger.info(f"Leere Trefferliste [{quelle}] auf Seite {page} — Pagination beendet "
			            f"(gesehen={gesehen}, trefferzahl={trefferzahl}).")
		elif gesehen<trefferzahl:
			# Auch fuer Folgeseiten Rotation anwenden, damit Listing-Last verteilt wird.
			# Kein oops_retry auf HTML-Listings — die Middleware ist nur fuer PDFs.
			folge_headers, folge_meta = self.apply_rotation(
				meta={'gesehen': gesehen, 'trefferzahl': trefferzahl, 'page': page,
				      'quelle': quelle},
				headers=dict(self.HEADERS))
			yield scrapy.Request(url=self.HOST+next_link, headers=folge_headers,
			                     callback=self.parse_trefferliste, errback=self.errback_httpbin,
			                     meta=folge_meta)


