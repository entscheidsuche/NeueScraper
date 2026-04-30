# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
import base64
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.headless_client import HeadlessClient
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
import uuid
import random

logger = logging.getLogger(__name__)

class CH_BGE(BasisSpider):
	name = 'CH_BGE'
	AUFSETZJAHR = 1954


	# Direkt search.bger.ch (kein bge_helper-Proxy mehr)
	HOST="https://search.bger.ch"
	INITIAL_URL='/ext/eurospider/live/de/php/clir/http/index_atf.php?lang=de'
	SUCH_URL='/ext/eurospider/live/de/php/clir/http/index_atf.php?year={band}&volume={volume}&lang=de&zoom=&system=clir'
	EGMR_URL='/ext/eurospider/live/de/php/clir/http/index_cedh.php?lang=de'
	
	SPRACHEN={"de": "D","fr": "F","it": "I"}
	
	reMeta=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>.*(?:(?:Auszug aus dem )?(?:Urteil|Entscheid) (?:der|des)|(?:Extrait de l'a|A)rrêt (?:de la|du)|Estratto dalla sentenza) (?P<VKammer>.+) (?:i\.\s*S\.|dans la cause) [^_]+ (?P<Num2>\d+[A-F]?(?:_|\.)\d+/(?:19|20)\d\d) (?:[^_]+ )?(?:vom|du)\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d))$")
	reMetaOhneGN=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>.*(?:(?:Auszug aus dem )?(?:Urteil|Entscheid) (?:der|des)|(?:Extrait de l'a|A)rrêt (?:de la|du)|Estratto dalla sentenza) (?P<VKammer>.+)\s+(?:vom|du)\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d))$")
	reMetaOhneKammer=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>.*(?:(?:Auszug aus dem )?(?:Urteil|Entscheid)|(?:Extrait de l\'a|A)rrêt (?:de la|du)|Estratto dalla sentenza)\s+(?:vom|du)\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)\s+i\.\s*S\.\s+.+\.?)\s*$")
	# Alte BGE-Formate (vor Einführung der Geschäftsnummer): Datum vor i.S./dans
	# la cause/nella causa, Kammer optional. Kein Num2.
	# DE: Urteil/Entscheid/Verfügung mit optionaler Kammer, "i. S." mit/ohne Spaces, terminale Period optional.
	reMetaAltDE=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>(?:Auszug aus (?:dem |der ))?(?:Urteil|Entscheid|Verfügung)(?:\s+(?:der|des)\s+(?P<VKammer>.+?))?\s+vom\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)\s+i\.\s*S\.\s+.+\.?)\s*$")
	# FR: 'Arrêt'/'Extrait de l'arrêt' mit optionaler Kammer, optionalem Komma vor 'du', 'dans la cause' oder 'en la cause'.
	reMetaAltFR=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>(?:Extrait de l'arrêt|Arrêt)(?:\s+de la\s+(?P<VKammer>.+?))?\s*,?\s+du\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)\s*,?\s+(?:dans la cause|en la cause)\s+.+\.?)\s*$")
	# IT: 'Estratto dalla|della sentenza' oder 'Sentenza', Datum optional mit 'del' davor, optionale Kammer mit 'della'.
	reMetaAltIT=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>(?:Estratto (?:dalla|della) sentenza|Sentenza)\s+(?:del\s+)?(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)(?:\s+(?:della|del)\s+(?P<VKammer>.+?))?\s+nella causa\s+.+\.?)\s*$")

	# Sehr alte BGE-Bände (1979/1980 etc.): manche Einträge stehen ohne
	# führende Eintrag-Nummerierung im Inhaltsverzeichnis. Dieselben Strukturen
	# wie reMetaAlt(DE|FR|IT), nur OHNE den "<NN>."-Prefix.
	reMetaAltDEnoNum=re.compile(r"^(?P<formal>(?:Auszug aus (?:dem |der ))?(?:Urteil|Entscheid|Verfügung)(?:\s+(?:der|des)\s+(?P<VKammer>.+?))?\s+vom\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)\s+i\.\s*S\.\s+.+\.?)\s*$")
	reMetaAltFRnoNum=re.compile(r"^(?P<formal>(?:Extrait de l'arrêt|Arrêt)(?:\s+de la\s+(?P<VKammer>.+?))?\s*,?\s+du\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)\s*,?\s+(?:dans la cause|en la cause)\s+.+\.?)\s*$")
	reMetaAltITnoNum=re.compile(r"^(?P<formal>(?:Estratto (?:dalla|della) sentenza|Sentenza)\s+(?:del\s+)?(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d)(?:\s+(?:della|del)\s+(?P<VKammer>.+?))?\s+nella causa\s+.+\.?)\s*$")

	# Format: "<NN>.<sp>(Auszug aus dem )?Urteil/Entscheid i.S. <Parteien> [<GN>] vom <Datum>."
	# Beispiele (DE, ohne Kammer, mit oder ohne alter EVG-Geschäftsnummer):
	#   "22.Urteil i.S. C. gegen ... B 34/00 vom 21. Mai 2002."
	#   "25.Auszug aus dem Urteil i.S. K. gegen ... K 172/00 vom 22. April 2002."
	#   "28.Urteil i.S. A. gegen ... U 319/01 vom 2. Mai 2002."
	# Die Geschäftsnummer ist hier z.B. "B 34/00" / "U 319/01" / "K 172/00" (alte EVG-Form)
	# – einzelner Buchstabe + Leerzeichen + Zahl + optional Buchstabe + "/" + 2- oder 4-stelliges Jahr.
	reMetaUrteilDirektDE=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>(?:Auszug aus (?:dem |der ))?(?:Urteil|Entscheid|Verfügung)\s+i\.\s*S\.\s+.+?(?:\s+(?P<Num2>[A-Z]\s?\d+[A-Z]?/\d{2,4}))?\s+vom\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d))\.?\s*$")
	# Französisches Pendant: "Arrêt dans la cause|en la cause <Parteien> [<GN>] du <Datum>." ohne Kammer.
	reMetaUrteilDirektFR=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\.\s*(?P<formal>(?:Extrait de l'arrêt|Arrêt)\s+(?:dans la cause|en la cause)\s+.+?(?:\s+(?P<Num2>[A-Z]\s?\d+[A-Z]?/\d{2,4}))?\s*,?\s+du\s+(?P<Datum>\d\d?\.?(?:er)?\s*(?:"+"|".join(BasisSpider.MONATEde+BasisSpider.MONATEfr+BasisSpider.MONATEit)+r")\s+(?:19|20)\d\d))\.?\s*$")

	reMetaSimple=re.compile(r"^[^\d]?(?:\d+\s+[IVX]+[ab]?\s+\d+\s+)?[^\d]?\d+\s?\.\s*(?P<Rest>.+)$")
	reRemoveDivs=re.compile(r"(</(div|span|a|artref)>)|(<(div|span|a|artref)[^>]+>)|(?:^<br>)|(?:<br>(?:(?=<br>)|$))")
	reDoubleSpaces=re.compile(r"\s\s+")

	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Referer': 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index_atf.php?lang=de',
		'Upgrade-Insecure-Requests': '1',
		'Sec-Fetch-Dest': 'document',
		'Sec-Fetch-Mode': 'navigate',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-User': '?1',
		'Priority': 'u=0, i',
		'Pragma': 'no-cache',
		'Cache-Control': 'no-cache',
		'TE': 'trailers'
	}

	# 100 Browserprofile zur Rotation. Jedes Profil ist ein vollständiges
	# Header-Set, das wie ein realer Browser aussieht (Firefox/Chrome/Edge/Safari
	# auf Mac/Win/Linux, mit jeweils passenden Sec-Ch-Ua bzw. DNT/TE-Headern).
	# Der Generator wird einmal beim Klassenladen ausgeführt und dann verworfen.
	def _build_browser_profiles():
		REFERER = 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index_atf.php?lang=de'
		LANGUAGES = [
			'de,en-US;q=0.7,en;q=0.3',
			'de-CH,de;q=0.9,en;q=0.7,fr;q=0.6',
			'fr-CH,fr;q=0.9,de;q=0.8,it;q=0.5,en;q=0.4',
			'it-CH,it;q=0.9,de;q=0.7,fr;q=0.6,en;q=0.5',
			'de-DE,de;q=0.9,en-US;q=0.7,en;q=0.5',
			'en-US,en;q=0.9,de;q=0.7',
			'en-GB,en;q=0.9,de;q=0.6',
			'fr-FR,fr;q=0.9,en;q=0.5',
		]
		profiles = []
		lang_idx = [0]
		def next_lang():
			l = LANGUAGES[lang_idx[0] % len(LANGUAGES)]
			lang_idx[0] += 1
			return l

		# --- Firefox: 5 OS x 10 Versionen = 50 Profile ---
		firefox_oses = [
			'Macintosh; Intel Mac OS X 10.15',
			'Macintosh; Intel Mac OS X 14.0',
			'Windows NT 10.0; Win64; x64',
			'Windows NT 11.0; Win64; x64',
			'X11; Linux x86_64',
		]
		firefox_versions = [141, 140, 139, 138, 137, 136, 135, 134, 132, 130]
		for os_str in firefox_oses:
			for v in firefox_versions:
				ua = f'Mozilla/5.0 ({os_str}; rv:{v}.0) Gecko/20100101 Firefox/{v}.0'
				profiles.append({
					'browser': f'firefox-{v}',
					'headers': {
						'User-Agent': ua,
						'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
						'Accept-Language': next_lang(),
						'Accept-Encoding': 'gzip, deflate, br, zstd',
						'DNT': '1',
						'Connection': 'keep-alive',
						'Referer': REFERER,
						'Upgrade-Insecure-Requests': '1',
						'Sec-Fetch-Dest': 'document',
						'Sec-Fetch-Mode': 'navigate',
						'Sec-Fetch-Site': 'same-origin',
						'Sec-Fetch-User': '?1',
						'Priority': 'u=0, i',
						'Pragma': 'no-cache',
						'Cache-Control': 'no-cache',
						'TE': 'trailers',
					},
				})

		# --- Chrome: 3 OS x 10 Versionen = 30 Profile ---
		chrome_oses = [
			('Macintosh; Intel Mac OS X 10_15_7', '"macOS"'),
			('Windows NT 10.0; Win64; x64', '"Windows"'),
			('X11; Linux x86_64', '"Linux"'),
		]
		chrome_versions = [129, 128, 127, 126, 125, 124, 123, 122, 121, 120]
		for os_str, platform in chrome_oses:
			for v in chrome_versions:
				ua = f'Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36'
				profiles.append({
					'browser': f'chrome-{v}',
					'headers': {
						'User-Agent': ua,
						'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
						'Accept-Language': next_lang(),
						'Accept-Encoding': 'gzip, deflate, br, zstd',
						'Connection': 'keep-alive',
						'Referer': REFERER,
						'Upgrade-Insecure-Requests': '1',
						'sec-ch-ua': f'"Chromium";v="{v}", "Not.A/Brand";v="24", "Google Chrome";v="{v}"',
						'sec-ch-ua-mobile': '?0',
						'sec-ch-ua-platform': platform,
						'Sec-Fetch-Dest': 'document',
						'Sec-Fetch-Mode': 'navigate',
						'Sec-Fetch-Site': 'same-origin',
						'Sec-Fetch-User': '?1',
						'Priority': 'u=0, i',
						'Cache-Control': 'no-cache',
						'Pragma': 'no-cache',
					},
				})

		# --- Edge: 2 OS x 6 Versionen = 12 Profile ---
		edge_oses = [
			('Windows NT 10.0; Win64; x64', '"Windows"'),
			('Macintosh; Intel Mac OS X 10_15_7', '"macOS"'),
		]
		edge_versions = [128, 127, 126, 125, 124, 122]
		for os_str, platform in edge_oses:
			for v in edge_versions:
				ua = f'Mozilla/5.0 ({os_str}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0'
				profiles.append({
					'browser': f'edge-{v}',
					'headers': {
						'User-Agent': ua,
						'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
						'Accept-Language': next_lang(),
						'Accept-Encoding': 'gzip, deflate, br, zstd',
						'Connection': 'keep-alive',
						'Referer': REFERER,
						'Upgrade-Insecure-Requests': '1',
						'sec-ch-ua': f'"Chromium";v="{v}", "Not.A/Brand";v="24", "Microsoft Edge";v="{v}"',
						'sec-ch-ua-mobile': '?0',
						'sec-ch-ua-platform': platform,
						'Sec-Fetch-Dest': 'document',
						'Sec-Fetch-Mode': 'navigate',
						'Sec-Fetch-Site': 'same-origin',
						'Sec-Fetch-User': '?1',
						'Priority': 'u=0, i',
					},
				})

		# --- Safari: 8 Profile (verschiedene macOS + Versionen) ---
		safari_combos = [
			('Macintosh; Intel Mac OS X 10_15_7', '17.5'),
			('Macintosh; Intel Mac OS X 14_5', '17.5'),
			('Macintosh; Intel Mac OS X 14_4', '17.4'),
			('Macintosh; Intel Mac OS X 14_2', '17.2'),
			('Macintosh; Intel Mac OS X 13_6_8', '17.0'),
			('Macintosh; Intel Mac OS X 13_5_2', '16.6'),
			('Macintosh; Intel Mac OS X 12_7_5', '16.4'),
			('Macintosh; Intel Mac OS X 12_6_3', '16.2'),
		]
		for os_str, ver in safari_combos:
			ua = f'Mozilla/5.0 ({os_str}) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/{ver} Safari/605.1.15'
			profiles.append({
				'browser': f'safari-{ver}',
				'headers': {
					'User-Agent': ua,
					'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
					'Accept-Language': next_lang(),
					'Accept-Encoding': 'gzip, deflate, br',
					'Connection': 'keep-alive',
					'Referer': REFERER,
					'Upgrade-Insecure-Requests': '1',
				},
			})

		assert len(profiles) == 100, f"Erwartet 100 Profile, habe {len(profiles)}"
		return profiles

	BROWSER_PROFILES = _build_browser_profiles()
	del _build_browser_profiles
	# Lane-Architektur: N parallele "Lanes" mit eigener Zyte-Session, eigenem
	# Cookie-Jar, eigenem Browser-Profil und eigenem Scrapy download_slot.
	# Die Per-IP-Drossel (search.bger.ch: max. 1 Request pro 2s pro IP) wird
	# über DOWNLOAD_DELAY=2 + slot-basierte Concurrency=1 enforced.
	# Gesamtdurchsatz = LANE_COUNT × 0.5 req/s.
	LANE_COUNT = 30
	custom_settings = {
		"COOKIES_ENABLED": True,
		"COOKIES_DEBUG": True,
		"DOWNLOAD_DELAY": .1,                       # 1 Request alle 2s pro Lane-Slot
		"RANDOMIZE_DOWNLOAD_DELAY": False,         # exakt 2s, kein Über-/Unterschreiten
		"CONCURRENT_REQUESTS_PER_DOMAIN": 30,       # nicht pro Lane, sondern gesamt
		"CONCURRENT_REQUESTS": 100,                # genug Platz für alle Lanes parallel
		"AUTOTHROTTLE_ENABLED": False,             # wir steuern explizit per Slot
		"ZYTE_API_MAX_REQUESTS": 100,
		# Default-Retry der Scrapy-RetryMiddleware auf 1 reduzieren. Wir haben
		# eigene, gestaffelte Retry-Pfade (_retry_lane_initial / _retry_trefferliste)
		# mit MAX_VERSUCHE=10 — der Default verstärkt sonst Bursts auf ein
		# überlastetes Backend, statt Last zu verteilen.
		"RETRY_TIMES": 1,
		# Datenverlust mid-stream als Fehler werten, nicht als Warnung mit
		# unvollständigem Body durchreichen. Sonst landen abgeschnittene
		# Documents als "scheinbar fertige" Items in der Pipeline und werden
		# in Folgeläufen via "neu"-Logik nicht mehr neu geholt.
		"DOWNLOAD_FAIL_ON_DATALOSS": True,
		# Diagnose-Middleware aktivieren: loggt Set-Cookie/Redirect/Short-200/Non-2xx,
		# damit wir Cookie-Resets und Bot-Challenges vor den eigentlichen Fehlern sehen.
		"DOWNLOADER_MIDDLEWARES": {
			"scrapy.downloadermiddlewares.redirect.RedirectMiddleware": 600,
			"NeueScraper.middlewares.ProxyAwareRedirectMiddleware": 601,
			"NeueScraper.middlewares.CookieDiagnoseMiddleware": 850,
		},
	}

	MAX_VERSUCHE = 10

	def _lane_id(self, lane_idx):
		"""Lane-Slot-ID, konstant pro Lane. Wird ausschliesslich als
		download_slot verwendet (für die 2s-Drossel pro IP)."""
		return f"lane_{lane_idx}"

	def _new_session_id(self):
		"""Neue Zyte-API-Session-ID (= neue Exit-IP bei sticky session)."""
		return uuid.uuid4().hex

	def _jar_for_session(self, session_id):
		"""Cookie-Jar-ID, die an die Session-ID gebunden ist. Wenn die Session
		wechselt (Retry oder Zyte-IP-Rotation), bekommt die neue Session zwingend
		einen frischen Jar — alte Cookies aus früherer IP werden NICHT
		mitgenommen. Damit bleibt Cookie ↔ IP atomar gepaart."""
		return f"jar_{session_id[:16]}"

	def _pick_browser_profile(self):
		"""Liefert ein zufällig gewähltes Browser-Profil aus BROWSER_PROFILES."""
		return random.choice(self.BROWSER_PROFILES)

	def _safe_response_text(self, response):
		"""Robuste Variante von response.text: fällt bei Responses ohne
		Text-Decoder (z.B. fehlender/unbekannter Charset) auf utf-8 mit
		errors='replace' zurück, statt mit AttributeError zu sterben."""
		try:
			return response.text
		except AttributeError:
			body = response.body or b""
			logger.warning(
				f"_safe_response_text: Response ohne Text-Decoder, "
				f"falle auf utf-8 zurück: {response.url}"
			)
			return body.decode("utf-8", errors="replace")

	@property
	def headless(self):
		"""HeadlessClient mit Settings aus dem Crawler. Lazy initialisiert,
		weil self.settings erst nach from_crawler verfügbar ist."""
		client = getattr(self, "_headless_client", None)
		if client is None:
			client = HeadlessClient.from_settings(self.settings)
			self._headless_client = client
			if client.is_enabled():
				logger.info("HeadlessClient aktiv: %s", client.base_url)
			else:
				logger.warning("HeadlessClient deaktiviert (HEADLESS-Token fehlt)")
		return client

	def _build_lane_initial_request(self, lane_idx, lane_groups, versuch=1):
		"""Initial-Request einer Lane: setzt Cookies via INITIAL_URL.
		download_slot=lane_id (konstant für 2s-Drossel pro IP).
		cookiejar=jar_id (an session_id gebunden, wechselt mit der IP).
		session_id und browser_profile werden bei jedem Versuch frisch gezogen."""
		lane_id = self._lane_id(lane_idx)
		session_id = self._new_session_id()
		jar_id = self._jar_for_session(session_id)
		profile = self._pick_browser_profile()
		headers = dict(profile['headers'])
		logger.info(
			f"Lane {lane_idx} Initial-Request Versuch={versuch} slot={lane_id} "
			f"jar={jar_id} session={session_id} profil={profile['browser']} groups={len(lane_groups)}"
		)
		return scrapy.Request(
			url=self.HOST + self.INITIAL_URL,
			headers=headers,
			callback=self.parse_cookie,
			errback=self.errback_lane_initial,
			dont_filter=True,
			meta={
				'cookiejar': jar_id,
				'lane_idx': lane_idx,
				'lane_id': lane_id,
				'jar_id': jar_id,
				'lane_groups': lane_groups,
				'versuch': versuch,
				'session_id': session_id,
				'zyte_api': {'session': {'id': session_id}, 'httpResponseHeaders': True},
				'handle_httpstatus_list': [502],
				'browser_profile': profile['browser'],
				'browser_headers': headers,
				'download_slot': lane_id,
			},
		)

	def _build_all_lane_initials(self, ab=None):
		"""Sammelt alle (Jahr, Band)-Gruppen plus EGMR und verteilt sie
		round-robin auf LANE_COUNT Lanes. Erzeugt einen Initial-Request je Lane."""
		bis = datetime.date.today().year
		von = self.AUFSETZJAHR if ab is None else int(ab)
		all_groups = []
		for jahr in range(von, bis + 1):
			for volume in ["I", "II", "III", "IV", "V"]:
				all_groups.append(("BGE", jahr, volume))
		all_groups.append(("EGMR",))
		# Round-robin auf Lanes verteilen
		lanes = [[] for _ in range(self.LANE_COUNT)]
		for i, group in enumerate(all_groups):
			lanes[i % self.LANE_COUNT].append(group)
		requests = []
		for idx, lane_groups in enumerate(lanes):
			if not lane_groups:
				continue
			requests.append(self._build_lane_initial_request(idx, lane_groups, versuch=1))
		logger.info(
			f"Initial: {self.LANE_COUNT} Lanes, {len(all_groups)} Gruppen "
			f"({len(all_groups)-1} BGE + 1 EGMR), {len(requests)} Initial-Requests erzeugt."
		)
		return requests

	def _retry_lane_initial(self, lane_idx, lane_groups, versuch, grund):
		"""Initial-Request einer Lane scheiterte → neue Session/Profil, gleicher Slot/Jar."""
		if versuch >= self.MAX_VERSUCHE:
			logger.error(f"Lane {lane_idx} Initial nach {versuch} Versuchen verworfen ({grund}). {len(lane_groups)} Gruppen entfallen.")
			return None
		logger.warning(
			f"Lane {lane_idx} Initial Versuch {versuch} fehlgeschlagen ({grund}); starte Versuch {versuch+1}."
		)
		return self._build_lane_initial_request(lane_idx, lane_groups, versuch + 1)

	def errback_lane_initial(self, failure):
		"""Errback für Lane-Initial-Requests bei Verbindungsfehlern."""
		self.errback_httpbin(failure)
		request = failure.request
		lane_idx = request.meta.get('lane_idx')
		lane_groups = request.meta.get('lane_groups') or []
		versuch = request.meta.get('versuch', 1)
		if lane_idx is None:
			return
		retry = self._retry_lane_initial(lane_idx, lane_groups, versuch, f"errback {failure.type.__name__}")
		if retry is not None:
			self.crawler.engine.crawl(retry)

	def _build_trefferliste_request(self, group, lane_meta, versuch=1):
		"""Trefferliste-Request einer Gruppe. Nutzt das Cookie-/Session-Paar
		der Lane (über lane_meta) — diese Methode wird NUR mit gerade frisch
		initialisierten Cookies (versuch=1 für die Gruppe) aufgerufen.
		Retries laufen über _retry_trefferliste → frischer Initial (neue Session+Jar)."""
		lane_id = lane_meta['lane_id']
		lane_idx = lane_meta['lane_idx']
		jar_id = lane_meta['jar_id']
		session_id = lane_meta['session_id']
		profile_name = lane_meta['browser_profile']
		headers = lane_meta['browser_headers']

		meta = {
			'cookiejar': jar_id,
			'lane_idx': lane_idx,
			'lane_id': lane_id,
			'jar_id': jar_id,
			'group': group,
			'versuch': versuch,
			'session_id': session_id,
			'zyte_api': {'session': {'id': session_id}, 'httpResponseHeaders': True},
			'handle_httpstatus_list': [502],
			'browser_profile': profile_name,
			'browser_headers': headers,
			'download_slot': lane_id,
		}
		if group[0] == "BGE":
			_, jahr, volume = group
			url = self.HOST + self.SUCH_URL.format(band=jahr - 1874, volume=volume)
			meta['Volume'] = volume
			meta['Jahr'] = jahr
			callback = self.parse_trefferliste
		else:
			url = self.HOST + self.EGMR_URL
			callback = self.parse_EGMR_trefferliste
		logger.info(
			f"Trefferliste Lane {lane_idx} Gruppe {group} Versuch={versuch} "
			f"jar={jar_id} session={session_id} profil={profile_name}"
		)
		return scrapy.Request(
			url=url, headers=headers,
			callback=callback, errback=self.errback_trefferliste,
			dont_filter=True, meta=meta,
		)

	def _retry_trefferliste(self, response, grund):
		"""Trefferliste scheiterte → kompletter Neustart für nur diese eine Gruppe:
		neue Zyte-Session, neuer Jar, frischer INITIAL-Request, danach diese
		eine Trefferliste. Damit bleiben Cookies und IP atomar gepaart."""
		group = response.meta['group']
		lane_idx = response.meta['lane_idx']
		versuch = response.meta.get('versuch', 1)
		if versuch >= self.MAX_VERSUCHE:
			logger.error(f"Trefferliste Lane {lane_idx} Gruppe {group} nach {versuch} Versuchen verworfen ({grund}).")
			return None
		logger.warning(
			f"Trefferliste Lane {lane_idx} Gruppe {group} Versuch {versuch} fehlgeschlagen ({grund}); "
			f"starte Versuch {versuch+1} mit frischer Session+Jar (über INITIAL)."
		)
		# Frischer Initial-Request, der NUR diese eine Gruppe als lane_groups hat.
		# parse_cookie wird daraufhin nur eine einzige Trefferliste yielden.
		return self._build_lane_initial_request(lane_idx, [group], versuch + 1)

	def errback_trefferliste(self, failure):
		"""Errback für Trefferlisten-Requests."""
		self.errback_httpbin(failure)
		request = failure.request
		if 'group' not in request.meta or 'lane_idx' not in request.meta:
			return
		# kuenstlichen response-aehnlichen Stub bauen, damit _retry_trefferliste
		# auf request.meta zugreifen kann
		class _Stub:
			pass
		stub = _Stub()
		stub.meta = request.meta
		retry = self._retry_trefferliste(stub, f"errback {failure.type.__name__}")
		if retry is not None:
			self.crawler.engine.crawl(retry)

	def initial_request(self):
		return self._build_all_lane_initials(self.ab)

	def parse_cookie(self, response):
		"""Initial-Response einer Lane: Cookies sind nun im jar_id gesetzt.
		Spawnt für alle Gruppen dieser Lane je einen Trefferlisten-Request mit
		demselben jar_id und derselben session_id (Cookie ↔ IP gepaart).
		Bei Trefferliste-Retry wird über _retry_trefferliste ein neuer Initial
		mit lane_groups=[group] erzeugt, daher kann lane_groups hier auch nur
		eine einzige Gruppe enthalten."""
		lane_idx = response.meta['lane_idx']
		lane_id = response.meta['lane_id']
		lane_groups = response.meta['lane_groups']
		versuch = response.meta['versuch']
		jar_id = response.meta['jar_id']
		session_id = response.meta['session_id']

		if response.status == 502:
			retry = self._retry_lane_initial(lane_idx, lane_groups, versuch, "502 auf Initial")
			if retry is not None:
				yield retry
			return

		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_cookie Lane={lane_idx}: Imperva-Challenge erkannt "
				f"(status={response.status} len={len(self._safe_response_text(response) or '')}), "
				f"delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_cookie,
				original_meta=response.meta,
			)
			return

		antwort = self._safe_response_text(response)
		logger.info(
			f"parse_cookie Lane={lane_idx} jar={jar_id} session={session_id} "
			f"status={response.status} len={len(antwort)} groups={len(lane_groups)} URL={response.url}"
		)
		logger.debug("parse_cookie Rohergebnis: " + antwort[:30000])
		try:
			cm = next(mw for mw in self.crawler.engine.downloader.middleware.middlewares
			          if isinstance(mw, CookiesMiddleware))
			cookies = json.dumps(
				[{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path,
				  "expires": c.expires, "secure": c.secure, "discard": c.discard,
				  "rest": getattr(c, "_rest", {})} for c in cm.jars[jar_id]],
				ensure_ascii=False)
			logger.info(f"Cookies(Lane {lane_idx}, jar={jar_id}): {cookies}")
		except Exception as e:
			logger.warning(f"Cookies konnten nicht geloggt werden: {e!r}")

		# Lane-Meta zusammenstellen: jar_id und session_id sind atomar gepaart;
		# alle Folge-Requests dieser Lane benutzen genau dieses Paar.
		lane_meta = {
			'lane_idx': lane_idx,
			'lane_id': lane_id,
			'jar_id': jar_id,
			'session_id': session_id,
			'browser_profile': response.meta.get('browser_profile'),
			'browser_headers': response.meta.get('browser_headers') or self.HEADER,
		}
		for group in lane_groups:
			yield self._build_trefferliste_request(group, lane_meta, versuch=1)

	def request_generator(self, ab):
		return self.initial_request()

	def __init__(self, ab=None, neu=None):
		super().__init__()
		self.neu=neu
		self.ab=ab

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status)+" URL: "+response.url)
		if response.status == 502:
			retry = self._retry_trefferliste(response, "502 auf Trefferliste")
			if retry is not None:
				yield retry
			return

		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_trefferliste Lane={response.meta.get('lane_idx')}: "
				f"Imperva-Challenge erkannt (status={response.status} "
				f"len={len(self._safe_response_text(response) or '')}), delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_trefferliste,
				original_meta=response.meta,
			)
			return

		antwort=self._safe_response_text(response)
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_trefferliste Rohergebnis: "+antwort[:30000])
		jahr=response.meta['Jahr']
		volume=response.meta['Volume']
		jar_id=response.meta['jar_id']
		session_id=response.meta.get('session_id')
		lane_id=response.meta.get('lane_id', jar_id)
		logger.info(f"parse_trefferliste Lane={response.meta.get('lane_idx')} jar={jar_id}")

		# Browser-Profil der Lane weiterverwenden
		browser_headers = dict(response.meta.get('browser_headers') or self.HEADER)
		browser_profile = response.meta.get('browser_profile')

		urteile=response.xpath("//ol/li[a]")
		if urteile is None:
			logger.info("keine Leitentscheide für "+str(jahr)+" Volume "+volume)
		else:
			logger.info("Liste von {} Urteilen".format(len(urteile))+" für "+str(jahr)+" Volume "+volume)

			def _sub_meta(extra):
				# Sub-Requests laufen mit demselben (jar_id, session_id)-Paar wie
				# die Trefferliste — Cookie ↔ IP bleibt atomar gekoppelt.
				# download_slot=lane_id für die 2s-Drossel pro IP.
				m = {
					'cookiejar': jar_id,
					'jar_id': jar_id,
					'browser_profile': browser_profile,
					'browser_headers': browser_headers,
					'download_slot': lane_id,
					'lane_id': lane_id,
					'lane_idx': response.meta.get('lane_idx'),
				}
				if session_id:
					m['session_id'] = session_id
					m['zyte_api'] = {'session': {'id': session_id}, 'httpResponseHeaders': True}
				m.update(extra)
				return m

			for entscheid in urteile:
				text=entscheid.get()
				item={}
				item['Num']="BGE "+entscheid.xpath("./a/text()").get()
				raw_href = entscheid.xpath("./a/@href").get()
				abs_url = response.urljoin(raw_href)
				item['HTMLUrls']=[abs_url]
				url = abs_url

				request = scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, headers=browser_headers, meta=_sub_meta({'item': item, 'Jahr': jahr}))

				subrequestliste=[]
				basisurl=item['HTMLUrls'][0]
				for sprache in self.SPRACHEN:
					url=basisurl.replace("%3Ade&lang=de","%3A"+sprache+"%3Aregeste&lang=de")
					subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, headers=browser_headers, meta=_sub_meta({'item': item, 'Jahr': jahr, 'Sprache': sprache})))
				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
				yield request

	def parse_EGMR_trefferliste(self, response):
		logger.info("parse_EGMR_trefferliste response.status "+str(response.status)+" URL: "+response.url)
		if response.status == 502:
			retry = self._retry_trefferliste(response, "502 auf EGMR-Trefferliste")
			if retry is not None:
				yield retry
			return
		antwort=self._safe_response_text(response)
		logger.info("parse_EGMR_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_EGMR_trefferliste Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['jar_id']
		session_id=response.meta.get('session_id')
		lane_id=response.meta.get('lane_id', jar_id)
		logger.info(f"parse_EGMR_trefferliste Lane={response.meta.get('lane_idx')} jar={jar_id}")

		# Browser-Profil der Lane weiterverwenden
		browser_headers = dict(response.meta.get('browser_headers') or self.HEADER)
		browser_profile = response.meta.get('browser_profile')

		urteile=response.xpath("//table[@width='75%' and @style='border: 0px; border-collapse: collapse;']/tr[td]")
		if urteile is None:
			logger.error("keine EGMR-Entscheide")
		else:
			logger.info("Liste von {} EGMR-Urteilen.".format(len(urteile)))

			def _sub_meta(extra):
				# Sub-Requests in derselben (jar, session)-Bindung; download_slot=lane_id für 2s-Drossel.
				m = {
					'cookiejar': jar_id,
					'jar_id': jar_id,
					'browser_profile': browser_profile,
					'browser_headers': browser_headers,
					'download_slot': lane_id,
					'lane_id': lane_id,
					'lane_idx': response.meta.get('lane_idx'),
				}
				if session_id:
					m['session_id'] = session_id
					m['zyte_api'] = {'session': {'id': session_id}, 'httpResponseHeaders': True}
				m.update(extra)
				return m

			for entscheid in urteile:
				item={}
				text=entscheid.get()
				item['Num']=PH.NC(entscheid.xpath("./td[2]/a/text()").get(),error="keine Geschäftsnummer in "+text)
				item['Num2']=PH.NC(entscheid.xpath("./td[4]/text()").get(),warning="keine Fallname in "+text)
				datumstring=PH.NC(entscheid.xpath("./td[1]/text()").get(),error="Kein Entscheiddatum in "+text)
				item["EDatum"]=PH.NC(self.norm_datum(datumstring),error="Kein parsbares Entscheiddatum '"+datumstring+"' in "+text)
				raw_href = PH.NC(entscheid.xpath("./td[2]/a/@href").get(),error="Keine HTML URL in "+text)
				abs_url = response.urljoin(raw_href) if raw_href else raw_href
				item['HTMLUrls']=[abs_url]
				url = abs_url

				request = scrapy.Request(url=url, callback=self.parse_EGMR_document, errback=self.errback_httpbin, headers=browser_headers, meta=_sub_meta({'item': item}))

				subrequestliste=[]
				basisurl=item['HTMLUrls'][0]
				logger.debug("basisurl: "+str(basisurl))
				for sprache in self.SPRACHEN:
					url=basisurl.replace(":de&lang=de",":"+sprache+":regeste&lang=de")
					logger.debug("angepasste basisurl: "+url)
					subrequestliste.append(scrapy.Request(url=url, callback=self.parse_regeste, errback=self.errback_httpbin, headers=browser_headers, meta=_sub_meta({'item': item, 'Sprache': sprache})))

				subrequestliste.append(request)
				request=subrequestliste[0]
				del subrequestliste[0]
				request.meta['requestliste']=subrequestliste
				yield request

	def parse_regeste(self, response):
		logger.info("parse_regeste response.status "+str(response.status)+": "+response.url)

		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_regeste: Imperva-Challenge erkannt "
				f"(status={response.status} len={len(self._safe_response_text(response) or '')}), "
				f"delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_regeste,
				original_meta=response.meta,
			)
			return

		antwort=self._safe_response_text(response)
		logger.info("parse_regeste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_regeste Rohergebnis: "+antwort[:10000])

		item=response.meta['item']
		sprache=response.meta['Sprache']
		text_parse=response.xpath("//div[@id='highlight_content']")
		if text_parse:
			text=text_parse.get()
			text=self.reRemoveDivs.sub("",text).strip()
			text=self.reRemoveDivs.sub("",text).strip()
			text=self.reDoubleSpaces.sub(" ",text)
			item['Abstract_'+sprache]=text
		else:
			logger.warning("Content der Regeste ("+sprache+") nicht erkannt in "+antwort[:5000])
		subrequestliste=response.meta['requestliste']
		request=subrequestliste[0]
		del subrequestliste[0]
		request.meta['item']=item
		request.meta['requestliste']=subrequestliste
		yield(request)

	def _parse_meta_string(self, meta_string, item, jahr, antwort):
		"""Versucht meta_string aus dem BGE-Eintrag zu parsen und füllt
		EDatum/VKammer/Num2/Formal_org. Reihenfolge der Versuche:
		1) modernes Format mit Geschäftsnummer
		2) modernes Format ohne Geschäftsnummer
		3) altes Format (DE/FR/IT) ohne Geschäftsnummer, Kammer optional
		4) Legacy: ohne Kammer (nur Datum + i.S.)
		5) Catch-all: nur Aufzählungsnummer
		"""
		if not meta_string:
			return

		# 1) modernes Format mit GN
		m = self.reMeta.search(meta_string)
		if m:
			item['EDatum'] = self.norm_datum(m.group('Datum'))
			item['VKammer'] = m.group('VKammer')
			item['Num2'] = m.group('Num2').replace('.', '_')
			return

		# 2) modernes Format ohne GN
		m = self.reMetaOhneGN.search(meta_string)
		if m:
			logger.warning(f"Eintrags-Geschäftsnummer nicht parsbar {item['Num']}: {meta_string}\nin: {antwort}")
			item['EDatum'] = self.norm_datum(m.group('Datum'))
			item['VKammer'] = m.group('VKammer')
			return

		# 3) alte BGE-Formate (vor GN-Einführung) – DE / FR / IT
		for re_alt in (self.reMetaAltDE, self.reMetaAltFR, self.reMetaAltIT):
			m = re_alt.search(meta_string)
			if m:
				item['EDatum'] = self.norm_datum(m.group('Datum'))
				vkammer = m.groupdict().get('VKammer')
				if vkammer:
					item['VKammer'] = vkammer
				return

		# 3a) Alt-Formate OHNE Eintrag-Nummer (sehr alte BGE-Bände, 1979–80 etc.,
		#     wo das Inhaltsverzeichnis ohne führendes "<NN>." kommt).
		for re_alt in (self.reMetaAltDEnoNum, self.reMetaAltFRnoNum, self.reMetaAltITnoNum):
			m = re_alt.search(meta_string)
			if m:
				item['EDatum'] = self.norm_datum(m.group('Datum'))
				vkammer = m.groupdict().get('VKammer')
				if vkammer:
					item['VKammer'] = vkammer
				return

		# 3b) "Urteil i.S. ... [GN] vom Datum" ohne Kammer (alte EVG-Einträge)
		for re_direkt in (self.reMetaUrteilDirektDE, self.reMetaUrteilDirektFR):
			m = re_direkt.search(meta_string)
			if m:
				item['EDatum'] = self.norm_datum(m.group('Datum'))
				num2 = m.groupdict().get('Num2')
				if num2:
					# GN-Format normalisieren wie in reMeta: Punkte/Spaces zu Underscore
					item['Num2'] = num2.replace(' ', '_').replace('.', '_')
				return

		# 4) Fallback: ohne Kammer (Legacy-Pattern)
		m = self.reMetaOhneKammer.search(meta_string)
		if m:
			logger.warning(f"Eintrags-Kammer und GN nicht parsbar : {meta_string}\nin: {antwort}")
			item['Formal_org'] = m.group('formal')
			item['EDatum'] = self.norm_datum(m.group('Datum'))
			return

		# 5) Catch-all
		m = self.reMetaSimple.search(meta_string)
		if m:
			logger.warning(f"Eintragsdetails nicht parsbar {item['Num']}: {meta_string}\nin: {antwort}")
			item['Formal_org'] = m.group('Rest')
			item['EDatum'] = self.norm_datum(str(jahr))
			return

		# 6) Garnichts
		logger.error(f"Eintrag nicht matchbar {item['Num']}: {meta_string}\nin: {antwort}")

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))

		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_document: Imperva-Challenge erkannt "
				f"(status={response.status} len={len(self._safe_response_text(response) or '')}), "
				f"delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_document,
				original_meta=response.meta,
			)
			return

		antwort=self._safe_response_text(response)
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_document Rohergebnis: "+antwort[:20000])
		jahr=response.meta['Jahr']

		item=response.meta['item']
			
		meta=response.xpath("//div[@class='paraatf']/text()")
		item['VKammer']=''
		if meta:
			meta_string = (meta.get() or '').strip()
			self._parse_meta_string(meta_string, item, jahr, antwort)

		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])

		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)

		yield(item)


	def parse_EGMR_document(self, response):
		logger.info("parse_EGMR_document response.status "+str(response.status))
		antwort=self._safe_response_text(response)
		logger.info("parse_EGMR_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_EGMR_document Rohergebnis: "+antwort[:20000])

		item=response.meta['item']

		item['VKammer']='EGMR'

		item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])

		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:20000])
		else:
			PH.write_html(html.get(), item, self)

		yield(item)

	# ------------------------------------------------------------------
	# Headless-Subsystem Loop (Imperva-Challenge-Solver)
	# ------------------------------------------------------------------
	def _on_headless_event(self, response):
		"""Verarbeitet eine Antwort des Subsystems (Antwort auf /start oder
		auf /feed). Verzweigt in need_fetch / done / error."""
		event = self.headless.parse_event(response)
		state = event.get("state")
		loop = (response.meta.get("_headless_loop") or {}).copy()

		if state == "need_fetch":
			# Session-ID festhalten; bei jedem Event vorhanden
			loop["session_id"] = event.get("session_id")
			loop["fetch_count"] = int(loop.get("fetch_count", 0)) + 1
			logger.info(
				f"headless need_fetch #{loop['fetch_count']} "
				f"sess={event.get('session_id','')[:8]} → {event.get('url')}"
			)

			original_meta = loop.get("original_meta") or {}
			zyte_session = (original_meta.get("zyte_api") or {}).get("session", {}).get("id")
			upstream_meta = {
				"_headless_loop": loop,
				"_headless_event": event,
				"dont_redirect": True,
				"handle_httpstatus_all": True,
				"dont_merge_cookies": True,
			}
			if original_meta.get("jar_id"):
				upstream_meta["cookiejar"] = original_meta["jar_id"]
			if zyte_session:
				upstream_meta["zyte_api"] = {
					"session": {"id": zyte_session},
					"httpResponseHeaders": True,
				}
			if original_meta.get("download_slot"):
				upstream_meta["download_slot"] = original_meta["download_slot"]

			body = None
			if event.get("body_b64"):
				try:
					body = base64.b64decode(event["body_b64"])
				except Exception as e:
					logger.warning(f"need_fetch body_b64 nicht dekodierbar: {e!r}")

			yield scrapy.Request(
				url=event["url"],
				method=event.get("method", "GET"),
				headers=event.get("headers") or {},
				body=body,
				callback=self._on_upstream_fetched,
				errback=self._on_upstream_failed,
				dont_filter=True,
				meta=upstream_meta,
			)
			return

		if state == "done":
			original_meta = loop.get("original_meta") or {}
			jar_id = original_meta.get("jar_id")
			cookies = event.get("cookies") or []
			n = HeadlessClient.inject_cookies_into_jar(self, jar_id, cookies) if jar_id else 0
			logger.info(
				f"headless done: fetches={event.get('fetch_count')} "
				f"duration={event.get('duration_s')}s status={event.get('status')} "
				f"cookies={n} → reissue {loop.get('original_url')}"
			)
			retry = self._reissue_original(loop)
			if retry is not None:
				yield retry
			return

		if state == "error":
			logger.error(
				f"headless error: code={event.get('code')} "
				f"msg={event.get('message')} loop={loop.get('original_url')}"
			)
			return

		logger.warning(f"headless: unbekannter state={state!r}, ignoriere")

	def _on_upstream_fetched(self, response):
		"""Antwort auf einen need_fetch-Upstream-Request → ans Subsystem
		zurückgeben."""
		event = response.meta.get("_headless_event")
		loop = response.meta.get("_headless_loop")
		if not event or not loop:
			logger.error("_on_upstream_fetched ohne Loop-State — Abbruch")
			return
		logger.info(
			f"upstream-fetched status={response.status} "
			f"len={len(response.body or b'')} → feed req={event.get('req_id','')[:8]}"
		)
		yield self.headless.feed_request(
			event=event,
			upstream_response=response,
			callback=self._on_headless_event,
			errback=self._on_headless_failed,
			extra_meta=loop,
		)

	def _on_upstream_failed(self, failure):
		"""Upstream-Fetch ist gescheitert (DNS, TCP, ...). Subsystem
		informieren, damit es die Session sauber beendet."""
		request = failure.request
		event = request.meta.get("_headless_event")
		loop = request.meta.get("_headless_loop") or {}
		err = f"{failure.type.__name__}: {failure.getErrorMessage()[:120]}"
		logger.warning(f"upstream errback: {err}")
		if not event:
			logger.error("upstream errback ohne Event — Abbruch")
			return
		return self.headless.feed_error_request(
			event=event,
			error=err,
			callback=self._on_headless_event,
			errback=self._on_headless_failed,
			extra_meta=loop,
		)

	def _on_headless_failed(self, failure):
		"""Subsystem-Call selbst (start/feed) ist HTTP-mässig gescheitert.
		Dann lassen wir den Auftrag fallen — kein verstecktes Wiederholen,
		um nicht in Endlosschleifen zu geraten."""
		err = failure.getErrorMessage()
		req = failure.request
		loop = req.meta.get("_headless_loop") or {}
		logger.error(
			f"headless subsystem call failed: {err} "
			f"original_url={loop.get('original_url')!r}"
		)
		return

	def _reissue_original(self, loop):
		"""Baut den Original-Request neu — die in den Lane-Jar injizierten
		Imperva-Cookies werden von der CookiesMiddleware automatisch
		mitgeschickt."""
		original_meta = loop.get("original_meta") or {}
		cb_name = loop.get("original_callback")
		callback = getattr(self, cb_name, None) if cb_name else None
		if callback is None:
			logger.error(
				f"_reissue_original: original_callback {cb_name!r} "
				f"nicht auflösbar — verwerfe"
			)
			return None
		body = None
		if loop.get("original_body_b64"):
			try:
				body = base64.b64decode(loop["original_body_b64"])
			except Exception:
				body = None
		return scrapy.Request(
			url=loop["original_url"],
			method=loop.get("original_method", "GET"),
			headers=loop.get("original_headers") or {},
			body=body,
			callback=callback,
			dont_filter=True,
			meta=dict(original_meta),
		)
