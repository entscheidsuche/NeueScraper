# -*- coding: utf-8 -*-
import scrapy
import re
import logging
import json
from urllib.parse import quote
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

# ENTWURF (Claude, 2026-07-07) — EGMR-Rechtsprechung in Sachen Schweiz aus HUDOC.
#
# Quelle: offizielles HUDOC-Query-API (JSON) + Conversion-Endpoint für die
# Volltexte. Getestet 07/2026: respondent:"CHE", Urteile+Entscheide
# = 1'403 Records für ~1'027 Fälle.
#
# Sprachmodell (Vorgabe Jörn, 07/2026):
#  - HUDOC führt pro Sprachfassung einen eigenen Record (eigene itemid).
#    Bei URTEILEN existieren stets FRE- UND ENG-Record; hat eine Fassung
#    keinen Volltext, ist ihr Record ein Metadaten-Platzhalter und im
#    Feld isplaceholder="True" markiert (Conversion antwortet dort 204).
#    Bei ENTSCHEIDEN gibt es Records nur mit Volltext. Empirie CHE:
#    230 Fälle mit zwei echten Volltexten, Rest einsprachig.
#  - Ablageregel (ein Dokument pro Fall, keine Doppelablage):
#      a) französischer Volltext vorhanden        -> französisch ablegen
#      b) nur englischer Volltext vorhanden       -> englisch ablegen
#    Metadaten (Titel, Leitsatz) wenn immer möglich aus dem französischen
#    Record (auch wenn er nur Platzhalter ist). Gibt es nur eine
#    Metadaten-Fassung, gilt sie für alle Oberflächensprachen.
#  - Der Sprachfilter der Oberfläche kennt aktuell kein Englisch; die
#    en-Dokumente laufen dort mit, bis der Filter erweitert ist.
#  - PDFs werden NICHT übernommen: Es sind serverseitige Konvertate aus
#    dem Word-Original (kein eigenständiges Original-PDF).
#
# Kammer-Matching über detect() aus der Basis (inkl. Kammerfallback).
# Der Spider enthält KEIN Mapping: Er reicht den originatingbody-Code der
# Quelle unverändert als vkammer-Marker "#EGMR_<code>#" durch (leerer Code
# als 0). Die Zuordnung Code -> Kammer/Signatur/Label erfolgt ausschliesslich
# in der Gerichtsliste (Excel); neue Codes laufen bis zur Excel-Ergänzung in
# den Kammerfallback — ohne Python-Änderung.
# Zur Doku fürs Excel — im CHE-Bestand aktuell vorhandene Codes, empirisch
# erhoben und am Volltextkopf verifiziert (Stand 07/2026):
#   8=Grosse Kammer | 4,5,6,7,23=Sektion I,II,III,IV,V
#   25,26,27,29=Komitees | 9=Court(Chamber) alt | 15=Court(Plenary) alt
#   1,2,3,17,21 und leer(=0)=Kommission
#
# Verlinkung: Num = Requête-Nummer pur ("24404/05") — Anker für die
# ES-seitige Verknüpfung mit den BGer-Zusammenfassungen (EGMR via
# Bundesgericht) und für die Zitatsuche. Num2 = Fallname.
# Urteil vs. Zulässigkeitsentscheid steht im Feld 'Entscheidart'.


