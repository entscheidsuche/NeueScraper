# -*- coding: utf-8 -*-
"""Spider-seitiger Adapter für das headless-scraping-subsystem.

Architektur (Erinnerung):
    Scrapy Spider                       FastAPI / Playwright              Imperva
    -------------                       --------------------              -------
    GET <ziel>                  ----->                                    403 + Challenge
                                <-----  (Spider sieht 403 / Mini-Body)

    POST /headless/challenge/start
       {url, cookies, ua}       ----->  öffnet BrowserContext, navigiert
                                <-----  200 NeedFetch {req_id, url, headers, ...}
    (Spider macht Scrapy-Request
     auf url MIT zyte_api-Session
     der Lane → gleiche Egress-IP
     wie der Original-Request)
                                ----->  bger.ch / imperva
                                <-----  upstream response
    POST /headless/challenge/feed/{req_id}
       {status, headers, body}  ----->
                                <-----  200 NeedFetch (nächster Subrequest)
                                        ... loop ...
                                <-----  200 ChallengeDone {html, cookies, ...}

    Cookies aus 'done' werden in den Lane-Jar injiziert; der Original-Request
    wird neu yielded — Scrapy/CookiesMiddleware schickt die Imperva-Cookies
    dann automatisch mit.

Nutzung im Spider (Skizze, vollständig in CH_BGE.py):

    from NeueScraper.headless_client import HeadlessClient

    class Spider:
        def __init__(self, ...):
            self.headless = HeadlessClient.from_settings(self.settings)

        def parse_trefferliste(self, response):
            if self.headless.is_imperva_challenge(response):
                yield self.headless.start_request(
                    response=response,
                    callback=self._on_headless_event,
                    errback=self._on_headless_failed,
                    original_callback=self.parse_trefferliste,
                    original_meta=response.meta,
                )
                return
            # ... normale Verarbeitung ...

Module exportiert eine ``HeadlessClient``-Klasse — keine globalen Zustände.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional

import scrapy

logger = logging.getLogger(__name__)


# Erkennungsmuster für Imperva (Incapsula). Werden auf den Response-Body
# (Text-Form) angewandt, wenn Status oder Bodygrösse verdächtig sind.
_IMPERVA_PATTERNS = (
	re.compile(r"_Incapsula_Resource", re.IGNORECASE),
	re.compile(r"Incapsula\s+incident", re.IGNORECASE),
	re.compile(r"<iframe[^>]+_Incapsula_Resource", re.IGNORECASE),
)


# Default-Subsystem-URL. Lässt sich pro Deployment überschreiben:
#   - via Scrapy-Setting HEADLESS_BASE
#   - oder konstruktor-Argument base_url
DEFAULT_HEADLESS_BASE = "https://files.entscheidsuche.ch/headless"


class HeadlessClient:
	"""Hilfsobjekt zum Aufbau der Subsystem-Requests.

	Das Modul macht *keine* I/O selbst — es liefert ``scrapy.Request``-Objekte,
	die der Spider yielded. Damit bleibt das Scrapy-Concurrency-Modell unberührt
	und Zyte-Sessions werden korrekt durchgereicht.
	"""

	def __init__(self, base_url: str, token: str):
		self.base_url = base_url.rstrip("/")
		self.token = token

	# ------------------------------------------------------------------
	# Konstruktion
	# ------------------------------------------------------------------
	@classmethod
	def from_settings(cls, settings) -> "HeadlessClient":
		"""Liest BASE_URL und Token aus Scrapy-Settings.

		HEADLESS_BASE  – Subsystem-Basis-URL (default DEFAULT_HEADLESS_BASE)
		HEADLESS       – Bearer-Token (Pflicht; ohne Token wird der Spider
		                 ohne Subsystem-Fallback laufen — is_enabled()=False)
		"""
		base = settings.get("HEADLESS_BASE", DEFAULT_HEADLESS_BASE)
		token = settings.get("HEADLESS") or ""
		return cls(base_url=base, token=token)

	def is_enabled(self) -> bool:
		return bool(self.token)

	# ------------------------------------------------------------------
	# Detection
	# ------------------------------------------------------------------
	@staticmethod
	def is_imperva_challenge(response) -> bool:
		"""Erkennt eine Imperva-Challenge-Seite.

		Trigger:
		  1. HTTP 403 mit '_Incapsula_Resource' / 'Incapsula incident' im Body.
		  2. Mini-Body (< 5 KB) mit '_Incapsula_Resource'-Marker. Decken die
		     200er-JS-Challenges ab, die Imperva als „Klick-mich-ich-bin-OK"
		     ausspielt.
		"""
		try:
			body = response.text or ""
		except (AttributeError, Exception):
			# Bei Responses ohne Text-Decoder (z.B. unbekannter Charset)
			# auf utf-8/replace zurückfallen, statt mit Exception zu fliegen.
			try:
				body = (response.body or b"").decode("utf-8", errors="replace")
			except Exception:
				body = ""
		# Gross-/Klein und kompakte Bodies abgleichen
		if response.status == 403:
			for p in _IMPERVA_PATTERNS:
				if p.search(body):
					return True
		# Mini-Body, typisch < 2 KB; wir lassen 5 KB als Sicherheitspuffer.
		if len(body) < 5000:
			for p in _IMPERVA_PATTERNS:
				if p.search(body):
					return True
		return False

	# ------------------------------------------------------------------
	# Request-Builder
	# ------------------------------------------------------------------
	def _auth_headers(self) -> Dict[str, str]:
		return {
			"Authorization": f"Bearer {self.token}",
			"Content-Type": "application/json",
		}

	def start_request(
		self,
		response,
		callback: Callable,
		errback: Optional[Callable] = None,
		original_callback: Optional[Callable] = None,
		original_meta: Optional[Dict[str, Any]] = None,
		correlation_id: Optional[str] = None,
		extra_meta: Optional[Dict[str, Any]] = None,
	) -> scrapy.Request:
		"""Baut den ``POST /headless/challenge/start``-Request.

		``response`` ist die Spider-Antwort, in der die Challenge erkannt wurde.
		Daraus zieht die Methode URL, UA und ggf. bereits empfangene Cookies.

		``original_callback`` und ``original_meta`` werden in den Loop-Meta
		mitgeführt, damit der Spider nach 'done' den Original-Request neu
		yielden kann.
		"""
		cookies = self._cookies_from_response(response)
		ua = (response.request.headers.get(b"User-Agent")
		      or b"").decode("latin1") if response.request else ""

		body_b64 = ""
		if response.request and response.request.body:
			body_b64 = base64.b64encode(response.request.body).decode("ascii")

		headers_in = self._headers_from_request(response.request) if response.request else {}

		payload = {
			"url": response.url,
			"method": response.request.method if response.request else "GET",
			"headers": headers_in,
			"body_b64": body_b64 or None,
			"cookies": cookies,
			"user_agent": ua or None,
			"correlation_id": correlation_id or uuid.uuid4().hex,
		}

		meta = {
			# Subsystem-Calls gehen DIREKT, NICHT über Zyte (kein zyte_api).
			"dont_redirect": True,
			"handle_httpstatus_all": True,
			# Kontext für die Loop-Callbacks
			"_headless_loop": {
				"original_url": response.url,
				"original_method": response.request.method if response.request else "GET",
				"original_headers": headers_in,
				"original_body_b64": body_b64,
				"original_meta": _safe_meta(original_meta or response.meta),
				"original_callback": _callback_name(original_callback),
				"correlation_id": payload["correlation_id"],
				"session_id": None,
				"fetch_count": 0,
			},
		}
		if extra_meta:
			meta.update(extra_meta)

		return scrapy.Request(
			url=f"{self.base_url}/challenge/start",
			method="POST",
			headers=self._auth_headers(),
			body=json.dumps(payload).encode("utf-8"),
			callback=callback,
			errback=errback,
			dont_filter=True,
			meta=meta,
		)

	def feed_request(
		self,
		event: Dict[str, Any],
		upstream_response,
		callback: Callable,
		errback: Optional[Callable] = None,
		extra_meta: Optional[Dict[str, Any]] = None,
	) -> scrapy.Request:
		"""Baut den ``POST /headless/challenge/feed/{req_id}``-Request.

		``event`` ist das vorausgegangene NeedFetch-Event (mit ``req_id`` /
		``session_id``). ``upstream_response`` ist die Scrapy-Antwort des
		gerade durchgeführten Upstream-Fetches.
		"""
		body_b64 = base64.b64encode(upstream_response.body or b"").decode("ascii")
		feed = {
			"status": int(upstream_response.status),
			"headers": _headers_to_dict(upstream_response.headers),
			"body_b64": body_b64,
		}
		req_id = event["req_id"]
		session_id = event["session_id"]
		url = f"{self.base_url}/challenge/feed/{req_id}?session_id={session_id}"

		# Loop-Meta durchreichen
		meta = {
			"dont_redirect": True,
			"handle_httpstatus_all": True,
			"_headless_loop": dict(extra_meta or {}),
		}

		return scrapy.Request(
			url=url,
			method="POST",
			headers=self._auth_headers(),
			body=json.dumps(feed).encode("utf-8"),
			callback=callback,
			errback=errback,
			dont_filter=True,
			meta=meta,
		)

	def feed_error_request(
		self,
		event: Dict[str, Any],
		error: str,
		callback: Callable,
		errback: Optional[Callable] = None,
		extra_meta: Optional[Dict[str, Any]] = None,
	) -> scrapy.Request:
		"""Wenn der Upstream-Fetch fehlschlug, signalisieren wir das dem
		Subsystem über ``feed`` mit ``error`` gesetzt."""
		req_id = event["req_id"]
		session_id = event["session_id"]
		url = f"{self.base_url}/challenge/feed/{req_id}?session_id={session_id}"
		feed = {"status": 0, "headers": {}, "body_b64": "", "error": error}
		meta = {
			"dont_redirect": True,
			"handle_httpstatus_all": True,
			"_headless_loop": dict(extra_meta or {}),
		}
		return scrapy.Request(
			url=url,
			method="POST",
			headers=self._auth_headers(),
			body=json.dumps(feed).encode("utf-8"),
			callback=callback,
			errback=errback,
			dont_filter=True,
			meta=meta,
		)

	# ------------------------------------------------------------------
	# Event-Parsing
	# ------------------------------------------------------------------
	@staticmethod
	def parse_event(response) -> Dict[str, Any]:
		"""Parst eine Subsystem-Antwort zu einem dict mit ``state``-Key.

		Bei Nicht-JSON oder HTTP-Fehler liefert die Methode einen
		``state='error'``-Event mit ``code/message`` damit der Aufrufer
		uniform weiterarbeiten kann.
		"""
		if response.status >= 500 or response.status == 0:
			return {
				"state": "error",
				"code": f"http_{response.status}",
				"message": f"Subsystem antwortete mit Status {response.status}",
			}
		try:
			data = json.loads(response.text)
		except Exception as e:
			return {
				"state": "error",
				"code": "invalid_json",
				"message": f"{type(e).__name__}: {e}",
			}
		if not isinstance(data, dict) or "state" not in data:
			return {
				"state": "error",
				"code": "malformed",
				"message": f"Unerwartetes Subsystem-Format: {response.text[:200]}",
			}
		return data

	# ------------------------------------------------------------------
	# Cookie-Helfer
	# ------------------------------------------------------------------
	@staticmethod
	def _cookies_from_response(response) -> List[Dict[str, Any]]:
		"""Sammelt die für die Domain der Response relevanten Cookies aus
		der Scrapy-CookiesMiddleware."""
		out: List[Dict[str, Any]] = []
		try:
			from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
			spider = response.request.meta.get("_spider_self")
			# Nicht jeder Pfad hat _spider_self gesetzt — als Fallback:
			# über scrapy.utils.misc o.ä. an die Middleware kommen wir
			# zuverlässig nicht. Wir akzeptieren leere Cookies als Fallback;
			# Imperva setzt sie selbst sowieso im Verlauf der Challenge.
			jar_id = response.request.meta.get("cookiejar")
			if spider is None or jar_id is None:
				return out
			cm = next(
				mw for mw in spider.crawler.engine.downloader.middleware.middlewares
				if isinstance(mw, CookiesMiddleware)
			)
			jar = cm.jars.get(jar_id)
			if jar is None:
				return out
			for c in jar:
				out.append({
					"name": c.name,
					"value": c.value,
					"domain": c.domain or "",
					"path": c.path or "/",
				})
		except Exception as e:
			logger.warning("HeadlessClient: cookies_from_response fehlgeschlagen: %r", e)
		return out

	@staticmethod
	def inject_cookies_into_jar(spider, jar_id: str,
	                            cookies: Iterable[Dict[str, Any]]) -> int:
		"""Injiziert die vom Subsystem gelieferten Cookies in den Lane-Jar.

		Liefert die Anzahl tatsächlich gesetzter Cookies. Cookies ohne
		Domain werden ignoriert (Set-Cookie ohne Domain wäre normalerweise
		der Request-Origin; ohne Original-Request Context lassen wir sie weg).
		"""
		try:
			from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
			from http.cookiejar import Cookie
			cm = next(
				mw for mw in spider.crawler.engine.downloader.middleware.middlewares
				if isinstance(mw, CookiesMiddleware)
			)
			jar = cm.jars[jar_id]  # legt Jar bei Bedarf an
		except Exception as e:
			logger.warning("HeadlessClient: konnte Cookie-Jar %s nicht öffnen: %r", jar_id, e)
			return 0

		count = 0
		for c in cookies:
			name = c.get("name")
			value = c.get("value")
			domain = c.get("domain") or ""
			path = c.get("path") or "/"
			if not name or value is None or not domain:
				continue
			cookie = Cookie(
				version=0,
				name=name,
				value=value,
				port=None, port_specified=False,
				domain=domain, domain_specified=bool(domain),
				domain_initial_dot=domain.startswith("."),
				path=path, path_specified=bool(path),
				secure=bool(c.get("secure", False)),
				expires=c.get("expires"),
				discard=False,
				comment=None, comment_url=None,
				rest={},
				rfc2109=False,
			)
			jar.set_cookie(cookie)
			count += 1
		logger.info("HeadlessClient: %d Cookie(s) in jar=%s injiziert", count, jar_id)
		return count

	# ------------------------------------------------------------------
	# Header-Helfer
	# ------------------------------------------------------------------
	@staticmethod
	def _headers_from_request(request) -> Dict[str, str]:
		"""Konvertiert Scrapy-Request-Header in einen einfachen str-dict.

		Wir lassen ``Host``, ``Cookie`` und ``Content-Length`` weg — die
		bestimmt das Subsystem für den simulierten Browser-Request neu.
		"""
		out: Dict[str, str] = {}
		drop = {"host", "cookie", "content-length"}
		for k, v in request.headers.items():
			try:
				kk = k.decode("latin1") if isinstance(k, (bytes, bytearray)) else str(k)
				if kk.lower() in drop:
					continue
				if isinstance(v, list) and v:
					vv = v[0]
				else:
					vv = v
				if isinstance(vv, (bytes, bytearray)):
					vv = vv.decode("latin1")
				out[kk] = str(vv)
			except Exception:
				continue
		return out


# ----------------------------------------------------------------------
# private Helfer
# ----------------------------------------------------------------------
def _headers_to_dict(headers) -> Dict[str, str]:
	"""Scrapy-Headers → einfacher str-dict."""
	out: Dict[str, str] = {}
	for k, v in headers.items():
		try:
			kk = k.decode("latin1") if isinstance(k, (bytes, bytearray)) else str(k)
			if isinstance(v, list) and v:
				vv = v[0]
			else:
				vv = v
			if isinstance(vv, (bytes, bytearray)):
				vv = vv.decode("latin1")
			out[kk] = str(vv)
		except Exception:
			continue
	return out


def _safe_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
	"""Picks die für den Loop nötigen Meta-Felder. Wir kopieren NICHT die
	gesamten Original-Meta — die enthalten Cookie-Jar-Pointers und können
	Zirkularitäten enthalten (z.B. download_slot, errback)."""
	if not meta:
		return {}
	keep = (
		"cookiejar", "jar_id", "lane_id", "lane_idx", "session_id",
		"download_slot", "browser_profile", "browser_headers",
		"versuch", "lane_groups", "Jahr", "Volume", "zyte_api",
		# Trefferlisten-/Item-Kontext, wenn vorhanden
		"item", "ProxyUrls", "PDFUrls",
	)
	out: Dict[str, Any] = {}
	for k in keep:
		if k in meta:
			out[k] = meta[k]
	return out


def _callback_name(cb: Optional[Callable]) -> Optional[str]:
	"""Wir reichen den Original-Callback als String-Name durch (Methodenname
	auf dem Spider), nicht als Funktionsobjekt — das ist serialisierungssicher
	und überlebt einen Disk-/Cluster-Hop."""
	if cb is None:
		return None
	name = getattr(cb, "__name__", None)
	if name:
		return name
	return None
