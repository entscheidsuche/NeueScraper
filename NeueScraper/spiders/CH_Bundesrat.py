# -*- coding: utf-8 -*-
import scrapy
import logging
import json
import posixpath
from urllib.parse import urlparse
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)


class CH_Bundesrat(BasisSpider):
	name = 'CH_Bundesrat'

	HOST = 'https://www.bj.admin.ch'
	# Die BJ-Website wurde 2026 komplett neu aufgesetzt (neues Vue-SSR-CMS,
	# neue URL-Struktur /de/... statt /bj/de/home/...). Die alte URL
	# /bj/de/home/publiservice/publikationen/beschwerdeentscheide.html
	# liefert seither HTTP 404.
	URL = '/de/beschwerdeentscheide-des-bundesrates'

	HEADERS = {
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		"Accept-Language": "de-CH,de;q=0.9,en;q=0.7,fr;q=0.6,it;q=0.5",
		"User-Agent": (
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) "
			"Gecko/20100101 Firefox/139.0"
		),
	}

	def __init__(self, ab=None, neu=None):
		self.neu = neu
		self.ab = ab
		super().__init__()
		self.request_gen = self.generate_request()

	def generate_request(self):
		return [scrapy.Request(
			url=self.HOST + self.URL,
			headers=self.HEADERS,
			callback=self.parse_liste,
			errback=self.errback_httpbin,
		)]

	def parse_liste(self, response):
		logger.info("parse_liste response.status " + str(response.status) + " for " + response.request.url)
		antwort = response.text
		logger.info("parse_liste Rohergebnis " + str(len(antwort)) + " Zeichen")
		logger.info("parse_liste Rohergebnis: " + antwort[:40000])

		# Jede Publikation ist eine 'card' mit Datum (.meta-info__item),
		# Titel (.card__title h3) und einem Link zur Detailseite
		# (.card__footer__action a). Auf der Detailseite liegt das PDF.
		# Es werden bewusst ALLE Karten mit Detaillink erfasst, also nicht
		# nur die eigentlichen Beschwerdeentscheide, sondern auch die
		# zugehoerigen prozeduralen EJPD-Dokumente (Ueberweisungen,
		# Schreiben, Zwischenverfuegungen) -- der alte Spider hat diese
		# ebenfalls geliefert.
		cards = response.xpath(
			'//div[contains(concat(" ", normalize-space(@class), " "), " card ")]'
			'[.//div[contains(@class, "card__footer__action")]//a/@href]'
		)
		logger.info(str(len(cards)) + " Karten gefunden")

		if not cards:
			logger.error("keine Entscheidkarten gefunden -- Seitenstruktur evtl. geaendert")
			return

		for card in cards:
			detail_href = card.xpath(
				'.//div[contains(@class, "card__footer__action")]//a/@href'
			).get()
			if not detail_href:
				continue

			datum_roh = card.xpath(
				'.//*[contains(@class, "meta-info__item")]/text()'
			).get()
			titel = " ".join(t.strip() for t in card.xpath(
				'.//div[contains(@class, "card__title")]//h3//text()'
			).getall() if t.strip())

			item = {}
			item['EDatum'] = PH.NC(
				self.norm_datum(datum_roh) if datum_roh else "nodate",
				warning="kein Datum gefunden in Karte fuer " + detail_href,
			)
			item['Num'] = detail_href
			item['noNumDisplay'] = True
			item['Leitsatz'] = titel
			item['VGericht'] = ''
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'], "", item['Num'])
			logger.info("parse_liste Item: " + json.dumps(item))

			detail_url = detail_href if detail_href.startswith("http") else self.HOST + detail_href
			yield scrapy.Request(
				url=detail_url,
				headers=self.HEADERS,
				callback=self.parse_page,
				errback=self.errback_httpbin,
				meta={'item': item},
			)

	def parse_page(self, response):
		logger.info("parse_page response.status " + str(response.status) + " for " + response.request.url)
		antwort = response.text
		logger.info("parse_page Rohergebnis " + str(len(antwort)) + " Zeichen")

		item = response.meta['item']

		# PDF-Download: <a class="download-item" href="https://www.bj.admin.ch/dam/.../<name>.pdf">
		pdf_urls = response.xpath(
			'//a[contains(concat(" ", normalize-space(@class), " "), " download-item ")]/@href'
		).getall()
		pdf_urls = [u for u in pdf_urls if u and u.lower().endswith(".pdf")]

		if not pdf_urls:
			logger.error("kein PDF-Download auf Detailseite gefunden: " + response.request.url)
			return

		if len(pdf_urls) > 1:
			logger.warning(
				"mehrere PDF-Downloads auf " + response.request.url
				+ " gefunden, verwende den ersten: " + json.dumps(pdf_urls)
			)

		pdf_url = pdf_urls[0]
		item['PDFUrls'] = [pdf_url]

		# Eindeutige, stabile Dokument-ID aus dem PDF-Dateinamen ableiten.
		# Die Namen sind sprechend und mit ISO-Datum praefixiert, z.B.
		# "2025-06-13-beschwerde-eda" -> garantiert eindeutig auch bei
		# mehreren Entscheiden am selben Datum. forceID umgeht die
		# Datums-basierte Namensgebung (num[:20]+EDatum), die bei
		# mehreren Dokumenten pro Tag zu Dateinamen-Kollisionen fuehrte.
		stem = posixpath.basename(urlparse(pdf_url).path)
		if stem.lower().endswith(".pdf"):
			stem = stem[:-4]
		item['forceID'] = stem

		# Falls aus der Liste kein Datum kam, aus dem ISO-Praefix des
		# Dateinamens nachziehen.
		if item.get('EDatum') in (None, '', 'nodate'):
			item['EDatum'] = self.norm_datum(stem)

		logger.info("parse_page item: " + json.dumps(item))
		yield item
