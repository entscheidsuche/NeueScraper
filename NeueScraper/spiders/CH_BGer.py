# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.headless_client import HeadlessClient
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
from urllib.parse import quote
import random
import os, base64, hashlib, time
import uuid
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from twisted.internet import reactor


logger = logging.getLogger(__name__)

class CH_BGer(BasisSpider):
	name = 'CH_BGer'

	INITIAL_URL='/sitemaps/sitemapindex.xml'
	HOST='http://relevancy.bger.ch'

	HEADER={
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
		'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
		'Accept-Encoding': 'gzip, deflate, br, zstd',
		'DNT': '1',
		'Connection': 'keep-alive',
		'Referer': 'https://search.bger.ch/ext/eurospider/live/de/php/clir/http/index.php',
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
	
	custom_settings = {
    "DOWNLOAD_DELAY": 0,
    "RANDOMIZE_DOWNLOAD_DELAY": False,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 8,
    "CONCURRENT_REQUESTS": 64,
    # AutoThrottle DEAKTIVIERT: relevancy.bger.ch antwortet auf Überlast mit
    # 429 binnen ~50ms — AutoThrottle interpretiert das als "schnell, mehr
    # Last möglich" und beschleunigt genau falsch. Wir drosseln per Hand.
    "AUTOTHROTTLE_ENABLED": False,
    "ZYTE_API_MAX_REQUESTS": 16,
    "RETRY_TIMES": 1,
    # Sitemap- und Document-Requests in getrennte Slots:
    # - 'bger_sitemap': sehr serverseitig-teuer (Jahres-XML mit allen IDs),
    #   sequentiell mit 3s Pause zwischen Jahren
    # - 'bger_doc':     pro Request billig, aber das Backend rate-limitet
    #   global-pro-URL (nicht pro IP), deshalb harte Drossel und keine
    #   AutoThrottle, die 429 falsch lesen würde.
    "DOWNLOAD_SLOTS": {
        "bger_sitemap": {"concurrency": 1, "delay": 3.0, "throttle": False},
        # Startwert für bger_doc: 8 parallel, 0.2s Tickrate.
        # Das tatsächliche Tempo wird zur Laufzeit per _on_throttle_event
        # adaptiv nachgezogen — bei 429 verlangsamen, bei Erfolgs-Streak
        # wieder beschleunigen. throttle=False, weil AutoThrottle den 429
        # nicht erkennt (kommt zu schnell zurück).
        "bger_doc":     {"concurrency": 8, "delay": 0.2, "throttle": False},
    },
}

	MAX_VERSUCHE = 10
	RETRY_STATUS = (502, 429)
	# Geometrisches Backoff: vor Versuch 2 = MIN, vor Versuch MAX_VERSUCHE = MAX
	RETRY_DELAY_MIN = 5     # Sekunden vor dem ersten Retry
	RETRY_DELAY_MAX = 100   # Sekunden vor dem letzten Retry

	# Header-Rotation – pro Request zufällig, unabhängig von der IP/Session.
	USER_AGENTS = [
		'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0',
		'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
		'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
		'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
		'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
	]
	ACCEPT_LANGUAGES = [
		'de,en-US;q=0.7,en;q=0.3',
		'de-CH,de;q=0.9,en;q=0.7,fr;q=0.6',
		'fr-CH,fr;q=0.9,de;q=0.7,en;q=0.5',
		'it-CH,it;q=0.9,de;q=0.7,en;q=0.5',
		'de-DE,de;q=0.9,en;q=0.5',
		'en-US,en;q=0.9,de;q=0.7',
	]

	reAZA=re.compile(r"sitemap_aza_(?P<Jahr>[12][90][0-9][0-9])\.xml$")
	reID=re.compile(r"JumpCGI\?id=(?P<ID>(?P<DATUM>\d\d\.\d\d\.\d\d\d\d)_(?P<NUM>[-_0-9A-Z]+/[12][90]\d\d))\s*$")
	
	# Adaptive Throttle-Konfiguration für bger_doc (AIMD-artig):
	# - Bei 429:  desired_delay × SLOWDOWN_FACTOR (cap auf MAX)
	# - Bei 200:  desired_delay × SPEEDUP_PER_OK (floor auf MIN, jeder Erfolg
	#   knabbert ein bisschen ab — keine Counter, keine Resets)
	# Der globale Zustand wird dann auf ALLE laufenden Slots geschrieben, deren
	# Key mit dem logischen Namen beginnt — scrapy-zyte-api legt pro Session
	# einen eigenen Slot an, sodass per-Slot-Speicher nicht reicht.
	ADAPTIVE_DELAY_MIN = 0.1
	ADAPTIVE_DELAY_MAX = 10.0
	ADAPTIVE_SLOWDOWN_FACTOR = 1.5
	ADAPTIVE_SPEEDUP_PER_OK = 0.99    # 1% pro Erfolg
	ADAPTIVE_SPEEDUP_LOG_EVERY = 200  # alle N Erfolge eine OK-Logzeile

	# Initial-Delays der adaptiven Slots — ab hier läuft das System eigenständig
	_INITIAL_DESIRED_DELAYS = {
		'bger_doc': 0.2,
	}

	# ab und bis nur in Jahreszahlen
	def __init__(self, ab=None, neu=None, bis=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		self.bis=bis
		self._pending_retries = 0  # offene verzögerte Retries
		self._consecutive_ok = 0   # nur für gelegentliches OK-Logging
		self._desired_delays = dict(self._INITIAL_DESIRED_DELAYS)
		self.request_gen = self.request_generator(ab, bis)

	@classmethod
	def from_crawler(cls, crawler, *args, **kwargs):
		spider = super().from_crawler(crawler, *args, **kwargs)
		crawler.signals.connect(spider._on_spider_idle, signal=signals.spider_idle)
		return spider

	def _on_spider_idle(self):
		"""Solange noch verzögerte Retries ausstehen, Spider nicht schliessen."""
		if self._pending_retries > 0:
			logger.info(f"spider_idle: {self._pending_retries} verzögerte Retries offen, Spider bleibt offen.")
			raise DontCloseSpider

	def request_generator(self,ab=None,bis=None):
		if ab:
			self.ab=ab
		else:
			self.ab=None

		if bis:
			self.bis=bis
		else:
			self.bis=None

		return [self._make_request(self.HOST+self.INITIAL_URL, self.parse_sitemap, kontext='Sitemap-Index', slot='bger_sitemap')]

	def _new_session_id(self):
		"""Neue Zyte-API-Session-ID pro Request (keine Sticky-Sessions)."""
		return uuid.uuid4().hex

	def _random_header(self, versuch=1):
		"""Header-Set pro Request: rotierender User-Agent + Accept-Language.
		Auf Retries (versuch > 1) wird zusätzlich der Referer weggelassen."""
		h = dict(self.HEADER)
		h['User-Agent'] = random.choice(self.USER_AGENTS)
		h['Accept-Language'] = random.choice(self.ACCEPT_LANGUAGES)
		if versuch > 1:
			h.pop('Referer', None)
		return h

	def _matching_slots(self, slot_name):
		"""Liefert alle aktiven Download-Slots, deren Key zum logischen Namen
		gehört. scrapy-zyte-api legt pro Session einen eigenen Slot an
		('bger_doc/<sessionhash>' o.ä.) — wir wenden unseren globalen
		Throttle-Zustand auf alle passenden Instanzen an."""
		try:
			slots_dict = self.crawler.engine.downloader.slots
		except Exception:
			return []
		out = []
		for key, slot in list(slots_dict.items()):
			if key == slot_name or key.startswith(slot_name + '/') \
			   or key.startswith(slot_name + '@') or key.startswith(slot_name + '#'):
				out.append((key, slot))
		return out

	def _apply_desired_delay(self, slot_name):
		"""Schreibt _desired_delays[slot_name] auf alle passenden Slot-Instanzen."""
		desired = self._desired_delays.get(slot_name)
		if desired is None:
			return 0
		applied = 0
		for _key, slot in self._matching_slots(slot_name):
			if abs(slot.delay - desired) > 0.001:
				slot.delay = desired
				applied += 1
		return applied

	def _on_throttle_event(self, slot_name, was_429):
		"""AIMD-Reaktion auf Throttle-relevante Responses, global pro
		logischem Slot. ``was_429=True`` verlangsamt multiplikativ;
		``was_429=False`` lässt jeden Erfolg ein bisschen vom Desired-Delay
		abknabbern. Der neue Wunschwert wird auf alle existierenden
		Slot-Instanzen geschrieben (scrapy-zyte-api hat ggf. viele)."""
		old = self._desired_delays.get(slot_name)
		if old is None:
			return
		if was_429:
			# Multiplikative Erhöhung; falls Delay extrem klein war, mindestens
			# auf MIN×FACTOR springen, damit der Effekt spürbar ist.
			base = max(old, self.ADAPTIVE_DELAY_MIN)
			new = min(base * self.ADAPTIVE_SLOWDOWN_FACTOR, self.ADAPTIVE_DELAY_MAX)
			if new > old:
				self._desired_delays[slot_name] = new
				self._consecutive_ok = 0
				applied = self._apply_desired_delay(slot_name)
				logger.warning(
					f"Throttle 429 ({slot_name}): desired {old:.2f}s → {new:.2f}s "
					f"(angewandt auf {applied} Slot-Instanz(en))"
				)
		else:
			self._consecutive_ok += 1
			new = max(old * self.ADAPTIVE_SPEEDUP_PER_OK, self.ADAPTIVE_DELAY_MIN)
			if new < old - 0.001:
				self._desired_delays[slot_name] = new
				self._apply_desired_delay(slot_name)
			# Logging im Erfolgsfall sparsam — nur alle N Erfolge eine Zeile
			if self._consecutive_ok % self.ADAPTIVE_SPEEDUP_LOG_EVERY == 0:
				current = self._desired_delays[slot_name]
				logger.info(
					f"Throttle OK x{self._consecutive_ok} ({slot_name}): "
					f"desired {current:.2f}s"
				)

	@property
	def headless(self):
		"""HeadlessClient mit Settings aus dem Crawler. Lazy initialisiert."""
		client = getattr(self, "_headless_client", None)
		if client is None:
			client = HeadlessClient.from_settings(self.settings)
			self._headless_client = client
			if client.is_enabled():
				logger.info("HeadlessClient aktiv: %s", client.base_url)
			else:
				logger.warning("HeadlessClient deaktiviert (HEADLESS-Token fehlt)")
		return client

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

	def _retry_delay(self, versuch):
		"""Geometrisches Backoff zwischen RETRY_DELAY_MIN und RETRY_DELAY_MAX.
		versuch ist die gerade fehlgeschlagene Versuchsnummer (1-indexiert).
		versuch=1 -> RETRY_DELAY_MIN, versuch=MAX_VERSUCHE-1 -> RETRY_DELAY_MAX."""
		n = self.MAX_VERSUCHE - 1  # mögliche Retries (zwischen Versuch 1..MAX)
		if n <= 1:
			return float(self.RETRY_DELAY_MIN)
		i = max(1, min(versuch, n))
		exponent = (i - 1) / (n - 1)
		ratio = (self.RETRY_DELAY_MAX / self.RETRY_DELAY_MIN) ** exponent
		return float(self.RETRY_DELAY_MIN) * ratio

	def _make_request(self, url, callback, kontext, versuch=1, item=None,
	                  extra_meta=None, slot='bger_doc'):
		"""Request mit eigener frischer Zyte-Session und rotierendem Header;
		502/429 kommen als Status direkt in den Callback (handle_httpstatus_list),
		Standard-Retry deaktiviert. extra_meta erlaubt es, zusätzliche Felder
		(z.B. 'remaining_years') durchzureichen, die der Retry-Pfad bewahrt.

		``slot`` weist den Request einem der DOWNLOAD_SLOTS zu — 'bger_sitemap'
		für die teuren Jahres-XMLs (sequentiell mit 3s Pause), 'bger_doc' für
		alles andere (parallel, mit AutoThrottle)."""
		session_id = self._new_session_id()
		header = self._random_header(versuch=versuch)
		meta = {
			'kontext': kontext,
			'versuch': versuch,
			'session_id': session_id,
			'zyte_api': {'session': {'id': session_id}, 'httpResponseHeaders': True},
			'handle_httpstatus_list': list(self.RETRY_STATUS),
			'dont_retry': True,
			'download_slot': slot,
		}
		if item is not None:
			meta['item'] = item
		if extra_meta:
			meta.update(extra_meta)
		logger.info(
			f"Request {kontext} Versuch={versuch} slot={slot} session={session_id} "
			f"UA={header['User-Agent'][:40]}... url={url}"
		)
		return scrapy.Request(
			url=url, headers=header,
			callback=callback, errback=self.errback_retry,
			dont_filter=True, meta=meta,
		)

	def _maybe_retry_status(self, response, kontext_prefix):
		"""True = Status führte zu (verzögertem) Retry oder Verwerfen, Aufrufer
		soll abbrechen. False = Status ok, normal weiterverarbeiten."""
		if response.status in self.RETRY_STATUS:
			# Adaptive Drossel: bei 429 den zugehörigen Slot verlangsamen
			# (502 ist meist Server-Hicks, nicht Throttle — dort nicht eingreifen)
			if response.status == 429:
				self._on_throttle_event(
					response.meta.get('download_slot', 'bger_doc'),
					was_429=True,
				)
			self._retry_request(response, f"{response.status} auf {kontext_prefix}")
			return True
		return False

	def _schedule_retry(self, url, callback, kontext, versuch, item, grund,
	                    extra_meta=None, slot='bger_doc', retry_after=None):
		"""Plant einen verzögerten Retry oder verwirft endgültig.
		Gibt True zurück, wenn ein Retry geplant wurde, sonst False.
		extra_meta wird an den neuen Request weitergereicht (z.B. 'remaining_years').
		slot bestimmt, in welchem Download-Slot der Retry läuft — wir bewahren
		den Slot des Originals, damit Sitemap-Retries nicht versehentlich in
		den schnellen Doc-Slot rutschen.
		retry_after (in Sekunden, falls vom Server gesendet) übersteuert die
		geometrische Backoff-Reihe — wir gehorchen dem Server."""
		if versuch >= self.MAX_VERSUCHE:
			logger.error(f"{kontext} nach {versuch} Versuchen verworfen ({grund}).")
			return False
		new_versuch = versuch + 1
		if retry_after is not None and retry_after > 0:
			delay = min(float(retry_after), 600.0)  # Cap bei 10 min, falls Server irre Werte schickt
			delay_src = "Retry-After"
		else:
			delay = self._retry_delay(versuch)
			delay_src = "backoff"
		logger.warning(
			f"{kontext} Versuch {versuch} fehlgeschlagen ({grund}); "
			f"Retry in {delay:.1f}s ({delay_src}) als Versuch {new_versuch}."
		)
		new_req = self._make_request(
			url=url, callback=callback, kontext=kontext,
			versuch=new_versuch, item=item, extra_meta=extra_meta, slot=slot,
		)
		self._pending_retries += 1
		reactor.callLater(delay, self._fire_retry, new_req, kontext, new_versuch)
		return True

	def _retry_after_from_response(self, response):
		"""Liest Retry-After aus den Response-Headern, falls vorhanden.
		Liefert eine Float-Sekundenzahl oder None. Akzeptiert reine
		Sekunden-Angaben (RFC 7231 erlaubt auch HTTP-Date — das ignorieren wir
		hier; Server liefern in der Praxis fast immer Sekunden)."""
		try:
			raw = response.headers.get(b'Retry-After')
		except Exception:
			return None
		if not raw:
			return None
		try:
			value = raw.decode('latin1').strip()
		except Exception:
			return None
		try:
			seconds = float(value)
			if seconds < 0:
				return None
			return seconds
		except ValueError:
			# Wäre HTTP-Date — ignorieren
			return None

	def _fire_retry(self, request, kontext, versuch):
		"""Wird vom Reactor aufgerufen, wenn die Retry-Wartezeit abgelaufen ist."""
		self._pending_retries = max(0, self._pending_retries - 1)
		logger.info(f"{kontext} Versuch {versuch}: gebe Retry-Request frei (offene Retries: {self._pending_retries}).")
		try:
			self.crawler.engine.crawl(request)
		except Exception as e:
			logger.error(f"{kontext} Retry konnte nicht eingeplant werden: {e!r}")

	# Meta-Keys, die beim Retry erhalten bleiben sollen (z.B. die Jahres-Kette).
	_PRESERVED_META_KEYS = ('remaining_years',)

	def _preserved_meta(self, meta):
		"""Filtert aus einem Meta-Dict die Keys, die der Retry weiterreichen muss."""
		if not meta:
			return None
		out = {k: meta[k] for k in self._PRESERVED_META_KEYS if k in meta}
		return out or None

	def _retry_request(self, response, grund):
		"""Plant einen verzögerten Retry für einen Response."""
		self._schedule_retry(
			url=response.url,
			callback=response.request.callback,
			kontext=response.meta.get('kontext', response.url),
			versuch=response.meta.get('versuch', 1),
			item=response.meta.get('item'),
			grund=grund,
			extra_meta=self._preserved_meta(response.meta),
			slot=response.meta.get('download_slot', 'bger_doc'),
			retry_after=self._retry_after_from_response(response),
		)
		# Aufrufer erwartet None (= nichts mehr yielden), Retry läuft asynchron.
		return None

	def errback_retry(self, failure):
		"""Errback: bei Verbindungs-/Timeout-Fehlern Retry mit neuer Session."""
		self.errback_httpbin(failure)
		request = failure.request
		self._schedule_retry(
			url=request.url,
			callback=request.callback,
			kontext=request.meta.get('kontext', request.url),
			versuch=request.meta.get('versuch', 1),
			item=request.meta.get('item'),
			grund=f"errback {failure.type.__name__}",
			extra_meta=self._preserved_meta(request.meta),
			slot=request.meta.get('download_slot', 'bger_doc'),
		)

	def parse_sitemap(self, response):
		if self._maybe_retry_status(response, "Sitemap-Index"):
			return
		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_sitemap: Imperva-Challenge erkannt "
				f"(status={response.status} len={len(self._safe_response_text(response) or '')}), "
				f"delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_sitemap,
				original_meta=response.meta,
			)
			return
		antwort=self._safe_response_text(response)
		logger.info("parse_sitemap Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_sitemap Rohergebnis: "+antwort[:30000])
		entries=response.xpath('//*[local-name()="loc"]/text()').getall()
		if not entries:
			logger.info("keine Einträge in der Sitemap gefunden: "+antwort)
			return

		# Jahres-Sitemap-URLs nach Jahr aufsteigend sammeln, gefiltert nach ab/bis.
		years = []
		for entry in entries:
			aza = self.reAZA.search(entry)
			if not aza:
				continue
			jahr = int(aza.group('Jahr'))
			if (self.ab and int(self.ab) > jahr) or (self.bis and int(self.bis) < jahr):
				logger.info(f"Gefunden {entry}. {jahr} ist nicht im Intervall von {self.ab} - {self.bis}")
				continue
			years.append((jahr, entry))
		years.sort(key=lambda t: t[0])

		if not years:
			logger.info("keine Jahres-Sitemap-URLs nach Filter übrig.")
			return

		first_jahr, first_url = years[0]
		remaining = years[1:]
		logger.info(f"Sitemap-Index: {len(years)} Jahres-Sitemaps gefunden, starte sequentiell mit Jahr {first_jahr}.")
		yield self._make_request(
			first_url, self.parse_jahressitemap,
			kontext=f"Jahres-Sitemap {first_jahr}",
			extra_meta={'remaining_years': remaining},
			slot='bger_sitemap',
		)

	def parse_jahressitemap(self, response):
		if self._maybe_retry_status(response, "Jahres-Sitemap"):
			return
		# Imperva-Challenge erkennen → Subsystem-Loop
		if self.headless.is_enabled() and self.headless.is_imperva_challenge(response):
			logger.warning(
				f"parse_jahressitemap: Imperva-Challenge erkannt "
				f"(status={response.status} len={len(self._safe_response_text(response) or '')}), "
				f"delegiere an Subsystem"
			)
			yield self.headless.start_request(
				response=response,
				callback=self._on_headless_event,
				errback=self._on_headless_failed,
				original_callback=self.parse_jahressitemap,
				original_meta=response.meta,
			)
			return

		# Nächste Jahres-Sitemap einreihen, falls noch welche ausstehen.
		remaining = response.meta.get('remaining_years') or []
		if remaining:
			next_jahr, next_url = remaining[0]
			logger.info(f"Reihe Jahres-Sitemap {next_jahr} ein (noch {len(remaining)} ausstehend).")
			yield self._make_request(
				next_url, self.parse_jahressitemap,
				kontext=f"Jahres-Sitemap {next_jahr}",
				extra_meta={'remaining_years': remaining[1:]},
				slot='bger_sitemap',
			)

		antwort=self._safe_response_text(response)
		logger.info("parse_jahressitemap Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_jahressitemap Rohergebnis: "+antwort[:30000])
		entries=response.xpath('//*[local-name()="loc"]/text()').getall()
		if entries==None:
			logger.info("keine Einträge in der Jahres-Sitemap gefunden: "+antwort)
		else:
			for entry in entries:
				item={}
				link=entry
				meta=self.reID.search(link)
				if meta:
					item['DocID']=PH.NC(meta.group("ID"),error="keine DokumentID in "+link)
					item['Num']=PH.NC(meta.group("NUM"),error="keine Geschäftsnummer in "+link)
					item['EDatum']=PH.NC(self.norm_datum(meta.group("DATUM")),error="kein Datum in "+link)
					item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
					item['HTMLUrls']=[link]
					yield self._make_request(link, self.parse_document, kontext=f"Dokument {item['DocID']}", item=item)
				else:
					logger.error(f"konnte {link} nicht zerlegen")

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status)+" for "+response.request.url)
		if self._maybe_retry_status(response, "Dokument"):
			return
		# Erfolg → Throttle-Speedup-Event auf bger_doc
		self._on_throttle_event(
			response.meta.get('download_slot', 'bger_doc'),
			was_429=False,
		)
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
		logger.info("parse_document Rohergebnis: "+antwort[:30000])

		item=response.meta['item']
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:30000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)

	# ------------------------------------------------------------------
	# Headless-Subsystem Loop (Imperva-Challenge-Solver)
	#
	# BGer-Variante: keine Lane-Jars; stattdessen werden die vom Browser
	# erworbenen Cookies beim Re-Issue per `cookies={...}`-Parameter
	# direkt am Original-Request angehängt (Per-Request-Scope).
	# Über die ganze Solve-Sequenz hinweg bleibt die Zyte-Session-ID
	# aus original_meta erhalten, damit IP / Browserprofil / Cookies
	# atomar zusammenpassen.
	# ------------------------------------------------------------------
	def _on_headless_event(self, response):
		"""Antwort des Subsystems (auf /start oder /feed). Verzweigt in
		need_fetch / done / error."""
		event = self.headless.parse_event(response)
		state = event.get("state")
		loop = (response.meta.get("_headless_loop") or {}).copy()

		if state == "need_fetch":
			loop["session_id"] = event.get("session_id")
			loop["fetch_count"] = int(loop.get("fetch_count", 0)) + 1
			logger.info(
				f"headless need_fetch #{loop['fetch_count']} "
				f"sess={(event.get('session_id') or '')[:8]} → {event.get('url')}"
			)

			original_meta = loop.get("original_meta") or {}
			zyte_session = (original_meta.get("zyte_api") or {}).get("session", {}).get("id")
			upstream_meta = {
				"_headless_loop": loop,
				"_headless_event": event,
				"dont_redirect": True,
				"handle_httpstatus_all": True,
				"dont_merge_cookies": True,
				"dont_retry": True,   # eigene Retry-Logik nicht stören
			}
			if zyte_session:
				upstream_meta["zyte_api"] = {
					"session": {"id": zyte_session},
					"httpResponseHeaders": True,
				}

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
			cookies = event.get("cookies") or []
			logger.info(
				f"headless done: fetches={event.get('fetch_count')} "
				f"duration={event.get('duration_s')}s status={event.get('status')} "
				f"cookies={len(cookies)} → reissue {loop.get('original_url')}"
			)
			retry = self._reissue_original(loop, cookies)
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
			f"len={len(response.body or b'')} → feed req={(event.get('req_id') or '')[:8]}"
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
		Wir lassen den Auftrag fallen — kein verstecktes Wiederholen."""
		err = failure.getErrorMessage()
		req = failure.request
		loop = req.meta.get("_headless_loop") or {}
		logger.error(
			f"headless subsystem call failed: {err} "
			f"original_url={loop.get('original_url')!r}"
		)
		return

	def _reissue_original(self, loop, cookies):
		"""Baut den Original-Request neu — selbe Zyte-Session, selbe Header,
		PLUS die vom Browser empfangenen Imperva-Cookies als Per-Request-
		Cookies. Damit IP/Profil/Cookies atomar zusammenpassen, ohne den
		globalen Default-Jar zu verschmutzen."""
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
		# Cookies in Scrapys cookies={}-Format umwandeln (Per-Request-Scope,
		# kein Default-Jar — passt zum BGer per-Request-Modell).
		cookies_dict = {}
		for c in (cookies or []):
			name = c.get("name")
			value = c.get("value")
			if name and value is not None:
				cookies_dict[name] = value
		# Original-Meta inkl. Zyte-Session/Header/Item bewahren; Loop-State
		# fliegt raus (wäre Müll für den eigentlichen Parser).
		new_meta = dict(original_meta)
		new_meta.pop("_headless_loop", None)
		new_meta.pop("_headless_event", None)
		# dont_merge_cookies = False — wir wollen, dass Scrapy unsere Cookies
		# tatsächlich an den Request anhängt, nicht aus jar=0 ergänzt.
		new_meta["dont_merge_cookies"] = True
		return scrapy.Request(
			url=loop["original_url"],
			method=loop.get("original_method", "GET"),
			headers=loop.get("original_headers") or {},
			body=body,
			cookies=cookies_dict if cookies_dict else None,
			callback=callback,
			errback=self.errback_retry,
			dont_filter=True,
			meta=new_meta,
		)
