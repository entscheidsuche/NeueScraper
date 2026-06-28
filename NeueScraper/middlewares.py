# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import logging
import uuid
from urllib.parse import urljoin, urlparse
from w3lib.url import safe_url_string
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware, _build_redirect_request
from scrapy.utils.httpobj import urlparse_cached

logger = logging.getLogger(__name__)


class OopsRetryMiddleware:
	"""Downloader-Middleware: Wiederholt PDF-Downloads, deren Body weder
	mit '%PDF-' beginnt noch eine PDF-Endemarkierung '%%EOF' enthaelt
	(auch nicht nach optionalem base64-Dekodieren). Wartet zwischen den
	Versuchen 5 Sekunden, zieht eine frische Zyte-Smart-Proxy-Session-ID
	und ein neues Browser-Profil. Maximal MAX_VERSUCHE Wiederholungen.

	Opt-in pro Request via meta['oops_retry']=True. Greift nur, wenn die
	Ziel-URL auf .pdf endet (Pfad oder Query). Andere Spider/Pipelines
	werden nicht beeinflusst.

	Aktivierung pro Spider via custom_settings:
		custom_settings = {
			'DOWNLOADER_MIDDLEWARES': {
				'NeueScraper.middlewares.OopsRetryMiddleware': 580,
			}
		}
	"""

	MAX_VERSUCHE = 3
	BACKOFF_SECONDS = 5

	@classmethod
	def from_crawler(cls, crawler):
		return cls(crawler)

	def __init__(self, crawler):
		self.crawler = crawler

	def _looks_like_pdf_url(self, url):
		# Tolerant: '.pdf' im Pfad ODER irgendwo im Query (z.B. DownloadPdf-Endpunkte
		# bei TYPO3 liefern PDFs ueber URLs ohne .pdf-Suffix, das deckt aber der
		# zusaetzliche Hint per meta['oops_retry']=True ab).
		try:
			parsed = urlparse(url)
		except Exception:
			return False
		return parsed.path.lower().endswith('.pdf')

	def _is_valid_pdf(self, body):
		# Setzt auf PipelineHelper.is_pdf_body auf (inkl. base64-Fallback).
		try:
			from NeueScraper.pipelines import PipelineHelper
			return PipelineHelper.is_pdf_body(body)
		except Exception as e:
			logger.warning(f"OopsRetryMiddleware: PDF-Check fehlgeschlagen: {e!r}")
			return True  # im Zweifel keinen Retry triggern

	def process_response(self, request, response, spider):
		if not request.meta.get('oops_retry'):
			return response
		# Nur PDFs validieren — die meta-Markierung ist Opt-in, aber wir
		# pruefen nichts anderes als PDFs.
		body = response.body or b''
		starts_ok = body[:5] == b'%PDF-'
		ends_ok = self._is_valid_pdf(body)
		if starts_ok and ends_ok:
			return response

		versuch = int(request.meta.get('oops_versuch', 1))
		if versuch >= self.MAX_VERSUCHE:
			logger.warning(
				f"OopsRetry: max. Versuche ({self.MAX_VERSUCHE}) ausgeschoepft fuer {request.url} — "
				f"Antwort durchreichen, Pipeline behandelt sie regulaer."
			)
			return response

		# Frische Session-ID und neues Browser-Profil ziehen (falls Spider Rotation
		# kennt). Sonst nur Session neu erzeugen.
		new_session_id = None
		new_headers = None
		if hasattr(spider, '_new_session_id'):
			new_session_id = spider._new_session_id()
		else:
			new_session_id = uuid.uuid4().hex
		new_profile_name = None
		if hasattr(spider, '_pick_browser_profile'):
			profile = spider._pick_browser_profile()
			new_headers = dict(profile['headers'])
			new_profile_name = profile['browser']

		new_meta = dict(request.meta)
		new_meta['oops_versuch'] = versuch + 1
		zyte = dict(new_meta.get('zyte_api') or {})
		zyte['session'] = {'id': new_session_id}
		zyte['httpResponseHeaders'] = True
		new_meta['zyte_api'] = zyte
		new_meta['session_id'] = new_session_id
		if new_profile_name:
			new_meta['browser_profile'] = new_profile_name
		if new_headers:
			new_meta['browser_headers'] = new_headers

		# Header neu aufbauen: vorhandene Request-Header (z.B. Authorization)
		# beibehalten, aber Browser-Headers ueberschreiben.
		base_headers = {k.decode('latin-1') if isinstance(k, bytes) else k:
		                v[0].decode('latin-1') if isinstance(v, list) and v and isinstance(v[0], bytes) else v
		                for k, v in request.headers.items()}
		if new_headers:
			base_headers.update(new_headers)

		new_request = request.replace(headers=base_headers, meta=new_meta, dont_filter=True)

		logger.warning(
			f"OopsRetry Versuch {versuch}/{self.MAX_VERSUCHE} fuer {request.url}: "
			f"PDF-Body ungueltig (starts_ok={starts_ok}, ends_ok={ends_ok}). "
			f"Neue Session={new_session_id[:8]} Profil={new_profile_name} — "
			f"Backoff {self.BACKOFF_SECONDS}s."
		)

		# Scrapy-idiomatisches Retry: aus process_response ein Deferred
		# zurueckgeben, das nach BACKOFF_SECONDS mit dem neuen Request
		# resolved. Scrapy verarbeitet den neuen Request danach im selben
		# Slot (inkl. FilesPipeline-Callbacks). Damit entfaellt der
		# 'NO_CALLBACK has been called'-Traceback, der bei IgnoreRequest
		# zwingend auftrat, weil die FilesPipeline-Media-Requests intern
		# NO_CALLBACK als Callback haben.
		try:
			from twisted.internet import reactor
			from twisted.internet.defer import Deferred
			d = Deferred()
			def _resolve():
				engine = self.crawler.engine
				if not getattr(engine, "running", True):
					logger.info(f"OopsRetry: Spider bereits geschlossen, Retry verworfen ({request.url})")
					# Spider geschlossen -> Original-Response weitergeben,
					# damit kein haengender Deferred entsteht.
					d.callback(response)
					return
				d.callback(new_request)
			reactor.callLater(self.BACKOFF_SECONDS, _resolve)
			return d
		except Exception as e:
			logger.error(f"OopsRetry: Deferred-Setup fehlgeschlagen ({e!r}) — Original-Response durchreichen.")
			return response

