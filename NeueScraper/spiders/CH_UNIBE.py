# -*- coding: utf-8 -*-
"""Scraper für historische BGE-Entscheide (Bände 1–79, Jahrgänge 1875–1953)
auf https://www.servat.unibe.ch/dfr/ (Universität Bern, Prof. Tschentscher).

Die Seite organisiert die Entscheide retrospektiv in den **fünf Teilen** des
BGE (I = öffentliches Recht, II = Familien-/Erb-/Sachenrecht,
III = Schuldbetreibung & Konkurs / OR-Recht, IV = Strafrecht,
V = Sozialversicherungs- bzw. Familienrecht). Pro Teil eine Index-Seite:
``dfr_bge1.html`` bis ``dfr_bge5.html``.

Pro Eintrag wird ein Detail-Request abgesetzt, der Body extrahiert und am
Ende ein trilingualer Quellen-Hinweis angehängt:

    Entscheid automatisiert übernommen von / Extrait automatiquement depuis /
    Estratto automaticamente dal https://www.servat.unibe.ch

Bände >= 80 (Jahrgänge ab 1954) holt CH_BGE.py vom regulären BGer-Server;
hier wird mit ``BIS_BAND = 79`` strikt darauf gefiltert.

Roman-Ziffern werden ohne Modifikation an ``self.detect()`` weitergereicht,
inklusive historischer Untergliederungen wie ``Ia`` oder ``Ib``. Wie diese
zugeordnet werden, entscheidet die Signaturen-Match-Tabelle.
"""
import scrapy
import re
import logging
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)