class CH_EGMR(BasisSpider):
	name = 'CH_EGMR'

	HOST = 'https://hudoc.echr.coe.int'
	QUERY_BASIS = ('contentsitename:ECHR AND (respondent:"CHE") AND '
		'(doctype:"HFJUD" OR doctype:"HEJUD" OR doctype:"HFDEC" OR doctype:"HEDEC")')
	SELECT = ('itemid,appno,docname,doctype,importance,originatingbody,'
		'judgementdate,decisiondate,languageisocode,conclusion,isplaceholder')
	SUCH_URL = '/app/query/results?query={query}&select={select}&sort={sort}&start={start}&length={length}'
	HTML_URL = '/app/conversion/docx/html/body?library=ECHR&id={itemid}'
	TREFFER_PRO_SEITE = 500
	SPRACHCODE = {'FRE': 'fr', 'ENG': 'en'}

	# HUDOC-Datumsformat: "29/07/2010 00:00:00"
	reDatum = re.compile(r'^(?P<Tag>\d{1,2})/(?P<Monat>\d{1,2})/(?P<Jahr>(?:19|20)\d\d)')

	custom_settings = {
		'DOWNLOAD_DELAY': 1.0,
		'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
		'AUTOTHROTTLE_ENABLED': True,
		'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
	}

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab = ab		# optional YYYY-MM-DD: nur Dokumente ab diesem (Urteils-)Datum
		self.neu = neu
		# (Requête-Nr., Datum, Klasse) -> {'fr': cols, 'en': cols}
		self.faelle = {}
		self.request_gen = [self.mache_request(start=0)]

	def mache_request(self, start):
		# EIN Durchlauf über beide Sprachen: languageisocode kommt als Spalte
		# mit, die Auswahl der Fassung passiert nach der Gruppierung.
		query = self.QUERY_BASIS
		if self.ab:
			# kpdate = massgebliches Datum (Urteil bzw. Entscheid) im HUDOC-Index
			query += ' AND (kpdate>="' + self.ab + 'T00:00:00.0Z")'
		url = self.HOST + self.SUCH_URL.format(
			query=quote(query, safe=''),
			select=self.SELECT,
			sort=quote('itemid Ascending', safe=''),
			start=start,
			length=self.TREFFER_PRO_SEITE)
		logger.info(f"HUDOC-Request start={start}: {url}")
		return scrapy.Request(url=url, callback=self.parse_trefferliste, errback=self.errback_httpbin,
			meta={'start': start}, dont_filter=True)

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status " + str(response.status))
		logger.info("parse_trefferliste Rohergebnis " + str(len(response.body)) + " Zeichen")

		start = response.meta['start']
		resultdict = json.loads(response.text)
		treffer = resultdict.get('resultcount', 0)
		entscheide = resultdict.get('results') or []
		logger.info(f"Insgesamt {treffer} Records, start={start}, auf dieser Seite {len(entscheide)}")
		if treffer == 0:
			logger.warning("kein Treffer")

		for entscheid in entscheide:
			cols = entscheid.get('columns') or {}
			if not cols.get('itemid'):
				PH.NC(None, error=f"keine itemid in {json.dumps(cols)}")
				continue
			sprache = self.SPRACHCODE.get(cols.get('languageisocode'))
			if not sprache:
				logger.warning(f"Unerwartete Sprache {cols.get('languageisocode')!r} "
					f"bei {cols.get('itemid')} — Record übersprungen.")
				continue
			appno = (cols.get('appno') or '').split(';')[0].strip()
			if not appno:
				PH.NC(None, error=f"keine Requête-Nummer in {json.dumps(cols)}")
				continue
			doctype = cols.get('doctype') or ''
			klasse = 'JUD' if doctype.endswith('JUD') else 'DEC'
			datum_roh = cols.get('judgementdate') or cols.get('decisiondate') or ''
			d = self.reDatum.match(datum_roh)
			edatum = None
			if d:
				edatum = "{}-{:0>2}-{:0>2}".format(d.group('Jahr'), d.group('Monat'), d.group('Tag'))
			else:
				logger.warning(f"kein Datum in {json.dumps(cols)}")
			key = (appno, edatum, klasse)
			self.faelle.setdefault(key, {})[sprache] = cols

		naechster_start = start + self.TREFFER_PRO_SEITE
		if naechster_start < treffer:
			yield self.mache_request(naechster_start)
		else:
			logger.info(f"Records gesammelt: {len(self.faelle)} Fälle, beginne Dokumentabruf.")
			for request in self.verarbeite_faelle():
				yield request

	def hat_volltext(self, cols):
		return cols is not None and cols.get('isplaceholder') != 'True'

	def verarbeite_faelle(self):
		for (appno, edatum, klasse), records in self.faelle.items():
			fr = records.get('fr')
			en = records.get('en')
			meta_rec = fr if fr else en		# Metadaten wenn möglich französisch

			# Ablageregel: a) fr-Volltext -> fr; b) sonst en-Volltext -> en
			if self.hat_volltext(fr):
				sprache, dok = 'fr', fr
			elif self.hat_volltext(en):
				sprache, dok = 'en', en
			else:
				logger.error(f"Kein Volltext in keiner Sprachfassung für {appno} "
					f"({meta_rec.get('docname')}) — Fall wird verworfen.")
				continue
			# Weitere vorhandene Volltext-Fassungen (wie die HUDOC-Oberfläche
			# sie anzeigt) — werden als Vermerk mit Deeplink ins Dokument
			# übernommen. Nach der Ablageregel betrifft das nur den Fall
			# fr abgelegt + en vorhanden.
			weitere = []
			if sprache == 'fr' and self.hat_volltext(en):
				weitere.append(('Version anglaise', en['itemid']))

			item = {}
			item['Num'] = appno
			if edatum:
				item['EDatum'] = edatum
			item['Titel'] = PH.NC(meta_rec.get('docname'),
				warning=f"kein Titel für {appno} in {json.dumps(meta_rec)}")
			if item['Titel']:
				item['Num2'] = item['Titel']
			if meta_rec.get('conclusion'):
				item['Leitsatz'] = meta_rec['conclusion']
			item['Entscheidart'] = 'Urteil' if klasse == 'JUD' else 'Entscheid'
			item['Sprache'] = sprache

			ob = str(meta_rec.get('originatingbody') or '').strip() or '0'
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(
				"", "#EGMR_" + ob + "#", item['Num'])
			if not self.check_blockliste(item):
				continue

			url = self.HOST + self.HTML_URL.format(itemid=dok['itemid'])
			yield scrapy.Request(url=url, callback=self.parse_document,
				errback=self.errback_httpbin, dont_filter=True,
				meta={'item': item, 'weitere': weitere, 'handle_httpstatus_list': [204]})

	def parse_document(self, response):
		item = response.meta['item']
		antwort = response.text if response.body else ''
		logger.info(f"parse_document status {response.status}, {len(antwort)} Zeichen "
			f"für {item['Num']} ({item['Sprache']})")
		if response.status == 204 or not antwort.strip():
			# Sollte dank isplaceholder-Auswertung nicht vorkommen —
			# Sicherheitsnetz, falls die Quelle inkonsistent ist.
			logger.error(f"Unerwartet kein Volltext für {item['Num']} "
				f"({item.get('Titel')}, {response.url}) — Fall wird verworfen.")
			return
		# Vermerk auf weitere Sprachfassungen (mit HUDOC-Deeplink) anhängen,
		# analog zur Anzeige in der HUDOC-Oberfläche.
		weitere = response.meta.get('weitere') or []
		if weitere:
			vermerke = " &middot; ".join(
				f'{label}: <a href="{self.HOST}/eng?i={itemid}">HUDOC {itemid}</a>'
				for label, itemid in weitere)
			antwort += ('\n<hr/><p class="sprachfassungen"><i>Autre version '
				'linguistique disponible &mdash; ' + vermerke + '</i></p>\n')
		item['HTMLUrls'] = [response.url]
		PH.write_html(antwort, item, self)
		yield item