class ProxyAwareRedirectMiddleware(RedirectMiddleware):
	"""Fängt 3xx ab, loggt die Kette, verpackt Location über spider.proxyUrl(), 
		und erzwingt Zyte followRedirect=False für Folge-Requests."""

	def process_request(self, request, spider):
		# Für markierte Requests (meta['proxy_wrap']=True) 3xx nie serverseitig folgen
		if 'item' in request.meta:
			item=request.meta['item']
			if "ProxyUrls" in item and item["ProxyUrls"]:
				zyte = dict(request.meta.get("zyte_api") or {})
				zyte["httpResponseHeaders"] = True
				zyte["followRedirect"] = False
				request.meta["zyte_api"] = zyte
		return None

	def process_response(self, request, response, spider):
		# Nichts zu tun, wenn kein Redirect o. Request nicht markiert
		if not 'item' in request.meta:
			return response
		else:
			item=request.meta['item']
			if (not ("ProxyUrls" in item and item["ProxyUrls"]) or response.status not in (301, 302, 303, 307, 308) or b"Location" not in response.headers):
				return response

        # Absolute Location aufbauen
		location = safe_url_string(response.headers["Location"])
		if response.headers["Location"].startswith(b"//"):
			scheme = urlparse_cached(request).scheme
			location = scheme + "://" + location.lstrip("/")
		redirected_url = urljoin(item['PDFUrls'][0], location)

		# Redirect-Kette pflegen (inkl. Set-Cookie zum Debuggen)
		chain = list(request.meta.get("redirect_chain") or [])
		chain.append({
			"status": int(response.status),
			"from": request.url,
			"to": redirected_url,
			"set_cookie": [v.decode("latin1") for v in response.headers.getlist(b"Set-Cookie")],
		})

		# Location über DEINEN bestehenden Wrapper führen (kein Doppel-Wrap,
		# da deine proxyUrl() das bereits verhindert)
		# line_proxy: lief der Request über eine bestimmte CH_BGE-Linie, wird der
		# Redirect über DENSELBEN Proxy zurückgewrappt. Ohne line_proxy (None)
		# bleibt es der bisherige Default-Proxy → weblaw u.a. unverändert.
		if "ProxyUrls" in item and item["ProxyUrls"]:
			redirected_url = spider.getProxyUrl(redirected_url, request.meta.get('line_proxy'))

		# Folge-Request wie Upstream bauen (GET bei 302/303 etc.)
		if response.status in (301, 307, 308) or request.method == "HEAD":
			redirected = _build_redirect_request(request, url=redirected_url)
		else:
			redirected = self._redirect_request_using_get(request, redirected_url)

		# Redirect-Kette & Zyte-Flags durchreichen
		redirected.meta["redirect_chain"] = chain
		zyte = dict(redirected.meta.get("zyte_api") or {})
		zyte["httpResponseHeaders"] = True
		zyte["followRedirect"] = False
		redirected.meta["zyte_api"] = zyte

		spider.logger.info("Redirect %s → %s [%s]", request.url, redirected_url, response.status)
		return self._redirect(redirected, request, spider, response.status)


