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
from scrapy.downloadermiddlewares.cookies import CookiesMiddleware
from urllib.parse import quote
import random
import os, base64, hashlib, time
try:
	from Cryptodome.Cipher import AES
except Exception:
	AES = None  # AES-Teil ist optional




logger = logging.getLogger(__name__)

class CH_BGer(BasisSpider):
	name = 'CH_BGer'
	TAGSCHRITTE = 4
	AUFSETZTAG = "01.01.2000"
	EINTAG=datetime.timedelta(days=1)

	INITIAL_URL='/ext/eurospider/live/de/php/aza/http/index.php'
	SUCH_URL='/ext/eurospider/live/de/php/aza/http/index.php?lang=de&type=simple_query&query_words=&top_subcollection_aza=all&from_date={von}&to_date={bis}&x=22&y=14'
	HOST='https://www.bger.ch'
	PROXY='https://entscheidsuche.ch/bge_helper/request.php?stub='
	USEPROXY=True
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
		"COOKIES_ENABLED": True,
		"COOKIES_DEBUG": True,
		"CONCURRENT_REQUESTS": 1,
		"DOWNLOAD_DELAY": 2.0,
		"ZYTE_API_PRESERVE_DELAY": True
	}
	# COOKIES={'powHash': '0000' + ''.join(random.choices('0123456789abcdef', k=60)), 'powNonce': str(random.randint(1000, 9999))}

	# ---------- Proof of Work ----------
	def sha256_bytes(self, s: str) -> bytes:
		return hashlib.sha256(s.encode("utf-8")).digest()

	def has_leading_zero_bits(self, b: bytes, difficulty_bits: int) -> bool:
		bits = difficulty_bits
		i = 0
		while bits >= 8:
			if i >= len(b) or b[i] != 0:
				return False
			i += 1; bits -= 8
		if bits > 0:
			mask = (0xFF << (8 - bits)) & 0xFF
			if i >= len(b) or (b[i] & mask) != 0:
				return False
		return True

	def mine(self, data: str, difficulty_bits: int, start_nonce: int = 0):
		nonce = start_nonce
		t0 = time.time()
		while True:
			h = self.sha256_bytes(f"{data}{nonce}")
			if self.has_leading_zero_bits(h, difficulty_bits):
				hhex = h.hex()
				return {"hash": hhex, "nonce": nonce, "elapsed_s": time.time() - t0}
			nonce += 1

	def validate_pow(self, data: str, difficulty_bits: int, hash_hex: str, nonce: int) -> bool:
		h = self.sha256_bytes(f"{data}{nonce}")
		return h.hex() == hash_hex and self.has_leading_zero_bits(h, difficulty_bits)

