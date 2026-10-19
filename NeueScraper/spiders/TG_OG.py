# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
import html
from scrapy.exceptions import CloseSpider
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)


class TG_OG(BasisSpider):
	name = 'TG_OG'

	# Seit dem Umbau von rechtsprechung.tg.ch (Sommer 2026, Scroll Sites) liefert jede
	# Sektion einen vollständigen Seitenbaum als JSON. Darin:
	#   Wurzelknoten '/og/entscheide' bzw. '/vg/entscheide'
	#     -> Jahrgänge ('RBOG 2025', 'TVR 2025')
	#        -> Entscheide ('RBOG 2025 Nr. 01', 'TVR 2025 Nr. 1')
	# Andere Wurzelknoten (Gesetzesregister, "zur Publikation vorgesehen", Entscheide für
	# Medienschaffende) werden bewusst nicht gescrapt.
	HOST = "https://rechtsprechung.tg.ch"
	SEKTIONEN = {
		'Obergericht': {'baum': '/og/__pagetree.json', 'wurzel': '/og/entscheide'},
		'Verwaltungsgericht': {'baum': '/vg/__pagetree.json', 'wurzel': '/vg/entscheide'},
	}

	# Metazeile Obergericht, z.B.
	#   "Obergericht, 2. Abteilung, 4. Dezember 2025, ZBS.2025.18"
	#   "Obergericht, 1. Abteilung, 10. Juli 2024 / 18. März 2025, SBR.2024.20"
	#   "Obergericht, 2. Abteilung, 10. / 22. Dezember 2020, BR.2020.53"
	#   "Rekurskommission, 24. August 1998, ZR 98 73/74/75"
	#   "Präsident des Obergerichts, 24. Februar 2000, BR.1999.141"
	# Kammer = Teile vor dem (ersten) Datum, Datum = letztes Datum, Num = Rest danach.
	reMetaOG = re.compile(r'^(?:Obergericht|Rekurskommiss?ion|Obergerichtspräsidium|Präsident(?:in)? des Obergerichts?)[,.]\s+(?P<Rest>.*)$')
	# Metazeile Verwaltungsgericht/Rekurskommissionen, z.B.
	#   "Entscheid des Verwaltungsgerichts VG.2023.2/E vom 24. April 2024"
	#   "Zwischenentscheid des Verwaltungsgerichts als Versicherungsgericht VV.2018.328/Z vom 30. Oktober 2019"
	#   "Entscheid der Steuerrekurskommission STRE.2023.117 und STRE.2023.118 vom 28. Mai 2024"
	#   "Entscheid der Rekurskommission für Strassenverkehrssachen Nr. 72/14 vom 22. August / 18. September 2014"
	#   "VG.2020.115/E vom 10. Februar 2021", "Entscheid vom 9. Mai 2001"
	# Num = Text zwischen Behörde und "vom" (sofern mit Ziffer), Datum = letztes Datum danach.
	reMetaVG = re.compile(r'^(?:(?:\([^)]*\))?(?:[Zz]wischen|[Tt]eil|Einzelrichter)?[Ee]ntscheide?(?P<Behoerde>(?:\s+(?!vom\b)[^\s\d§]+)*?)\s+|(?=[A-Z][A-Za-z]{1,4}\.(?:19|20)\d\d\.))(?:(?P<Num>(?!vom\b)\S*\d.*?)\s+)?vom\b,?\s*(?P<Rest>.*)$')
	reDatum = re.compile(r'\d{1,2}\.\s*(?:' + "|".join(BasisSpider.MONATEde) + r')\s+(?:19|20)\d\d')
	reDatumBeginn = re.compile(r'^\d{1,2}\.\s*(?:/|' + "|".join(BasisSpider.MONATEde) + r')')
	reFussnote = re.compile(r'^\[\d+\]')
	reZeilenende = re.compile(r'<br\s*/?>|<hr[^>]*>|</?(?:p|li|ol|ul|div|h\d|table|tr|td|th|section)\b[^>]*>', re.I)
	reTags = re.compile(r'<[^>]+>')
	reSpaces = re.compile(r'\s+')
	reAltPfad = re.compile(r'^TG_OG/TG_OG_001_(?P<Num>.+)_(?P<Datum>[0-9-]+|nodate)\.html$')
	filenamechars = re.compile("[^-a-zA-Z0-9]")

	def __init__(self, neu=None):
		super().__init__()
		self.neu = neu
		self.alt_datum = None
		self.request_gen = self.get_requests()

	def get_requests(self):
		requests = []
		for gericht, sektion in self.SEKTIONEN.items():
			requests.append(scrapy.Request(url=self.HOST + sektion['baum'], callback=self.parse_seitenbaum, errback=self.errback_httpbin, meta={'Gericht': gericht}))
		return requests

	def get_alt_datum(self, num):
		# Bisherige Dokument-IDs haben je nach Jahrgang nur die Jahreszahl oder ein
		# (teils heuristisch ermitteltes) Datum als Datumsteil. Damit bereits bekannte
		# Entscheide ihre ID behalten, wird der Datumsteil aus den Alt-Scrapedaten
		# übernommen. Neue Entscheide erhalten das Datum aus der Metazeile.
		if self.alt_datum is None:
			self.alt_datum = {}
			for pfad, eintrag in self.alt_scrape.items():
				if eintrag.get('status') == 'nicht_mehr_da':
					continue
				match = self.reAltPfad.match(pfad)
				if match:
					self.alt_datum[match.group('Num')] = match.group('Datum')
			logger.info("Datumsteile bisheriger Dokument-IDs: " + str(len(self.alt_datum)))
			if not self.alt_datum and self.neu != 'neu':
				# Ohne Alt-Daten würden alle Entscheide unter neuen IDs abgelegt (Dubletten).
				self.fehler += 1
				logger.error("Keine Alt-Scrapedaten für TG_OG -> Abbruch, um Dubletten zu vermeiden. Für einen Neuaufbau mit -a neu=neu starten.")
				raise CloseSpider('keine_altdaten')
		return self.alt_datum.get(self.filenamechars.sub('-', num)[:20])

	def parse_seitenbaum(self, response):
		gericht = response.meta['Gericht']
		wurzelpfad = self.SEKTIONEN[gericht]['wurzel']
		logger.info("parse_seitenbaum " + gericht + " response.status " + str(response.status))
		try:
			baum = json.loads(response.text)
		except ValueError as ex:
			self.fehler += 1
			logger.error("Seitenbaum für " + gericht + " nicht lesbar: " + repr(ex) + " Rohergebnis: " + response.text[:2000])
			return

		wurzel = [k for k in baum if k.get('path') == wurzelpfad]
		if not wurzel:
			self.fehler += 1
			logger.error("Wurzelknoten " + wurzelpfad + " nicht im Seitenbaum gefunden. Vorhandene Knoten: " + json.dumps([(k.get('title'), k.get('path')) for k in baum]))
			return

		jahre = wurzel[0].get('children') or []
		anzahl = 0
		for jahr in jahre:
			for entscheid in jahr.get('children') or []:
				anzahl += 1
				item = {}
				item['Num'] = self.reSpaces.sub(' ', entscheid['title']).strip()
				item['HTMLUrls'] = [self.HOST + entscheid['path']]
				item['VGericht'] = gericht
				request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
				yield request
		logger.info("Für " + gericht + ": " + str(len(jahre)) + " Jahrgänge mit " + str(anzahl) + " Entscheiden gefunden.")
		if anzahl == 0:
			# Seitenstruktur hat sich vermutlich geändert: nicht still mit 0 Dokumenten enden.
			self.fehler += 1
			logger.error("Für " + gericht + " keine Entscheide im Seitenbaum gefunden: " + json.dumps(wurzel[0])[:2000])

	def get_zeilen(self, response):
		# Entscheidtext zeilenweise: Die Metazeile steht teils in einem eigenen <p>,
		# teils per <br> an den letzten Absatz angehängt (auch innerhalb von <ol><li>).
		body = response.xpath("//section[contains(concat(' ', normalize-space(@class), ' '), ' article-body ')]").get()
		if not body:
			return []
		text = html.unescape(self.reTags.sub('', self.reZeilenende.sub('\n', body)))
		zeilen = [self.reSpaces.sub(' ', z).strip() for z in text.split('\n')]
		return [z for z in zeilen if z]

	def get_meta(self, zeilen, gericht):
		# Liefert (Datum, Geschäftsnummer, Kammer) aus der ersten erkannten Metazeile.
		for zeile in zeilen:
			if len(zeile) > 250 or self.reFussnote.match(zeile):
				continue
			if gericht == "Obergericht":
				match = self.reMetaOG.match(zeile)
				if not match:
					continue
				rest = match.group('Rest')
				daten = list(self.reDatum.finditer(rest))
				if not daten:
					continue
				teile = rest[:daten[0].start()].split(',')
				kammerteile = []
				for teil in teile:
					teil = teil.strip()
					if not teil or self.reDatumBeginn.match(teil):
						break
					kammerteile.append(teil)
				num = rest[daten[-1].end():].strip(' ,.')
				num = re.sub(r'\.\s+(?=\d)', '.', num)
				return daten[-1].group(0), (num if re.search(r'\d', num) else None), (', '.join(kammerteile) or None)
			else:
				match = self.reMetaVG.match(zeile)
				if not match:
					continue
				daten = list(self.reDatum.finditer(match.group('Rest')))
				if not daten:
					continue
				num = match.group('Num')
				return daten[-1].group(0), (num.strip(' ,') if num else None), None
		return None

	def parse_document(self, response):
		logger.debug("parse_document response.status " + str(response.status) + " für " + response.url)
		antwort = response.text
		logger.info("parse_document Rohergebnis " + str(len(antwort)) + " Zeichen")
		item = response.meta['item']

		zeilen = self.get_zeilen(response)
		if not zeilen:
			self.fehler += 1
			logger.error("Kein Entscheidtext (section.article-body) gefunden für " + item['Num'] + " " + response.url)
			return

		item['Leitsatz'] = zeilen[0]

		vkammer = ""
		meta = self.get_meta(zeilen, item['VGericht'])
		if meta:
			datum, num2, kammer = meta
			if num2:
				item['Num2'] = num2
			if kammer:
				item['VKammer'] = kammer
				vkammer = kammer
			edatum = self.norm_datum(datum)
		else:
			logger.warning("Metazeile nicht erkannt in " + item['Num'] + " " + response.url)
			# EDatum notfalls aus der Jahreszahl erstellen.
			edatum = self.norm_datum(item['Num'])

		alt = self.get_alt_datum(item['Num'])
		if alt:
			if alt != edatum:
				logger.info("Übernehme bisherigen Datumsteil " + alt + " statt " + edatum + " für " + item['Num'])
			item['EDatum'] = alt
		else:
			logger.info("Neuer Entscheid " + item['Num'] + " mit Datum " + edatum)
			item['EDatum'] = edatum

		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("", vkammer, item['Num'])
		PH.write_html(antwort, item, self)
		yield item
