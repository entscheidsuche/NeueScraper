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
# Quelle: offizielles HUDOC-Query-API (JSON), getestet 07/2026:
#   respondent:"CHE" (alle Typen)                -> 3'148 Dokumente
#   Volltext-HTML:  /app/conversion/docx/html/body?library=ECHR&id=<itemid>
#   Volltext-PDF:   /app/conversion/docx/pdf?library=ECHR&id=<itemid>&filename=...
#
# Vor Produktivbetrieb:
#  1. Gerichtsliste (Excel/CSV) braucht neue Zeilen; das Kammer-Matching läuft
#     über die vkammer-Marker, die dieser Spider an detect() übergibt.
#     Marker -> empfohlene Signatur/Kammer-Label (de/fr):
#       #EGMR_GK#          CH_EGMR_001  Grosse Kammer / Grande Chambre
#       #EGMR_SEC1#        CH_EGMR_002  I. Sektion / Première section
#       #EGMR_SEC2#        CH_EGMR_003  II. Sektion / Deuxième section
#       #EGMR_SEC3#        CH_EGMR_004  III. Sektion / Troisième section
#       #EGMR_SEC4#        CH_EGMR_005  IV. Sektion / Quatrième section
#       #EGMR_SEC5#        CH_EGMR_006  V. Sektion / Cinquième section
#       #EGMR_KOMITEE#     CH_EGMR_007  Komitee / Comité
#       #EGMR_ALTKAMMER#   CH_EGMR_008  Kammer (altes Gericht, vor 1998) / Chambre
#       #EGMR_PLENUM#      CH_EGMR_009  Plenum (altes Gericht) / Cour plénière
#       #EGMR_KOMMISSION#  CH_EGMR_010  Kommission (EKMR) / Commission
#     Urteil vs. Zulässigkeitsentscheid steckt im Feld 'Entscheidart'.
#     Grundlage: originatingbody-Codes, empirisch über alle 1'403 CHE-Dokumente
#     erhoben und am Volltextkopf verifiziert (07/2026):
#       8=GK | 4,5,6,7,23=Sektion I,II,III,IV,V | 25,26,27,29=Komitees
#       9=Court(Chamber) alt | 15=Court(Plenary) alt
#       1,2,3,17,21,leer=Kommission
#  2. Sprachfassungen: FRE und ENG werden BEIDE als eigenständige Dokumente
#     übernommen (kein Dedup — der Textumfang der Fassungen differiert).
#     Pfadkollisionen verhindert forceID (enthält Sprachsuffix); die
#     Fassungen verlinken sich gegenseitig über die gemeinsamen Nummern.
#  3. Verlinkung (numliste-Mechanik wie BGer<->BGE):
#       Num  = "YYYYMMDD_appno" mit '_' statt '/' — EXAKT das Num[0]-Format
#              von CH_BGE_012 (BGer-EGMR-Regesten). Dadurch verlinken sich
#              HUDOC-Volltext und BGer-Regeste automatisch.
#       Num2 = Fallname (docname) — entspricht Num[1] von CH_BGE_012.
#       Num3 = Requête-Nummer pur ("24404/05") — verbindet die beiden
#              Sprachfassungen untereinander und dient der Zitatsuche.
#  4. doctype-Filter: HFJUD/HEJUD (Urteile) + HFDEC/HEDEC (Entscheide).
#     Communicated Cases, Legal Summaries, Resolutionen etc. bleiben draussen.


