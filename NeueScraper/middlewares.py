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
