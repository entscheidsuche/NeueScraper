# -*- coding: utf-8 -*-
"""Scraper für den historischen BGE-Vollbestand (Bände 1–79, Jahrgänge
1875–1953) auf https://www.servat.unibe.ch/dfr/ (Universität Bern,
Prof. Tschentscher).

Quelle sind die BANDWEISEN Indexseiten dfr_bge00.html (Bände 1–9) bis
dfr_bge07.html (Bände 70–79). Sie listen den kompletten Bestand — anders als
die früher genutzten Teil-Seiten dfr_bge1..5.html, die nur Tschentschers
kuratierte HTML-Auswahl (~346 Entscheide) enthalten. Aufbau:

    <div class="col">
      <b>BGE 1 I:</b><br>
      <a href="c1001003.html">3</a>, <a href="c1001013.pdf">13</a>, ...
    </div>

Die Überschrift <b>BGE {Band} {Teil}:</b> liefert Band + Teil, jeder folgende
<a> ist ein Entscheid (Linktext = Seite). Pro Entscheid gibt es ENTWEDER eine
transkribierte HTML-Seite (~8 %) ODER ein Scan-PDF (~92 %), nie beides.

Datum: Die amtliche Sammlung hat genau einen Band pro Jahr, daher
Jahr = 1874 + Band (verifiziert 1→1875, 26→1900, 46→1920, 50→1924, 66→1940,
79→1953). Der Spider setzt EDatum auf den 1.1. dieses Jahres. Das exakte
Urteilsdatum wird aus dem Dokument nachgezogen:
  - HTML: direkt hier aus dem Seitenkopf (parse_html_document),
  - PDF:  in MyFilesPipeline.file_downloaded, wenn das Flag 'PDFDatumPruefen'
          gesetzt ist (dort liegt das PDF ohne Zweitabruf vor).
Ein Textdatum wird nur übernommen, wenn sein Jahr zu 1874+Band passt (±1) —
das fängt OCR-Müll ab (die alten Scans sind teils schlecht erkannt).

forceID = Fundstelle macht die DocID datumsunabhängig (pipelines.py
PipelineHelper.file_path), sodass die spätere PDF-Datumskorrektur den Pfad
nicht ändert.

Bände ≥ 80 (ab 1954) holt CH_BGE vom regulären BGer-Server; hier BIS_BAND = 79.
"""
import re
import datetime
import logging
import scrapy
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)


# Anker auf die Kopfzeile eines Entscheids; das Datum steht direkt danach.
_reUrteilAnker = re.compile(
	r'(?:Urteil|Urtheil|Entscheid|Arr[eê]t|Sentenza)\b', re.IGNORECASE
)

# Monatsname (de/fr/it, kleingeschrieben) -> Monatsnummer. Eigene Tabelle,
# weil die basis-Regexe nur 19xx/20xx-Jahre erfassen; die historischen BGE
# beginnen aber 1875 (18xx). Deshalb hier ein Datums-Regex, der auch 18xx nimmt.
_MONAT_NR = {}
for _lst in (BasisSpider.MONATEde, BasisSpider.MONATEfr, BasisSpider.MONATEit):
	for _i, _name in enumerate(_lst, 1):
		_MONAT_NR[_name.lower()] = _i

_reDatum = re.compile(r'(\d\d?)\.?\s*([A-Za-zÀ-ÿ]+)\s+((?:18|19|20)\d\d)')


def band_jahr(band):
	"""Amtliche Sammlung: genau ein Band pro Jahr -> Jahr = 1874 + Band."""
	return 1874 + band


def datum_aus_text(text, band, spider=None):
	"""Urteilsdatum aus (Whitespace-normalisiertem) Dokumenttext lesen.

	Sucht die Kopfzeile ("Urteil/Arrêt/Sentenza …") und liest das direkt
	folgende Datum (de/fr/it, inkl. 18xx-Jahren). Übernahme nur, wenn das Jahr
	zu 1874+Band passt (±1) — das fängt OCR-Müll wie "lSmO" ab. Sonst Fallback
	{1874+Band}-01-01 (jahresgenau, wie OpenCaseLaw). Wird von beiden Zweigen
	genutzt: HTML (Spider) und PDF (MyFilesPipeline). `spider` wird nicht mehr
	benötigt (Signatur bleibt für die bestehenden Aufrufer erhalten).
	"""
	soll = band_jahr(band)
	flach = re.sub(r'\s+', ' ', text or '')
	m = _reUrteilAnker.search(flach)
	if m:
		fenster = flach[m.end():m.end() + 60]
		for d in _reDatum.finditer(fenster):
			nr = _MONAT_NR.get(d.group(2).lower())
			if not nr:
				continue
			jahr = int(d.group(3))
			if abs(jahr - soll) <= 1:
				try:
					# Kalendertag validieren — OCR verstümmelt Tage (z.B. "98"),
					# ein ungültiges Datum würde Elasticsearch beim Indexieren
					# mit mapper_parsing_exception ablehnen.
					return datetime.date(jahr, nr, int(d.group(1))).isoformat()
				except ValueError:
					break
			break
	return "%d-01-01" % soll