class CH_EGMR(BasisSpider):
	name = 'CH_EGMR'

	HOST = 'https://hudoc.echr.coe.int'
	QUERY_BASIS = ('contentsitename:ECHR AND (respondent:"CHE") AND '
		'(doctype:"HFJUD" OR doctype:"HEJUD" OR doctype:"HFDEC" OR doctype:"HEDEC")')
	SELECT = ('itemid,appno,docname,doctype,importance,originatingbody,'
		'judgementdate,decisiondate,languageisocode,conclusion')
	SUCH_URL = '/app/query/results?query={query}&select={select}&sort={sort}&start={start}&length={length}'
	HTML_URL = '/app/conversion/docx/html/body?library=ECHR&id={itemid}'
	PDF_URL = '/app/conversion/docx/pdf?library=ECHR&id={itemid}&filename={filename}'
	TREFFER_PRO_SEITE = 500
	# Beide Sprachfassungen werden vollständig gescrapt (eigene Dokumente).
	SPRACHEN = ['FRE', 'ENG']
	SPRACHCODE = {'FRE': 'fr', 'ENG': 'en'}

	# HUDOC-Datumsformat: "29/07/2010 00:00:00"
	reDatum = re.compile(r'^(?P<Tag>\d{1,2})/(?P<Monat>\d{1,2})/(?P<Jahr>(?:19|20)\d\d)')

	# originatingbody-Code -> Kammer-Marker fürs Gerichtsliste-Matching.
	# Empirisch erhoben über den gesamten CHE-Bestand, siehe Kopfkommentar.
	ORIGINATINGBODY_MARKER = {
		'8': 'GK',
		'4': 'SEC1', '5': 'SEC2', '6': 'SEC3', '7': 'SEC4', '23': 'SEC5',
		'25': 'KOMITEE', '26': 'KOMITEE', '27': 'KOMITEE', '29': 'KOMITEE',
		'9': 'ALTKAMMER',
		'15': 'PLENUM',
		'1': 'KOMMISSION', '2': 'KOMMISSION', '3': 'KOMMISSION',
		'17': 'KOMMISSION', '21': 'KOMMISSION',
		# leerer Code kommt bei 13 alten Kommissions-Dokumenten vor (verifiziert)
		'': 'KOMMISSION',
	}

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
		self.request_gen = [self.mache_request(sprache_index=0, start=0)]

	def mache_request(self, sprache_index, start):
		sprache = self.SPRACHEN[sprache_index]
		query = self.QUERY_BASIS + ' AND (languageisocode:"' + sprache + '")'
		if self.ab:
			# kpdate = massgebliches Datum (Urteil bzw. Entscheid) im HUDOC-Index
			query += ' AND (kpdate>="' + self.ab + 'T00:00:00.0Z")'
		url = self.HOST + self.SUCH_URL.format(
			query=quote(query, safe=''),
			select=self.SELECT,
			sort=quote('itemid Ascending', safe=''),
			start=start,
			length=self.TREFFER_PRO_SEITE)
		logger.info(f"HUDOC-Request Sprache={sprache} start={start}: {url}")
		return scrapy.Request(url=url, callback=self.parse_trefferliste, errback=self.errback_httpbin,
			meta={'sprache_index': sprache_index, 'start': start}, dont_filter=True)

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status " + str(response.status))
		logger.info("parse_trefferliste Rohergebnis " + str(len(response.body)) + " Zeichen")
		logger.info("parse_trefferliste Rohergebnis: " + response.text[:5000])

		sprache_index = response.meta['sprache_index']
		start = response.meta['start']
		resultdict = json.loads(response.text)
		treffer = resultdict.get('resultcount', 0)
		entscheide = resultdict.get('results') or []
		logger.info(f"Sprache {self.SPRACHEN[sprache_index]}: insgesamt {treffer} Treffer, "
			f"start={start}, auf dieser Seite {len(entscheide)}")
		if treffer == 0:
			logger.warning("kein Treffer")

		for entscheid in entscheide:
			cols = entscheid.get('columns') or {}
			item = {}
			itemid = PH.NC(cols.get('itemid'), error=f"keine itemid in {json.dumps(cols)}")
			if not itemid:
				continue
			item['DocID'] = itemid

			# Requête-Nummer(n): "24404/05" bzw. "123/06;456/07" -> erste massgeblich
			appno = (cols.get('appno') or '').split(';')[0].strip()
			appno = PH.NC(appno or None, error=f"keine Requête-Nummer in {json.dumps(cols)}")
			if not appno:
				continue

			item['Titel'] = PH.NC(cols.get('docname'), warning=f"kein Titel in {json.dumps(cols)}")

			doctype = cols.get('doctype') or ''
			klasse = 'JUD' if doctype.endswith('JUD') else 'DEC'
			datum_roh = cols.get('judgementdate') or cols.get('decisiondate') or ''
			edatum = None
			d = self.reDatum.match(datum_roh)
			if d:
				edatum = "{}-{:0>2}-{:0>2}".format(d.group('Jahr'), d.group('Monat'), d.group('Tag'))
				item['EDatum'] = edatum
			else:
				logger.warning(f"kein Datum in {json.dumps(cols)}")

			sprache = self.SPRACHCODE[self.SPRACHEN[sprache_index]]
			item['Sprache'] = sprache

			# Verlinkung (siehe Kopfkommentar): Num im CH_BGE_012-Format,
			# Num2 = Fallname, Num3 = Requête-Nummer pur.
			datum_kompakt = edatum.replace('-', '') if edatum else 'nodate'
			item['Num'] = datum_kompakt + '_' + appno.replace('/', '_')
			if item['Titel']:
				item['Num2'] = item['Titel']
			item['Num3'] = appno

			# Pfad: Sprachsuffix in der forceID, damit FRE- und ENG-Fassung
			# nicht kollidieren (Num+EDatum wären identisch).
			item['forceID'] = (datum_kompakt + '-' + appno.replace('/', '-')
				+ '-' + sprache + '_' + (edatum or 'nodate'))

			if cols.get('conclusion'):
				item['Leitsatz'] = cols['conclusion']
			item['HTMLUrls'] = [self.HOST + self.HTML_URL.format(itemid=itemid)]
			item['PDFUrls'] = [self.HOST + self.PDF_URL.format(itemid=itemid,
				filename=quote(appno.replace('/', '-') + '-' + sprache + '.pdf'))]

			# Spruchkörper: originatingbody-Code -> Marker -> Matching über die
			# Gerichtsliste (Excel-Sheet), analog VD_Omni ('#CDAP#' etc.).
			ob = str(cols.get('originatingbody') or '').strip()
			marker = self.ORIGINATINGBODY_MARKER.get(ob)
			if marker is None:
				logger.warning(f"Unbekannter originatingbody-Code {ob!r} bei {itemid} "
					f"({item['Titel']}) — Kammerfallback greift.")
				marker = 'UNBEKANNT'
			item['Entscheidart'] = 'Urteil' if klasse == 'JUD' else 'Entscheid'
			item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(
				"", "#EGMR_" + marker + "#", item['Num'])
			logger.info("Item gelesen: " + json.dumps(item))
			if self.check_blockliste(item):
				yield item

		# Pagination: erst alle Seiten der aktuellen Sprache, dann nächste Sprache.
		naechster_start = start + self.TREFFER_PRO_SEITE
		if naechster_start < treffer:
			yield self.mache_request(sprache_index, naechster_start)
		elif sprache_index + 1 < len(self.SPRACHEN):
			yield self.mache_request(sprache_index + 1, 0)
		else:
			logger.info("Alle Sprachen abgearbeitet.")
