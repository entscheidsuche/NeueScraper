# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from io import BytesIO
from urllib.parse import urldefrag
from scrapy.http import Response
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

# Militärkassationsgericht (MKG / TMC / TMC), publiziert vom Oberauditorat.
#
#  - Das MKG hat keine Kammern: ein Eintrag CH_MKG_001 in der Gerichtsliste,
#    detect() liefert ohne Mehrfachspider immer Zeile 0.
#  - Quelle ist eine einzige Übersichtsseite. Stand 10/2026: Band 13, 15, 16 als
#    Einzel-PDFs, Band 14 (2014-2021, 34 Entscheide) nur als Sammel-PDF.
#    Ältere Bände (1-12) stehen nicht auf der Seite.
#  - Jedes Entscheid-PDF endet mit einer Fusszeile wie
#      "(MKG 950, 28 novembre 2025, auditeur contre Tribunal militaire d'appel 1)"
#      "(Nr. 798/799, 13. Dezember 2007, R. W. und Auditor c. Mil Ger 4)"
#    Daraus kommen Geschäftsnummer (Num2), Entscheiddatum (EDatum) und Sprache.
#    Num ist die Fundstelle "MKGE <Band> Nr. <Nr>" (eindeutig; die
#    Geschäftsnummer ist es nicht, z.B. MKGE 13 Nr. 5 und 6 = beide 795).
#  - Der Spider lädt jedes PDF selbst (Fusszeile lesen). Damit die FilesPipeline
#    es nicht ein zweites Mal holt, legt er die Bytes in self.pdf_cache ab; die
#    PdfCacheMiddleware (unten, nur für diesen Spider aktiv) beantwortet den
#    Pipeline-Request daraus.
#  - Sammel-PDFs eines Bandes, zu dem es keine Einzel-PDFs gibt (Band 14),
#    werden seitengenau in Einzelentscheide zerlegt (pypdf, nur ganze Seiten).
#    Jede Entscheidseite trägt die Kolumne "Nr. N"; Entscheid N reicht von der
#    ersten Seite mit "Nr. N" bis vor die erste Seite mit "Nr. N+1". Die
#    PDFUrl der Teile ist die Sammel-PDF-URL mit eindeutigem Query und
#    Seitensprung ("...pdf?mkge=14-5#page=40"); der Server ignoriert den Query.


class PdfCacheMiddleware:
	""" Downloader-Middleware: liefert PDFs, die der Spider bereits geladen bzw.
	aus einem Sammel-PDF erzeugt hat, aus spider.pdf_cache statt erneut herunter.
	Schlüssel ist die URL ohne Fragment. """

	def process_request(self, request, spider):
		cache = getattr(spider, 'pdf_cache', None)
		if not cache:
			return None
		key = urldefrag(request.url)[0]
		body = cache.get(key)
		if body is None:
			return None
		logger.info(f"PDF aus Cache geliefert ({len(body)} Bytes): {key}")
		return Response(url=request.url, status=200, body=body,
			headers={'Content-Type': 'application/pdf'}, request=request)


def seitentexte(data):
	""" Text pro Seite (ein pdfminer-Durchlauf); Textboxen durch Leerzeile getrennt
	wie bei extract_text. """
	from pdfminer.high_level import extract_pages
	from pdfminer.layout import LTTextContainer
	texte = []
	for seite in extract_pages(BytesIO(data)):
		texte.append("\n".join(el.get_text() for el in seite if isinstance(el, LTTextContainer)))
	return texte


