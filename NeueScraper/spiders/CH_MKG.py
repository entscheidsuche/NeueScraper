# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

# ENTWURF (Claude, 2026-07-07) — vor Produktivbetrieb:
#  1. Gerichtsliste/CSV braucht neue Signatur CH_MKG_001
#     (Militärkassationsgericht, de/fr/it: Tribunal militaire de cassation /
#     Tribunale militare di cassazione).
#  2. Entscheiddatum steht NICHT in der Trefferliste, nur im PDF-Rubrum.
#     Die Items tragen daher nur PDatum (Upload-Datum der Seite); die Dateien
#     landen als _nodate. Falls unerwünscht: Nachlauf, der das Datum aus dem
#     PDF-Text extrahiert (Rubrum erste Seite, "Urteil vom ..."), oder
#     EDatum-Anreicherung im Konsolidierer.
#  3. Die Bände 1-12 (1915 ff.) liegen auf der Seite nur als Sammel-PDFs
#     ("MKGE Band 15 Nr. 1-9") vor. Diese werden hier bewusst übersprungen
#     (reSammel); wenn die Altbände gewünscht sind, wäre ein Zerlege-Schritt
#     nötig (ein PDF pro Band mit mehreren Entscheiden).


class CH_MKG(BasisSpider):
	name = 'CH_MKG'

	HOST = 'https://www.oa.admin.ch'
	# Übersichtsseite des Oberauditorats mit den Einzelentscheid-PDFs
	# (Stand 07/2026: MKGE Band 13-16 einzeln, ältere nur als Band-PDF).
	URLS = ['/de/urteile-militarkassationsgericht']

	# "MKGE 16 Nr. 15" — Einzelentscheid
	reNum = re.compile(r'MKGE\s+(?P<Band>\d+)\s+Nr\.\s+0?(?P<Nr>\d+)\b')
	# Band-Sammel-PDFs ("MKGE Band 16 Nr. 1-16", "MKGE - ATM - STMC 15 N° 1-9")
	# und Regesten-PDFs überspringen
	reSammel = re.compile(r'Regeste|Band|N[°o]?\s*\d+\s*-\s*\d+|Nrn?\.\s*\d+\s*-\s*\d+|ATM|STMC', re.IGNORECASE)
	# Upload-/Publikationsdatum am Ende des Linktexts ("... 30. Juni 2025")
	reUpload = re.compile(r'(?P<Datum>\d{1,2}\.\s*[A-Za-zäöüéû]+\s+(?:19|20)\d\d)\s*$')

	custom_settings = {
		'DOWNLOAD_DELAY': 2,
		'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
		'AUTOTHROTTLE_ENABLED': True,
	}

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab = ab		# wird hier nicht gebraucht (eine Übersichtsseite), aber Muster-konform
		self.neu = neu
		self.seen = set()
		self.request_gen = [scrapy.Request(url=self.HOST + u, callback=self.parse_trefferliste,
			errback=self.errback_httpbin, dont_filter=True) for u in self.URLS]

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status " + str(response.status))
		antwort = response.text
		logger.info("parse_trefferliste Rohergebnis " + str(len(antwort)) + " Zeichen für " + response.url)

		links = response.xpath("//a[contains(@href,'.pdf')]")
		logger.info(f"{len(links)} PDF-Links gefunden auf {response.url}")
		if not links:
			logger.error("Keine PDF-Links gefunden — Seitenlayout geändert? " + antwort[:5000])
			return

		treffer = 0
		for a in links:
			text = " ".join(t.strip() for t in a.xpath('.//text()').getall() if t.strip())
			href = a.xpath('./@href').get()
			if not href:
				continue
			m = self.reNum.search(text)
			if not m:
				logger.info("Übersprungen (keine Einzelentscheid-Nummer): " + text[:80])
				continue
			if self.reSammel.search(text):
				logger.info("Übersprungen (Sammel-/Regesten-PDF): " + text[:80])
				continue
			num = f"MKGE {m.group('Band')} Nr. {m.group('Nr')}"
			if num in self.seen:
				logger.info("Dublette übersprungen: " + num)
				continue
			self.seen.add(num)

			item = {}
			item['Num'] = num
			item['Titel'] = num
			item['PDFUrls'] = [response.urljoin(href)]
			# Entscheiddatum steht nur im PDF (siehe Kopfkommentar). Das auf der
			# Seite angezeigte Datum ist das Upload-Datum -> PDatum.
			up = self.reUpload.search(text)
			if up:
				pdatum = self.norm_datum(up.group('Datum'), warning=f"Kein Publikationsdatum in {text[:80]}")
				if pdatum and pdatum != "nodate":
					item['PDatum'] = pdatum
			item['Signatur'] = 'CH_MKG_001'
			item['Gericht'], item['Kammer'] = self.detect_by_signatur(item['Signatur'])
			logger.info("Item gelesen: " + json.dumps(item))
			if self.check_blockliste(item):
				yield item
			treffer += 1
		logger.info(f"{treffer} Einzelentscheide auf {response.url} identifiziert.")
