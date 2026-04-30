# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import logging
from urllib.parse import urljoin
from w3lib.url import safe_url_string
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware, _build_redirect_request
from scrapy.utils.httpobj import urlparse_cached

logger = logging.getLogger(__name__)

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
		if "ProxyUrls" in item and item["ProxyUrls"]:
			redirected_url = spider.getProxyUrl(redirected_url)

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