class CH_UNIBE(BasisSpider):
	name = 'CH_UNIBE'

	HOST = 'https://www.servat.unibe.ch'

	# Die fünf Teile der amtlichen Sammlung BGE — eine Index-URL pro Teil.
	# Jede dieser Seiten enthält ALLE Entscheide eines Teils (modern + historisch);
	# wir filtern später strikt auf Band ≤ BIS_BAND.
	TEILE = [
		('I',   '/dfr/dfr_bge1.html'),
		('II',  '/dfr/dfr_bge2.html'),
		('III', '/dfr/dfr_bge3.html'),
		('IV',  '/dfr/dfr_bge4.html'),
		('V',   '/dfr/dfr_bge5.html'),
	]

	# Höchster Band, den wir hier holen wollen. 79 = letzter Band des
	# klassischen BGE (Jahrgang 1953). Ab Band 80 (1954) holt CH_BGE.
	BIS_BAND = 79

	HEADER = {
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br',
		'Connection': 'keep-alive',
		'Upgrade-Insecure-Requests': '1',
	}

	# Universitätsserver — defensiv drosseln.
	custom_settings = {
		"DOWNLOAD_DELAY": 0.5,
		"RANDOMIZE_DOWNLOAD_DELAY": True,
		"CONCURRENT_REQUESTS_PER_DOMAIN": 4,
		"CONCURRENT_REQUESTS": 8,
		"AUTOTHROTTLE_ENABLED": True,
		"AUTOTHROTTLE_TARGET_CONCURRENCY": 4,
		"AUTOTHROTTLE_START_DELAY": 0.5,
		"AUTOTHROTTLE_MAX_DELAY": 10.0,
	}

	# Trilingualer Quellen-Hinweis, wird unter jeden Entscheid angehängt.
	FOOTER_HTML = (
		'<p style="font-size:0.9em; color:#555; margin-top:2em; '
		'border-top:1px solid #ccc; padding-top:0.5em;">'
		'Entscheid automatisiert übernommen von / '
		'Extrait automatiquement depuis / '
		'Estratto automaticamente dal '
		'<a href="https://www.servat.unibe.ch">https://www.servat.unibe.ch</a>'
		'</p>'
	)

	# Regex auf den Linktext "BGE 1 I 3" — nur zur Zerlegung in Komponenten,
	# nicht zur HTML-Suche (die macht XPath).
	reBGE = re.compile(
		r'^\s*BGE\s+(?P<band>\d+)\s+(?P<roman>[IVX]+[ab]?)\s+(?P<seite>\d+)\s*$'
	)

	# Klammern um das Datum entfernen: "(07.05.1875)" → "07.05.1875"
	reDateClean = re.compile(r'^\(\s*(?P<datum>\d\d\.\d\d\.\d\d\d\d)\s*\)\s*$')

	# DocID aus dem Dateinamen extrahieren — egal ob href relativ ("c1001003.html")
	# oder absolut ("/dfr/c2145303.html") ist. Wir suchen den letzten c<DIGITS>-
	# Block am Ende des Pfads.
	reDocID = re.compile(r'(?P<docid>c\d+)\.html$')

	def __init__(self, ab=None, neu=None, bis=None):
		super().__init__()
		self.ab = ab
		self.neu = neu
		self.bis = bis
		self.request_gen = self._build_initial_requests()

	def _build_initial_requests(self):
		"""Eine Anfrage pro Teil-Index-Seite (5 Stück)."""
		return [
			scrapy.Request(
				url=self.HOST + path,
				headers=self.HEADER,
				callback=self.parse_index,
				errback=self.errback_httpbin,
				dont_filter=True,
				meta={'teil': roman},
			)
			for roman, path in self.TEILE
		]

	# ------------------------------------------------------------------
	# Index-Parsing
	# ------------------------------------------------------------------
	def parse_index(self, response):
		teil = response.meta.get('teil')
		logger.info(
			f"parse_index Teil {teil} response.status {response.status} URL: {response.url}"
		)

		# Ein Eintrag ist ein <a href="...c<NN>.html">BGE V Roman P</a>, gefolgt
		# (auf gleicher Ebene) von <b>Titel</b> und <small>(Datum)</small>.
		# Achtung: die href-Form unterscheidet sich pro Teil-Index-Seite —
		# Teil I hat relative Pfade ("c1147206.html"), Teile II–V haben
		# absolute ("/dfr/c2145303.html"). Wir matchen daher nur über den
		# Linktext, der konsistent mit "BGE " beginnt.
		entries = response.xpath(
			'//a[contains(@href, ".html") and starts-with(text(), "BGE ")]'
		)
		logger.info(f"parse_index Teil {teil}: {len(entries)} Anker gefunden")

		gefunden = 0
		gefiltert_band = 0
		gefiltert_jahr = 0
		yielded = 0
		ungueltig = 0

		for anchor in entries:
			gefunden += 1
			href = PH.NC(
				anchor.xpath('./@href').get(),
				warning=f"Anker ohne href in Teil {teil}",
			)
			if not href:
				ungueltig += 1
				continue
			doc_match = self.reDocID.search(href)
			if not doc_match:
				logger.warning(f"Ungültige DocID-Form: href={href!r} (Teil {teil})")
				ungueltig += 1
				continue
			doc_id = doc_match.group('docid')

			bge_text = PH.NC(
				anchor.xpath('./text()').get(),
				warning=f"Anker {href} ohne Text in Teil {teil}",
			)
			m = self.reBGE.match(bge_text or '')
			if not m:
				logger.warning(
					f"Linktext nicht als BGE-Referenz parsbar: {bge_text!r} "
					f"(href={href}, Teil {teil})"
				)
				ungueltig += 1
				continue

			band = int(m.group('band'))
			roman = m.group('roman')
			seite = int(m.group('seite'))

			# Band-Filter: nur historische BGE
			if band > self.BIS_BAND:
				gefiltert_band += 1
				continue

			# Titel = unmittelbar folgender <b>-Tag, Datum = folgender <small>
			titel = PH.NC(
				anchor.xpath('./following-sibling::b[1]/text()').get(),
				replace='',
				info=f"kein Titel für BGE {band} {roman} {seite}",
			)
			datum_roh = PH.NC(
				anchor.xpath('./following-sibling::small[1]/text()').get(),
				warning=f"kein Datum-Element für BGE {band} {roman} {seite}",
			)

			# Datum aus Klammern lösen: "(07.05.1875)" → "07.05.1875"
			datum_str = ''
			jahr = None
			if datum_roh:
				dm = self.reDateClean.match(datum_roh)
				if dm:
					datum_str = dm.group('datum')
					try:
						jahr = int(datum_str.split('.')[2])
					except (IndexError, ValueError):
						jahr = None
				else:
					logger.warning(
						f"Datum-Format unerwartet: {datum_roh!r} "
						f"für BGE {band} {roman} {seite}"
					)

			# Optionale Jahres-Filter (ab/bis)
			if jahr is not None:
				if self.ab and jahr < int(self.ab):
					gefiltert_jahr += 1
					continue
				if self.bis and jahr > int(self.bis):
					gefiltert_jahr += 1
					continue

			# norm_datum kann mit leerem String umgehen (gibt None zurück) —
			# wir loggen aber explizit, wenn kein Datum vorlag
			edatum = self.norm_datum(datum_str) if datum_str else None
			if not edatum:
				logger.warning(
					f"BGE {band} {roman} {seite}: kein gültiges EDatum "
					f"(roh={datum_roh!r})"
				)

			# Item zusammenbauen — Num behält die echte Zitation (inkl. Ia/Ib).
			# response.urljoin baut die absolute URL aus dem href-Wert auf,
			# unabhängig davon ob er relativ ("c1xxx.html") oder absolut
			# ("/dfr/c2xxx.html") notiert ist.
			doc_url = response.urljoin(href)
			item = {
				'DocID': doc_id,
				'Num': f"BGE {band} {roman} {seite}",
				'Titel': titel,
				'EDatum': edatum,
				'HTMLUrls': [doc_url],
				'Quelle': 'servat.unibe.ch',
			}

			# Roman-Ziffer unverändert an detect() weiterreichen — die
			# Match-Tabelle entscheidet, wie mit Ia/Ib umgegangen wird.
			# (Der Spider stripped hier bewusst NICHT, weil die Unterscheidung
			# Ia/Ib gegenüber I in der Signaturen-Tabelle absichtlich gemacht
			# wird, damit moderne und historische Inhalte richtig zugeordnet
			# bleiben.)
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(
				"", "", item['Num']
			)

			logger.info(
				f"Index-Treffer Teil {teil} → Band={band} {roman} S.{seite} "
				f"({datum_str or '?'}) Sig={item['Signatur']} URL={doc_url}"
			)

			yield scrapy.Request(
				url=doc_url,
				headers=self.HEADER,
				callback=self.parse_document,
				errback=self.errback_httpbin,
				meta={'item': item, 'teil': teil},
				dont_filter=True,
			)
			yielded += 1

		logger.info(
			f"parse_index Teil {teil} abgeschlossen: "
			f"gefunden={gefunden}, ungültig={ungueltig}, "
			f"verworfen_band>{self.BIS_BAND}={gefiltert_band}, "
			f"verworfen_jahresfilter={gefiltert_jahr}, "
			f"yielded={yielded}"
		)

	# ------------------------------------------------------------------
	# Document-Parsing
	# ------------------------------------------------------------------
	def parse_document(self, response):
		item = response.meta['item']
		teil = response.meta.get('teil', '?')
		logger.info(
			f"parse_document Teil {teil} {item.get('Num')} "
			f"response.status {response.status} URL: {response.url}"
		)

		# Rechte Spalte = der eigentliche Entscheidungstext + interne Tools.
		# Bootstrap-Layout: col-sm-2 (Navigation) + col-sm-10 (Content).
		body_html = PH.NC(
			response.xpath('//div[contains(@class, "col-sm-10")]').get(),
			warning=(
				f"col-sm-10 nicht gefunden in {response.url} "
				f"({item.get('Num')}); falle auf <body> zurück"
			),
		)
		if not body_html:
			body_html = PH.NC(
				response.xpath('//body').get(),
				error=f"weder col-sm-10 noch <body> in {response.url}",
				replace='',
			)

		# Bearbeitung/Copyright-Zeile von Tschentscher entfernen — der separate
		# trilinguale Quellen-Hinweis ersetzt sie.
		body_html = re.sub(
			r'<tr[^>]*>\s*<td[^>]*bgcolor="#002856"[^>]*>.*?</tr>',
			'',
			body_html,
			flags=re.DOTALL | re.IGNORECASE,
		)

		# Trilingualer Quellen-Hinweis anhängen
		full_html = body_html + self.FOOTER_HTML

		PH.write_html(full_html, item, self)
		yield item