# ---------- AES-CBC (ZeroPadding) wie im JS (IV || Ciphertext, Base64) ----------
	def _zero_pad(self, b: bytes, block: int = 16) -> bytes:
		rem = len(b) % block
		return b if rem == 0 else b + b"\x00" * (block - rem)

	def encrypt_pow_data(self, data: str, hex_key: str) -> str:
		if AES is None: raise RuntimeError("PyCryptodome nicht installiert")
		key = bytes.fromhex(hex_key)			# 16/24/32 Byte
		iv  = os.urandom(16)
		cipher = AES.new(key, AES.MODE_CBC, iv)
		ct = cipher.encrypt(self._zero_pad(data.encode("utf-8"), 16))
		return base64.b64encode(iv + ct).decode("ascii")

	def decrypt_pow_data(self, b64: str, hex_key: str) -> str:
		if AES is None: raise RuntimeError("PyCryptodome nicht installiert")
		raw = base64.b64decode(b64)
		iv, ct = raw[:16], raw[16:]
		key = bytes.fromhex(hex_key)
		pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
		return pt.rstrip(b"\x00").decode("utf-8", errors="ignore")

	def mache_request(self,jar_id, von="",bis="",seite=1):
		logger.info(f"mache_request von {von} bis {bis}")
		if seite:
			page="&page="+str(seite)
		else:
			page=""
		url=self.HOST+self.SUCH_URL.format(von=von,bis=bis)+page
		if self.USEPROXY:
			before, sep, after = url.partition('?')
			encoded = quote(before, safe='') 
			url=self.PROXY+encoded+"&"+after
		
		request = scrapy.Request(url=url, headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, cookies={'powData': self.powData, 'powDifficulty': str(self.powDifficulty), 'powHash': self.powHash, 'powNonce': self.powNonce}, meta={'cookiejar': jar_id, 'page': seite, 'von': von, 'bis': bis, 'retry': 0})
		return request		

	def request_generator(self,jar_id,ab=None,bis=None):
		requests=[]
		parse_date = lambda s: datetime.datetime.strptime(s, "%d.%m.%Y").date()

		if ab is None:
			von=parse_date(self.AUFSETZTAG)
		else:
			von=parse_date(ab)
		
		if bis is None:
			ende=datetime.date.today()
		else:
			ende=parse_date(bis)
			
		while von<=ende:
			biszu=von+datetime.timedelta(days=self.TAGSCHRITTE-1)
			logger.info(f"request_generator von {von} bis {biszu}")		
			requests.append(self.mache_request(jar_id,von.strftime("%d.%m.%Y"),biszu.strftime("%d.%m.%Y")))
			von=biszu+self.EINTAG
		return requests
		
	def initial_request(self):
		url=self.HOST+self.INITIAL_URL
		if self.USEPROXY:
			before, sep, after = url.partition('?')
			encoded = quote(before, safe='') 
			url=self.PROXY+encoded+"&"+after
		requests=[scrapy.Request(url=url, headers=self.HEADER, meta={'cookiejar': 0}, callback=self.parse_cookie)]
		return requests
	
	def __init__(self, ab=None, neu=None, bis=None):
		super().__init__()
		self.ab=ab
		self.neu=neu
		self.bis=bis
		self.request_gen = self.initial_request()
		
		self.powDataUE = hashlib.sha256(os.urandom(32)).hexdigest()  # ersatzweise "Fingerprint"
		self.powDifficulty = 16  # wie im JS

		res = self.mine(self.powDataUE, self.powDifficulty)
		self.powNonce=res["nonce"]
		self.powHash=res["hash"]
		logger.info(f"Ohne Crypto: Hash: {self.powHash}, Nonce: {self.powNonce}, Dauer: {res['elapsed_s']:.2f}s, Difficulty: {self.powDifficulty}, Gültig: {self.validate_pow(self.powDataUE, self.powDifficulty, self.powHash, self.powNonce)}")

		# Optional: powData wie im JS (AES-CBC ZeroPadding, IV||CT -> Base64)
		hex_key = "9f3c1a8e7b4d62f1e0b5c47a2d8f93bc"  # 128-bit Key wie im Snippet
		if AES:
			self.powData = self.encrypt_pow_data(self.powDataUE, hex_key)
			logger.info(f"Mit Crypto: Hash: {self.powHash}, Nonce: {self.powNonce}, Dauer: {res['elapsed_s']:.2f}s, Difficulty: {self.powDifficulty}, Gültig: {self.validate_pow(self.powDataUE, self.powDifficulty, self.powHash, self.powNonce)}")
			assert self.decrypt_pow_data(self.powData, hex_key) == self.powDataUE
	
		
	def parse_cookie(self, response):
		antwort=response.text
		logger.info("parse_cookie Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_cookie Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_cookie Cookie Jar ID: {jar_id}")
		cm = next(mw for mw in self.crawler.engine.downloader.middleware.middlewares if isinstance(mw, CookiesMiddleware))
		cookies=json.dumps([{"name": c.name,"value": c.value,"domain": c.domain,"path": c.path,"expires": c.expires,"secure": c.secure,"discard": c.discard,"rest": getattr(c, "_rest", {})} for c in cm.jars[jar_id] ],ensure_ascii=False)
		logger.info("Cookies: "+cookies)
		requests = self.request_generator(jar_id,self.ab, self.bis)
		logger.info(f"{len(requests)} Requests")
		for r in requests:
			yield r


	def parse_trefferliste(self, response):
		logger.debug("parse_trefferliste response.status "+str(response.status))
		antwort=response.text
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen: "+response.url)
		logger.info("parse_trefferliste Rohergebnis: "+antwort[:30000])
		jar_id=response.meta['cookiejar']
		logger.info(f"parse_trefferliste Cookie Jar ID: {jar_id}")
		retry=response.meta['retry']
	
		trefferstring=PH.NC(response.xpath("//div[@class='content']/div[@class='ranklist_header center']/text()").get(),info="Trefferzahl nicht gefunden in: "+antwort)
		if trefferstring=="":
			no_treffer=response.xpath("//div[@class='content']/div[@class='ranklist_content center']/text()").get()
			if no_treffer and "keine Urteile gefunden" in no_treffer:
				logger.info("keine Urteile im Zeitraum "+response.meta['von']+"-"+response.meta['bis'])
			else:
				if retry>4:
					logger.error("Trotz 5 retries weder Trefferzahl noch 'keine Treffer' gefunden in: "+response.url+": "+antwort)
				else:
					logger.warning("Weder Trefferzahl noch 'keine Treffer' gefunden")
					request=response.request
					request.meta['retry']=retry+1
					if 'pow.php' in request.url:
						logger.info("Lief in den Miner. Versuch "+str(retry)+": Weder Trefferzahl noch 'keine Treffer' gefunden in: "+response.url+": "+antwort)
						url=response.url.replace("pow.php","index.php")
					else:
						logger.info("Lief nicht in den Miner. Versuch "+str(retry)+": Weder Trefferzahl noch 'keine Treffer' gefunden in: "+response.url+": "+antwort)
						url=request.url
					yield scrapy.Request(url=url, headers=self.HEADER, callback=self.parse_trefferliste, errback=self.errback_httpbin, cookies={'powData': self.powData, 'powDifficulty': str(self.powDifficulty), 'powHash': self.powHash, 'powNonce': self.powNonce}, meta=request.meta, dont_filter=True)
		else:
			treffer=int(trefferstring.split(" ")[0])
			if treffer>100:
				logger.warning(f"Request {response.request.url} findet mit {treffer} mehr als 100 Treffer. Spalte dies in Tagesrequests auf.")
				von=response.meta['von']
				bis=response.meta['bis']
				logger.info(f"Suchrequest {von}-{bis}")
				fmt = "%d.%m.%Y"
				tag = datetime.datetime.strptime(von, fmt).date()
				end = datetime.datetime.strptime(bis, fmt).date()
				if end < tag:
					raise ValueError("end < start")
				while tag <= end:
					tagstring=tag.strftime("%d.%m.%Y")
					request=self.mache_request(response.meta['cookiejar'],tagstring,tagstring)
					yield request
					tag += datetime.timedelta(days=1)
			else:			
				anfangsposition=int(response.xpath("//div[@class='ranklist_content']/ol/@start").get())
				urteile=response.xpath("//div[@class='ranklist_content']/ol/li")

				logger.info("Liste von {} Urteilen. Start bei {} von {} Treffer".format(len(urteile),anfangsposition, treffer))
		
				for entscheid in urteile:
					item={}
					text=entscheid.get()
					meta=entscheid.xpath("./span/a/text()").get()
					item['HTMLUrls']=[entscheid.xpath("./span/a/@href").get()]
					titel=entscheid.xpath("./div/div[3]/text()").get()
					if titel:
						item['Titel']=titel.strip()
					item['VKammer']=PH.NC(entscheid.xpath("./div/div[1]/text()").get(), warning="Kammerzeile nicht geparst: "+text)
					item['Rechtsgebiet']=PH.NC(entscheid.xpath("./div/div[2]/text()").get(), warning="Rechtsgebietszeile nicht geparst: "+text)
			
					if self.reDatumEinfach.search(meta) is None:
						logger.error("Konnte Datum in meta nicht erkennen: "+meta)
					else:
						item['EDatum']=self.norm_datum(meta)
						item['Num']=meta[11:]
						space=item['Num'].find(' ')
						if space>1 and space < 5:
							item['Num2']=item['Num'].replace(" ","_")
							logger.info("Ersetze Leerzeichen in "+item['Num']+": "+item['Num2'])
						
						item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['VKammer'],item['Num'])
						url=item['HTMLUrls'][0]
						if self.USEPROXY:
							before, sep, after = url.partition('?')
							encoded = quote(before, safe='') 
							url=self.PROXY+encoded+"&"+after
						request = scrapy.Request(url=url, callback=self.parse_document, errback=self.errback_httpbin, cookies={'powData': self.powData, 'powDifficulty': str(self.powDifficulty), 'powHash': self.powHash, 'powNonce': self.powNonce}, meta={'item': item})
						yield request
				if anfangsposition+len(urteile)<treffer:
					if response.meta['page']==10:
						logger.error("mehr als 100 Trreffer können wegen eines Bugs nicht angezeigt werden. Hier {} Treffer, von {} bis {} und Seite {}".format(treffer, response.meta['von'],response.meta['bis'],response.meta['page']))
					else:
						request=self.mache_request(jar_id, response.meta['von'],response.meta['bis'],response.meta['page']+1)
						yield request			

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status)+" for "+response.request.url)
		antwort=response.text
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:30000])
		
		item=response.meta['item']	
		html=response.xpath("//div[@id='highlight_content']/div[@class='content']")
		if html == []:
			logger.warning("Content nicht erkannt in "+antwort[:30000])
		else:
			PH.write_html(html.get(), item, self)
		yield(item)