class CookieDiagnoseMiddleware:
	"""Loggt Antworten, die auf Cookie-Resets, Bot-Challenges oder
	Redirect-basierte Cookie-Wechsel hindeuten. Ziel: Vor einem 4xx/5xx-Fehler
	im Log nachvollziehen können, welche Antwort die Cookies geändert hat.

	Erkannte Events (alle als logger.info):
	  COOKIE-EVENT  – Response hat Set-Cookie-Header (Mid-Session Cookie-Wechsel)
	  REDIRECT      – 3xx mit Location + Set-Cookie (Imperva-Challenge-typisch)
	  SHORT-200     – 200-Response unter SUSPICIOUS_BODY_THRESHOLD Bytes
	                  (typisch für JS-Challenge / Block-Page mit 200)
	  NON-2XX       – 4xx/5xx mit Cookie-Header der gesendet wurde
	"""

	SUSPICIOUS_BODY_THRESHOLD = 2000  # bytes; Challenge-Pages sind meist <2 KB

	@classmethod
	def from_crawler(cls, crawler):
		return cls()

	def process_response(self, request, response, spider):
		try:
			self._log_events(request, response, spider)
		except Exception as e:
			# Diagnose-Logging darf den Spider unter keinen Umständen brechen
			spider.logger.warning(f"CookieDiagnoseMiddleware: Logging fehlgeschlagen: {e!r}")
		return response

	def _log_events(self, request, response, spider):
		jar = request.meta.get('cookiejar', '?')
		lane_idx = request.meta.get('lane_idx', '?')
		# 1) Set-Cookie-Header der Response
		set_cookies = response.headers.getlist(b'Set-Cookie')
		if set_cookies:
			names = []
			for c in set_cookies:
				try:
					nm = c.split(b'=', 1)[0].decode('latin1', errors='replace')
					names.append(nm)
				except Exception:
					pass
			# Hat der Request schon Cookies geschickt? Dann ist es ein Mid-Session-Wechsel.
			req_cookie_hdr = request.headers.get(b'Cookie')
			marker = 'MID-SESSION' if req_cookie_hdr else 'INITIAL'
			spider.logger.info(
				f"COOKIE-EVENT[{marker}] status={response.status} jar={jar} lane={lane_idx} "
				f"set-cookie-names={names} url={response.url}"
			)

		# 2) Redirects (3xx)
		if 300 <= response.status < 400:
			location_b = response.headers.get(b'Location', b'')
			location = location_b.decode('utf-8', errors='replace') if location_b else ''
			spider.logger.info(
				f"REDIRECT status={response.status} jar={jar} lane={lane_idx} "
				f"from={response.url} to={location}"
			)

		# 3) Verdächtig kurze 200-Antworten (Challenge-Page hat oft 200 + winzigen Body)
		if response.status == 200 and len(response.body) < self.SUSPICIOUS_BODY_THRESHOLD:
			body_preview = response.text[:400] if hasattr(response, 'text') else ''
			body_preview = body_preview.replace('\n', ' ').replace('\r', '')
			spider.logger.info(
				f"SHORT-200 size={len(response.body)} jar={jar} lane={lane_idx} "
				f"url={response.url} body={body_preview!r}"
			)

		# 4) 4xx/5xx mit gesendeten Cookies, damit wir nachvollziehen, was der Server abgewiesen hat
		if response.status >= 400:
			req_cookie_hdr = request.headers.get(b'Cookie', b'')
			req_cookies = req_cookie_hdr.decode('utf-8', errors='replace') if req_cookie_hdr else ''
			# Nur die Cookie-Namen + ersten 6 Zeichen Wert ausgeben (kompakt)
			compact = []
			for kv in req_cookies.split(';'):
				kv = kv.strip()
				if '=' in kv:
					n, v = kv.split('=', 1)
					compact.append(f"{n}={v[:6]}…")
			spider.logger.info(
				f"NON-2XX status={response.status} jar={jar} lane={lane_idx} "
				f"url={response.url} sent={compact}"
			)