class CH_UNIBE(BasisSpider):
	name = 'CH_UNIBE'

	HOST = 'https://www.servat.unibe.ch'

	# Bandweise Indexseiten: bge00 = Bände 1–9 ... bge07 = Bände 70–79.
	INDEX_PAGES = ['/dfr/dfr_bge0%d.html' % n for n in range(0, 8)]

	# Höchster Band, den wir hier holen; 79 = letzter Band des klassischen BGE
	# (Jahrgang 1953). Ab Band 80 (1954) holt CH_BGE.
	BIS_BAND = 79

	HEADER = {
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) '
		              'Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,fr;q=0.7,it;q=0.5,en;q=0.3',
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

	# Trilingualer Quellen-Hinweis, wird unter jeden HTML-Entscheid angehängt.
	FOOTER_HTML = (
		'<p style="font-size:0.9em; color:#555; margin-top:2em; '
		'border-top:1px solid #ccc; padding-top:0.5em;">'
		'Entscheid automatisiert übernommen von / '
		'Extrait automatiquement depuis / '
		'Estratto automaticamente dal '
		'<a href="https://www.servat.unibe.ch">https://www.servat.unibe.ch</a>'
		'</p>'
	)

	# Ueberschrift eines Band-Teil-Blocks: "BGE 1 I:" (roman inkl. Ia/Ib).
	reHeader = re.compile(r'BGE\s+(?P<band>\d+)\s+(?P<teil>[IVX]+[ab]?)\s*:')
	# Entscheid-Link: c<CODE>.html oder c<CODE>.pdf am Ende des Pfads.
	reDocCode = re.compile(r'(?P<docid>c\d+)\.(?P<kind>html|pdf)(?:$|[?#])')

	def __init__(self, ab=None, neu=None, bis=None):
		super().__init__()
		self.ab = ab
		self.neu = neu
		self.bis = bis
		self.request_gen = self._build_initial_requests()

	def _build_initial_requests(self):
		"""Eine Anfrage pro bandweiser Indexseite (dfr_bge00..07)."""
		return [
			scrapy.Request(
				url=self.HOST + path,
				headers=self.HEADER,
				callback=self.parse_index,
				errback=self.errback_httpbin,
				dont_filter=True,
			)
			for path in self.INDEX_PAGES
		]

	# ------------------------------------------------------------------
	# Index-Parsing: linearer Scan über <b>-Überschriften und <a>-Links in
	# Dokumentreihenfolge. Jede Überschrift setzt den aktuellen Band + Teil,
	# jeder folgende Entscheid-Link erbt diesen Kontext.
	# ------------------------------------------------------------------
	def parse_index(self, response):
		nodes = response.xpath(
			'//b[starts-with(normalize-space(.),"BGE ")]'
			' | //a[contains(@href,"c") and '
			'(contains(@href,".html") or contains(@href,".pdf"))]'
		)
		band = None
		teil = None
		gefunden = 0
		yielded = 0

		for sel in nodes:
			if sel.root.tag == 'b':
				h = self.reHeader.search(sel.xpath('normalize-space(.)').get() or '')
				if h:
					band = int(h.group('band'))
					teil = h.group('teil')
				continue

			href = sel.xpath('./@href').get() or ''
			dm = self.reDocCode.search(href)
			if not dm or band is None or band > self.BIS_BAND:
				continue

			gefunden += 1
			seite = (sel.xpath('normalize-space(.)').get() or '').strip()
			kind = dm.group('kind')
			url = response.urljoin(href)

			item = {
				'DocID': dm.group('docid'),
				'Num': "BGE %d %s %s" % (band, teil, seite),
				'Titel': '',
				# Band-Jahr; das exakte Datum wird spaeter nachgezogen (HTML hier,
				# PDF in der Files-Pipeline).
				'EDatum': "%d-01-01" % band_jahr(band),
				'Quelle': 'servat.unibe.ch',
			}
			# forceID = Fundstelle -> DocID/Pfad haengt NICHT von EDatum ab
			# (pipelines.py PipelineHelper.file_path). Damit bleibt die DocID bei
			# der spaeteren PDF-Datumskorrektur stabil.
			item['forceID'] = item['Num']
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(
				"", "", item['Num']
			)

			if kind == 'html':
				yield scrapy.Request(
					url=url,
					headers=self.HEADER,
					callback=self.parse_html_document,
					errback=self.errback_httpbin,
					meta={'item': item, 'band': band},
					dont_filter=True,
				)
			else:  # pdf: NICHT hier laden -> Files-Pipeline holt es via PDFUrls
				item['PDFUrls'] = [url]
				item['PDFDatumPruefen'] = True   # Flag: Datum aus PDF nachziehen
				yield item

			yielded += 1

		logger.info(
			"parse_index %s: entscheide=%d, yielded=%d"
			% (response.url, gefunden, yielded)
		)

	# ------------------------------------------------------------------
	# HTML-Entscheid: Body speichern + exaktes Datum aus dem Seitenkopf.
	# ------------------------------------------------------------------
	def parse_html_document(self, response):
		item = response.meta['item']
		band = response.meta['band']
		logger.info(
			"parse_html_document %s response.status %s URL: %s"
			% (item.get('Num'), response.status, response.url)
		)

		body_html = PH.NC(
			response.xpath('//div[contains(@class, "col-sm-10")]').get(),
			warning="col-sm-10 nicht gefunden in %s (%s); falle auf <body> zurück"
			% (response.url, item.get('Num')),
		)
		if not body_html:
			body_html = PH.NC(
				response.xpath('//body').get(),
				error="weder col-sm-10 noch <body> in %s" % response.url,
				replace='',
			)

		# Bearbeitungs-/Copyright-Zeile von Tschentscher entfernen — der
		# separate trilinguale Quellen-Hinweis ersetzt sie.
		body_html = re.sub(
			r'<tr[^>]*>\s*<td[^>]*bgcolor="#002856"[^>]*>.*?</tr>',
			'',
			body_html,
			flags=re.DOTALL | re.IGNORECASE,
		)

		item['EDatum'] = datum_aus_text(response.text, band, self)
		titel = response.xpath('normalize-space(//title)').get() or ''
		item['Titel'] = titel.split(' - ')[-1].strip() if ' - ' in titel else ''
		item['HTMLUrls'] = [response.url]

		PH.write_html(body_html + self.FOOTER_HTML, item, self)
		yield item
