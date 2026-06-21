# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
import calendar
import datetime
from scrapy.http.cookies import CookieJar
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)


class LU_Gerichte(BasisSpider):
	name = 'LU_Gerichte'
	HOST = 'https://gerichte.lu.ch'
	START_URL = '/recht_sprechung/lgve'
	TREFFER_PRO_SEITE = 50

	# Default-Startdatum für Vollläufe.
	DEFAULT_AB = '01.01.1990'

	custom_settings = {
		"COOKIES_ENABLED": True,
		"COOKIES_DEBUG": True,
		"AUTOTHROTTLE_ENABLED": False,
		"DOWNLOAD_DELAY": 0.5,
		"RANDOMIZE_DOWNLOAD_DELAY": False,
		# 4 Zeitscheiben parallel → ~8 req/s aggregiert. Bei 503-Welle weiter senken.
		"CONCURRENT_REQUESTS_PER_DOMAIN": 4,
		"CONCURRENT_REQUESTS": 16,
		"RETRY_TIMES": 5,
		"RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
	}

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.ab = ab
		self.neu = neu
		self.request_gen = self._build_initial_requests()

	# ------------------------------------------------------------------
	# Zeitscheiben-Bildung
	# ------------------------------------------------------------------
	def _parse_ab(self):
		"""ab als 'dd.mm.yyyy' parsen.
		Sonderwert 'zuletzt' → heute − 6 Monate.
		None/leer → DEFAULT_AB.
		"""
		if self.ab and self.ab.strip().lower() == "zuletzt":
			heute = datetime.date.today()
			monat = heute.month - 6
			jahr = heute.year
			if monat <= 0:
				monat += 12
				jahr -= 1
			# Tag auf gültiges Monatsende klemmen (29.2., 31.4. usw. abfangen)
			tag = min(heute.day, calendar.monthrange(jahr, monat)[1])
			d = datetime.date(jahr, monat, tag)
			logger.info(f"ab='zuletzt' → {d.strftime('%d.%m.%Y')}")
			return d

		s = self.ab if self.ab else self.DEFAULT_AB
		try:
			return datetime.datetime.strptime(s, "%d.%m.%Y").date()
		except ValueError:
			logger.error(f"ab='{self.ab}' nicht im Format dd.mm.yyyy, falle auf {self.DEFAULT_AB} zurück")
			return datetime.datetime.strptime(self.DEFAULT_AB, "%d.%m.%Y").date()

	def _zeitscheiben(self):
		"""Liefert Liste von (datum_von, datum_bis)-Paaren als 'dd.mm.yyyy'-Strings,
		ein Eintrag pro Kalenderjahr. Erste Scheibe beginnt bei ab, letzte endet heute."""
		ab = self._parse_ab()
		heute = datetime.date.today()
		scheiben = []
		jahr = ab.year
		von = ab
		while jahr <= heute.year:
			bis = datetime.date(jahr, 12, 31) if jahr < heute.year else heute
			scheiben.append((von.strftime("%d.%m.%Y"), bis.strftime("%d.%m.%Y")))
			jahr += 1
			if jahr <= heute.year:
				von = datetime.date(jahr, 1, 1)
		logger.info(f"LU_Gerichte: {len(scheiben)} Zeitscheiben ab {ab.isoformat()}")
		return scheiben

	def _slot_id(self, idx):
		return f"lu_ts_{idx}"

	def _jar_id(self, idx):
		return f"lu_ts_{idx}"

	# ------------------------------------------------------------------
	# Request-Aufbau
	# ------------------------------------------------------------------
	def _build_initial_requests(self):
		"""Pro Zeitscheibe ein GET auf das Suchformular, um ViewState + Cookies zu holen."""
		requests = []
		for idx, (datum_von, datum_bis) in enumerate(self._zeitscheiben()):
			slot = self._slot_id(idx)
			jar = self._jar_id(idx)
			meta = {
				'datum_von': datum_von,
				'datum_bis': datum_bis,
				'cookiejar': jar,
				'download_slot': slot,
				'ts_idx': idx,
			}
			logger.info(f"Zeitscheibe {idx}: {datum_von} bis {datum_bis} (jar={jar}, slot={slot})")
			requests.append(scrapy.Request(
				url=self.HOST + self.START_URL,
				callback=self.parse_form,
				errback=self.errback_httpbin,
				meta=meta,
				dont_filter=True,
			))
		return requests

	def _carry_meta(self, response, extra=None):
		"""Behält cookiejar/download_slot/ts_idx/Datumsbereich der Zeitscheibe bei."""
		base = {
			'datum_von': response.meta['datum_von'],
			'datum_bis': response.meta['datum_bis'],
			'cookiejar': response.meta['cookiejar'],
			'download_slot': response.meta['download_slot'],
			'ts_idx': response.meta['ts_idx'],
		}
		if extra:
			base.update(extra)
		return base

	# ------------------------------------------------------------------
	# Form-Submit mit Datumsbereich
	# ------------------------------------------------------------------
	def parse_form(self, response):
		idx = response.meta['ts_idx']
		datum_von = response.meta['datum_von']
		datum_bis = response.meta['datum_bis']
		logger.info(f"parse_form[TS{idx}] status={response.status} ({datum_von} – {datum_bis})")
		logger.debug("parse_form Rohergebnis: " + response.text[:30000])

		formdata = {
			'maincontent_1$txtCaseNr': '',
			'maincontent_1$txtDateFrom': datum_von,
			'maincontent_1$txtDateTo': datum_bis,
			'maincontent_1$ddlJustice': '0',
			'maincontent_1$txtLGVENr': '',
			'maincontent_1$ddlLGVE': 'Alle',
			'maincontent_1$txtKeyword1': '',
			'maincontent_1$txtKeyword2': '',
			'maincontent_1$rbtnOp1': 'und',
			'maincontent_1$txtKeyword3': '',
			'maincontent_1$rbtnOp2': 'und',
			'maincontent_1$txtKeyword4': '',
			'maincontent_1$rbtnOp3': 'und',
		}
		yield scrapy.FormRequest.from_response(
			response,
			formxpath='//*[@id="maincontent_1_btnSearch"]',
			formdata=formdata,
			callback=self.parse_weiter,
			errback=self.errback_httpbin,
			meta=self._carry_meta(response, {'Seite': 1}),
			dont_filter=True,
		)

	def parse_weiter(self, response):
		idx = response.meta['ts_idx']
		seite = response.meta['Seite']
		datum_von = response.meta['datum_von']
		datum_bis = response.meta['datum_bis']
		logger.info(f"parse_weiter[TS{idx} S{seite}] status={response.status}")
		antwort = response.text
		logger.debug("parse_weiter Rohergebnis: " + antwort[:30000])

		if seite > 1:
			trefferzahl = response.meta['Trefferzahl']
		else:
			trefferzahl_string = PH.NC(
				response.xpath("//p/span[@id='maincontent_1_lblCountInfo' and contains(.,'Anzahl Treffer: ')]/text()").get(),
				warning=f"kein lblCountInfo in TS{idx} ({datum_von}–{datum_bis}) – behandle als 0 Treffer",
			)
			if not trefferzahl_string:
				logger.warning(f"TS{idx} ({datum_von}–{datum_bis}): keine Treffer (kein Trefferzahl-Element gefunden)")
				return
			logger.info(f"TS{idx} Trefferzahlstring: {trefferzahl_string}")
			trefferzahl = int(trefferzahl_string[16:])
			if trefferzahl == 0:
				logger.warning(f"TS{idx} ({datum_von}–{datum_bis}): 0 Treffer")
				return
			logger.info(f"TS{idx} ({datum_von}–{datum_bis}): {trefferzahl} Treffer")

		entscheide = response.xpath(
			"//tr[td/a[contains(@id,'maincontent_1_lstJurisdictions_hypCaseNr_') and contains(@href, 'lgve')]]"
		)
		logger.info(f"TS{idx} S{seite}: {len(entscheide)} Entscheide auf dieser Seite")

		for entscheid in entscheide:
			item = {}
			text = entscheid.get()
			url = self.HOST + PH.NC(entscheid.xpath('.//a/@href').get(), error="keine URL gefunden in " + text)
			item['HTMLUrls'] = [url]
			item['Leitsatz'] = PH.NC(entscheid.xpath("./td[not(@class)]/text()").get(), warning="kein Leitsatz in " + text)
			item['Num'] = PH.NC(entscheid.xpath("./td/a/text()").get(), error="keine Geschäftsnummer in " + text)
			num2 = PH.NC(entscheid.xpath("./td[@class='dt-body-nowrap'][3]/text()").get(),
			             info="keine zweite Geschäftsnummer in " + text)
			if num2:
				item['Num2'] = num2
			edatum_roh = PH.NC(entscheid.xpath("./td[@class='dt-body-nowrap'][1]/text()").get(),
			                   info="kein Entscheiddatum in " + text)
			item['EDatum'] = self.norm_datum(edatum_roh)
			logger.info(f"TS{idx} Entscheid: " + json.dumps(item))
			yield scrapy.Request(
				url=item['HTMLUrls'][0],
				callback=self.parse_document,
				errback=self.errback_httpbin,
				meta=self._carry_meta(response, {'item': item}),
			)

		if trefferzahl > self.TREFFER_PRO_SEITE * seite:
			if len(entscheide) < self.TREFFER_PRO_SEITE:
				logger.error(
					f"TS{idx}: Gehe von {self.TREFFER_PRO_SEITE} Treffer pro Seite aus. "
					f"Insgesamt sind es {trefferzahl}. Dies ist Seite {seite} mit nur {len(entscheide)} Treffern."
				)
			yield scrapy.FormRequest.from_response(
				response,
				formdata={'maincontent_1$dprJurisdictions$ctl02$ctl00': ''},
				callback=self.parse_weiter,
				errback=self.errback_httpbin,
				dont_click=True,
				meta=self._carry_meta(response, {'Seite': seite + 1, 'Trefferzahl': trefferzahl}),
			)

	def parse_document(self, response):
		idx = response.meta['ts_idx']
		logger.info(f"parse_document[TS{idx}] status={response.status}")
		antwort = response.text
		logger.debug("parse_document Rohergebnis: " + antwort[:20000])

		item = response.meta['item']
		textteile = response.xpath("//div[@id='JurisdictionPrintArea']")
		text = textteile.get()
		item['VGericht'] = PH.NC(
			textteile.xpath(".//th[.='Gericht/Verwaltung:' or .='Instanz:']/following-sibling::td/text()").get(),
			error="Gericht nicht gefunden in " + item['Num'] + ": '" + text + "'",
		)
		vkammer = PH.NC(
			textteile.xpath(".//th[.='Abteilung:']/following-sibling::td/text()").get(),
			info="Kammer nicht gefunden in " + item['Num'] + ": '" + text + "'",
		)
		if len(vkammer) > 3:
			item['VKammer'] = vkammer
		else:
			vkammer = ""
		item['Rechtsgebiet'] = PH.NC(
			textteile.xpath(".//th[.='Rechtsgebiet:']/following-sibling::td/text()").get(),
			info="Rechtsgebiet nicht gefunden in " + item['Num'] + ": '" + text + "'",
		)
		item['Normen'] = PH.NC(
			textteile.xpath(".//th[.='Gesetzesartikel:']/following-sibling::td/text()").get(),
			info="Normen nicht gefunden in " + item['Num'] + ": '" + text + "'",
		)
		item['Weiterzug'] = PH.NC(
			textteile.xpath(".//th[.='Rechtskraft:']/following-sibling::td/text()").get(),
			info="Rechtskraft/Weiterzug nicht gefunden in " + item['Num'] + ": '" + text + "'",
		)
		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect(item['VGericht'], vkammer, item['Num'])
		PH.write_html(text, item, self)
		yield item