class NeuescraperSpiderMiddleware:
	# Not all methods need to be defined. If a method is not defined,
	# scrapy acts as if the spider middleware does not modify the
	# passed objects.

	@classmethod
	def from_crawler(cls, crawler):
		# This method is used by Scrapy to create your spiders.
		s = cls()
		crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
		return s

	def process_spider_input(self, response, spider):
		# Called for each response that goes through the spider
		# middleware and into the spider.

		# Should return None or raise an exception.
		return None

	def process_spider_output(self, response, result, spider):
		# Called with the results returned from the Spider, after
		# it has processed the response.

		# Must return an iterable of Request, dict or Item objects.
		for i in result:
			yield i

	def process_spider_exception(self, response, exception, spider):
		# Called when a spider or process_spider_input() method
		# (from other spider middleware) raises an exception.

		# Should return either None or an iterable of Request, dict
		# or Item objects.
		pass

	def process_start_requests(self, start_requests, spider):
		# Called with the start requests of the spider, and works
		# similarly to the process_spider_output() method, except
		# that it doesn’t have a response associated.

		# Must return only requests (not items).
		for r in start_requests:
			yield r

	def spider_opened(self, spider):
		spider.logger.info('Spider opened: %s' % spider.name)


class NeuescraperDownloaderMiddleware:
	# Not all methods need to be defined. If a method is not defined,
	# scrapy acts as if the downloader middleware does not modify the
	# passed objects.

	@classmethod
	def from_crawler(cls, crawler):
		# This method is used by Scrapy to create your spiders.
		s = cls()
		crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
		return s

	def process_request(self, request, spider):
		# Called for each request that goes through the downloader
		# middleware.

		# Must either:
		# - return None: continue processing this request
		# - or return a Response object
		# - or return a Request object
		# - or raise IgnoreRequest: process_exception() methods of
		#   installed downloader middleware will be called
		return None

	def process_response(self, request, response, spider):
		# Called with the response returned from the downloader.

		# Must either;
		# - return a Response object
		# - return a Request object
		# - or raise IgnoreRequest
		if 'cached' in response.flags:
			logger.warning("cached request found: "+request.url)
			request.meta['dont_cache']=True
			return request
		else:
			logger.info("request not cached: "+request.url)
			return response

	def process_exception(self, request, exception, spider):
		# Called when a download handler or a process_request()
		# (from other downloader middleware) raises an exception.

		# Must either:
		# - return None: continue processing this exception
		# - return a Response object: stops process_exception() chain
		# - return a Request object: stops process_exception() chain
		pass

	def spider_opened(self, spider):
		spider.logger.info('Spider opened: %s' % spider.name)