class CH_MKG(BasisSpider):
	name = 'CH_MKG'

	HOST = 'https://www.oa.admin.ch'
	URLS = ['/de/urteile-militarkassationsgericht']

	# "MKGE 16 Nr. 15" — Einzelentscheid
	reNum = re.compile(r'MKGE\s+(?P<Band>\d+)\s+Nr\.\s+0?(?P<Nr>\d+)\b')
	# Band-Sammel-PDFs ("MKGE Band 16 Nr. 1-16") und Regesten-PDFs überspringen
	reSammel = re.compile(r'Regeste|Band|N[°o]?\s*\d+\s*-\s*\d+|Nrn?\.\s*\d+\s*-\s*\d+|ATM|STMC', re.IGNORECASE)
	# Sammel-PDF mit Entscheiden eines Bandes ("Entscheide MKG Band 14 (2014-2021)",
	# "MKGE Band 16 Nr. 1-16"); Register und Regesten nicht
	reBand = re.compile(r'^(?:Entscheide\s+MKG|MKGE)\s+Band\s+(?P<Band>\d+)\b(?!.*(?:Regest|Register))', re.IGNORECASE)
	# Upload-/Publikationsdatum am Ende des Linktexts ("... 30. Juni 2025")
	reUpload = re.compile(r'(?P<Datum>\d{1,2}\.\s*[A-Za-zäöüéû]+\s+(?:19|20)\d\d)\s*$')
	# Fusszeile am Entscheidende, s. Kopfkommentar
	reFusszeile = re.compile(r'\(\s*(?:MKG|TMC|Nr\.|N°)?\s*(?P<GN>\d{3}(?:\.\d)?(?:\s*(?:/|et|und|e)\s*\d{3}(?:\.\d)?)*)\s*(?:,|du)\s*(?:arrêt du\s*)?(?P<Datum>\d{1,2}\.?\s*[A-Za-zäöüéû]+\s+(?:19|20)\d\d)\s*,(?P<Parteien>[^()]{0,250})\)')
	# Kolumne "Nr. 5" einer Entscheidseite im Sammel-PDF
	reKolumne = re.compile(r'^\s*Nr\.\s*(?P<Nr>\d+)\s*$', re.MULTILINE)

	MONATE = {
		'de': ['januar', 'februar', 'märz', 'april', 'mai', 'juni', 'juli', 'august', 'september', 'oktober', 'november', 'dezember'],
		'fr': ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'],
		'it': ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre'],
	}
	reParteiSprache = {
		'de': re.compile(r'\b(?:gegen|und|g\.)\s'),
		'fr': re.compile(r'\b(?:contre|et)\s'),
		'it': re.compile(r'\b(?:contro|e)\s'),
	}

	custom_settings = {
		'DOWNLOAD_DELAY': 2,
		'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
		'AUTOTHROTTLE_ENABLED': True,
		'DOWNLOADER_MIDDLEWARES': {
			"scrapy.downloadermiddlewares.redirect.RedirectMiddleware": 600,
			"NeueScraper.middlewares.ProxyAwareRedirectMiddleware": 601,
			"NeueScraper.spiders.CH_MKG.PdfCacheMiddleware": 50,
		},
	}

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab = ab		# wird hier nicht gebraucht (eine Übersichtsseite), aber Muster-konform
		self.neu = neu
		self.seen = set()
		self.pdf_cache = {}
		self.request_gen = [scrapy.Request(url=self.HOST + u, callback=self.parse_trefferliste,
			errback=self.errback_httpbin, dont_filter=True) for u in self.URLS]

	def pdatum_aus_linktext(self, text):
		up = self.reUpload.search(text)
		if up:
			pdatum = self.norm_datum(up.group('Datum'), warning=f"Kein Publikationsdatum in {text[:80]}")
			if pdatum and pdatum != "nodate":
				return pdatum
		return None

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
		baende_einzeln = set()
		sammelbaende = {}
		for a in links:
			text = " ".join(t.strip() for t in a.xpath('.//text()').getall() if t.strip())
			href = a.xpath('./@href').get()
			if not href:
				continue
			m = self.reNum.search(text)
			if not m:
				mb = self.reBand.search(text)
				if mb:
					sammelbaende.setdefault(mb.group('Band'), (response.urljoin(href), self.pdatum_aus_linktext(text)))
					logger.info("Sammel-PDF Band " + mb.group('Band') + " vorgemerkt: " + text[:80])
				else:
					logger.info("Übersprungen (keine Einzelentscheid-Nummer): " + text[:80])
				continue
			if self.reSammel.search(text):
				logger.info("Übersprungen (Sammel-/Regesten-PDF): " + text[:80])
				continue
			num = f"MKGE {m.group('Band')} Nr. {m.group('Nr')}"
			baende_einzeln.add(m.group('Band'))
			if num in self.seen:
				logger.info("Dublette übersprungen: " + num)
				continue
			self.seen.add(num)

			item = {}
			item['Num'] = num
			item['Titel'] = num
			item['PDFUrls'] = [response.urljoin(href)]
			pdatum = self.pdatum_aus_linktext(text)
			if pdatum:
				item['PDatum'] = pdatum
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("", "", item['Num'])
			treffer += 1
			yield scrapy.Request(url=item['PDFUrls'][0], callback=self.parse_einzel_pdf,
				errback=self.errback_einzel_pdf, dont_filter=True, meta={'item': item})
		logger.info(f"{treffer} Einzelentscheide auf {response.url} identifiziert.")

		for band, (url, pdatum) in sammelbaende.items():
			if band in baende_einzeln:
				logger.info(f"Sammel-PDF Band {band} übersprungen (Einzel-PDFs vorhanden).")
				continue
			logger.info(f"Band {band} nur als Sammel-PDF vorhanden -> zerlegen: {url}")
			yield scrapy.Request(url=url, callback=self.parse_sammel_pdf, errback=self.errback_httpbin,
				dont_filter=True, meta={'band': band, 'pdatum': pdatum})

	def fusszeile_auswerten(self, item, text):
		""" Setzt Num2, EDatum, Sprache aus der letzten Fusszeile des Entscheidtexts.
		Ohne Fusszeile bleibt es bei PDatum (Warnung). """
		flach = re.sub(r'\s+', ' ', text)
		treffer = list(self.reFusszeile.finditer(flach))
		if not treffer:
			logger.warning(f"{item['Num']}: keine Fusszeile (Geschäftsnummer/Datum) gefunden, nur PDatum.")
			return
		m = treffer[-1]
		gn = re.sub(r'\s*(?:/|\bet\b|\bund\b|\be\b)\s*', '/', m.group('GN')).replace(' ', '')
		item['Num2'] = "MKG " + gn
		datum = m.group('Datum')
		monat = re.search(r'[A-Za-zäöüéû]+', datum).group(0)
		monat_kl = monat.lower()
		# norm_datum kennt die Monatsnamen in Kleinschreibung (fr/it) bzw. Grossschreibung (de)
		if monat_kl not in self.MONATE['de']:
			datum = datum.replace(monat, monat_kl)
		edatum = self.norm_datum(datum, warning=f"{item['Num']}: Fusszeilendatum {datum} ")
		if edatum and edatum != "nodate":
			item['EDatum'] = edatum
		sprachen = [s for s, mon in self.MONATE.items() if monat_kl in mon]
		if len(sprachen) > 1:
			nach_partei = [s for s in sprachen if self.reParteiSprache[s].search(m.group('Parteien') + " ")]
			if len(nach_partei) == 1:
				sprachen = nach_partei
			elif re.search(r'\bdu\b|arrêt', m.group(0)):
				sprachen = ['fr']
		if len(sprachen) == 1:
			item['Sprache'] = sprachen[0]
		logger.info(f"{item['Num']}: Fusszeile '{m.group(0)[:80]}' -> {item.get('Num2')}, {item.get('EDatum')}, {item.get('Sprache')}")

	def titel_auswerten(self, item, text, nr):
		""" Titel = erster Absatz nach dem Absatz, der nur die Entscheidnummer enthält
		(Regestentitel). Fallback: Num. """
		absaetze = [re.sub(r'\s+', ' ', a).strip() for a in re.split(r'\n\s*\n', text)]
		for i, a in enumerate(absaetze[:-1]):
			if a.replace(' ', '') == str(nr) or re.fullmatch(r'Nr\.\s*' + str(nr) + r'\s+' + str(nr), a):
				titel = absaetze[i + 1]
				if 10 <= len(titel) <= 400:
					item['Titel'] = titel
				return

	def item_fertig(self, item, text, nr, body):
		self.fusszeile_auswerten(item, text)
		self.titel_auswerten(item, text, nr)
		self.pdf_cache[urldefrag(item['PDFUrls'][0])[0]] = body
		logger.info("Item gelesen: " + json.dumps(item, ensure_ascii=False))
		if self.check_blockliste(item):
			return item
		return None

	def parse_einzel_pdf(self, response):
		item = response.meta['item']
		if response.status != 200 or response.body[:5] != b'%PDF-':
			logger.error(f"{item['Num']}: PDF nicht geladen (Status {response.status}) {response.url}")
			return
		try:
			text = "\n\n".join(seitentexte(response.body))
		except Exception as e:
			logger.warning(f"{item['Num']}: PDF-Text nicht lesbar ({e!r}), nur PDatum.")
			text = ""
		nr = item['Num'].rpartition(' ')[2]
		ergebnis = self.item_fertig(item, text, nr, response.body)
		if ergebnis:
			yield ergebnis

	def errback_einzel_pdf(self, failure):
		# PDF-Abruf im Spider gescheitert: Item trotzdem ausgeben, die Pipeline
		# versucht den Download dann selbst (ohne Fusszeilen-Daten).
		item = failure.request.meta['item']
		logger.warning(f"{item['Num']}: PDF-Abruf im Spider fehlgeschlagen ({failure.value!r}), Item ohne Fusszeilen-Daten.")
		if self.check_blockliste(item):
			yield item

	def parse_sammel_pdf(self, response):
		band = response.meta['band']
		if response.status != 200 or response.body[:5] != b'%PDF-':
			logger.error(f"Sammel-PDF Band {band} nicht geladen (Status {response.status}) {response.url}")
			return
		from pypdf import PdfReader, PdfWriter
		data = response.body
		texte = seitentexte(data)
		reader = PdfReader(BytesIO(data))
		if len(reader.pages) != len(texte):
			logger.error(f"Sammel-PDF Band {band}: pypdf {len(reader.pages)} Seiten, pdfminer {len(texte)} Seiten -> nicht zerlegt.")
			return

		# Seiten pro Entscheidnummer anhand der Kolumne "Nr. N"
		erste, letzte = {}, {}
		for i, t in enumerate(texte):
			k = self.reKolumne.search(t)
			if k:
				nr = int(k.group('Nr'))
				erste.setdefault(nr, i)
				letzte[nr] = i
		nummern = sorted(erste)
		if not nummern or nummern != list(range(1, len(nummern) + 1)):
			logger.error(f"Sammel-PDF Band {band}: Entscheidnummern nicht lückenlos ({nummern}) -> nicht zerlegt.")
			return
		for a, b in zip(nummern, nummern[1:]):
			if not (letzte[a] < erste[b]):
				logger.error(f"Sammel-PDF Band {band}: Seiten von Nr. {a} und Nr. {b} überlappen -> nicht zerlegt.")
				return
		mangabe = re.search(r'enthält\s+(\d+)\s+Entscheid', " ".join(texte[:12]))
		if mangabe and int(mangabe.group(1)) != len(nummern):
			logger.warning(f"Sammel-PDF Band {band}: laut Vorwort {mangabe.group(1)} Entscheide, gefunden {len(nummern)}.")
		logger.info(f"Sammel-PDF Band {band}: {len(nummern)} Entscheide erkannt.")

		basis_url = urldefrag(response.url)[0]
		for idx, nr in enumerate(nummern):
			von = erste[nr]
			bis = erste[nummern[idx + 1]] - 1 if idx + 1 < len(nummern) else letzte[nr]
			writer = PdfWriter()
			for s in range(von, bis + 1):
				writer.add_page(reader.pages[s])
			puffer = BytesIO()
			writer.write(puffer)
			num = f"MKGE {band} Nr. {nr}"
			if num in self.seen:
				logger.info("Dublette übersprungen: " + num)
				continue
			self.seen.add(num)
			item = {}
			item['Num'] = num
			item['Titel'] = num
			trenner = '&' if '?' in basis_url else '?'
			item['PDFUrls'] = [f"{basis_url}{trenner}mkge={band}-{nr}#page={von + 1}"]
			if response.meta.get('pdatum'):
				item['PDatum'] = response.meta['pdatum']
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("", "", item['Num'])
			logger.info(f"{num}: Seiten {von + 1}-{bis + 1} von Band {band}, {len(puffer.getvalue())} Bytes")
			ergebnis = self.item_fertig(item, "\n\n".join(texte[von:bis + 1]), nr, puffer.getvalue())
			if ergebnis:
				yield ergebnis
