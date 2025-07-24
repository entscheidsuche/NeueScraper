# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH
import time

logger = logging.getLogger(__name__)

"""
Um einen Tribuna-Spider zu bauen, müssen die URLs und die Hostnamen angepasst werden.
Dazu dann in den Requests für Suche mit und ohne Datum die Trefferzahl auf 1 setzen (ist dort auf 20) und Seitennummer sowie im zweiten Request auch das Suche-ab-Datum markieren.
"""

class TribunaSpider(BasisSpider):
	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 20000
	reVor=re.compile('//OK\\[[0-9,\\.]+\\[')
	reAll=re.compile('(?<=,\\")[^\\"]*(?:\\\\\\"[^\\"]*)*(?=\\",)')
	reID=re.compile('[0-9a-f]{32}|[0-9]{15,17}')
	reDatum=re.compile('\d{4}-\d{2}-\d{2}')
	reRG=re.compile('[^0-9\\.:-]{3}.{3,}')
	reTreffer=re.compile('(?<=^//OK\\[)[0-9]+')
	reDecrypt=re.compile('(?<=//OK\[1,\[")[0-9a-f]+')
	reDecrypt2=re.compile('(?<=//OK)([0-9,"a-z.A-Z/\[\]]+partURL\",\")(?P<p1>[^"]+_)(?P<p2>[^"_]+)","(?P<p3>dossiernummer)","(?P<p4>[^"]+)')
	reDecode=re.compile(r'\\x([0-9A-Fa-f]{2})')

	rePfad=re.compile(r'[A-Z]:(?:\\.+)+\.pdf')
	rePfad2=re.compile(r'[0-9a-f]{128,192}')
	page_nr=0
	trefferzahl=0
	ENCRYPTED=False
	ASCII_ENCRYPTED=False
	COOKIE=False
	VKAMMER=True
	HOLE_AUCH_HTML = False
	
	#name = 'Tribuna, virtuell'
	
	def get_next_request(self):
		logger.info("Hole Treffer Nr. "+str(self.page_nr))
		millis=str(int(time.time()*1000))
		if self.ab is None:
			body = self.RESULT_QUERY_TPL.format(page_nr=self.page_nr, millis=millis)
		else:
			body = self.RESULT_QUERY_TPL_AB.format(page_nr=self.page_nr, millis=millis, datum=self.ab)
		self.page_nr=self.page_nr+1
		return body	
	
	def request_generator(self):
		logger.info("request_generator: Self ist vom Typ: "+str(type(self)))			
		""" Generates scrapy frist request
		"""
		body=self.get_next_request()
		if self.COOKIE:
			orequest=scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)
			request=scrapy.Request(url=self.COOKIE_INIT, headers=self.COOKIE_HEADERS, callback=self.set_cookie, errback=self.errback_httpbin, meta={'request': orequest, 'referrer_policy': "no-referrer"})
			return [request]
		else:
			request=scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin, meta={'referrer_policy': "no-referrer"})
		return [request]

	def __init__(self,ab=None, neu=None):
		self.neu=neu
		logger.info("__init__ in tribuna: Self ist vom Typ: "+str(type(self)))			
		super().__init__()
		self.ab = ab
		self.request_gen=self.request_generator()

	def set_cookie(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.info("Response Cookie Init with "+self.COOKIE_INIT+" with status: "+str(response.status))
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			# construct and download document links
			logger.info("Rohergebnis set_cookie: "+response.text)
			logger.info("Headers set_coookie: "+PH.mydumps(response.headers))
			cookie=response.headers['Set-Cookie'].decode('ascii').split(';')[0].encode('ascii')
			request=response.meta['request']
			request.headers['Cookie']=cookie
			logger.info("Starte nun Request "+request.url+" mit Header "+PH.mydumps(request.headers)+" und Body "+PH.mydumps(request.body))
			yield request

	def parse_page(self, response):	
		""" Parses the current search result page, downloads documents and yields the request for the next search
		result page
		"""
		logger.info("Anfrage war: "+response.request.body.decode('utf-8'))
		logger.info("Rohergebnis: "+response.text)
		if response.status == 200 and len(response.body) > self.MINIMUM_PAGE_LEN:
			# construct and download document links

			if self.page_nr==1:
				treffer=self.reTreffer.search(response.text)
				if treffer:
					logger.info("Trefferzahl: "+treffer.group())
					self.trefferzahl=int(treffer.group())
			
			if self.trefferzahl>0:
				content = self.reVor.sub('',response.text)
			
				logger.info("Ergebnisseite: "+content)

				werte=self.reAll.findall(content)
				i=0
				for wert in werte:
					logger.info("Wert " +str(i)+": "+ wert)
					i=i+1

				korrektur=0
				brauchbar=True
			
				if self.reID.fullmatch(werte[3]):
					id_=werte[3]
				elif self.reID.fullmatch(werte[4]):
					id_=werte[4]
					korrektur=1
				elif self.reID.fullmatch(werte[5]):
					id_=werte[5]
					korrektur=2
				else:
					logger.error("Type mismatch keine ID '"+werte[3]+"', '"+werte[3+1]+"', '"+werte[3+2]+"'")	
					brauchbar=False

				vkammer=""
				if korrektur>0:
					if len(werte[3])>8:
						vkammer=werte[3]
					else:
						logger.warning("Type mismatch keine Kammer '"+werte[3]+"'")
			
				titel=werte[4+korrektur].replace("\\x27","'")
				if len(titel)<8:
					logger.warning("Type mismatch kein Titel '"+titel+"'")
					titel=""
				 
				if self.reNum.fullmatch(werte[5+korrektur]):
					num=werte[5+korrektur]
				elif self.reNum.fullmatch(werte[5+korrektur+1]):
					korrektur+=1
					num=werte[5+korrektur]
				elif self.reNum.fullmatch(werte[5+korrektur-1]):
					korrektur-=1
					num=werte[5+korrektur]
				else:
					logger.error("Type mismatch keine Geschäftsnummer '"+werte[5+korrektur-1]+"', '"+werte[5+korrektur]+"', '"+werte[5+korrektur+1]+"'")
					brauchbar=False

				if self.reDatum.fullmatch(werte[6+korrektur]):
					entscheiddatum=werte[6+korrektur]
				elif self.reDatum.fullmatch(werte[6+korrektur+1]):
					korrektur+=1
					entscheiddatum=werte[6+korrektur]
				else:
					logger.error("Type mismatch kein Entscheiddatum '"+werte[6+korrektur]+"', '"+werte[6+korrektur+1]+"'")
					brauchbar=False
			
				leitsatz=werte[7+korrektur].replace("\\x27","'")
				if len(leitsatz)<11:
					if leitsatz != '-':
						logger.warning("Type mismatch kein Leitsatz '"+leitsatz+"'")
					leitsatz=""

				neuePfadsyntax=False
				if self.rePfad.fullmatch(werte[8+korrektur]):
					pfad=werte[8+korrektur]
				elif self.rePfad.fullmatch(werte[8+korrektur+1]):
					korrektur+=1
					pfad=werte[8+korrektur]
				elif self.rePfad.fullmatch(werte[8+korrektur+2]):
					korrektur+=2
					pfad=werte[8+korrektur]
				elif self.rePfad.fullmatch(werte[8+korrektur+3]):
					korrektur+=3
					pfad=werte[8+korrektur]
				elif self.rePfad2.fullmatch(werte[8+korrektur]):
					pfad=werte[8+korrektur]
					neuePfadsyntax=True
				elif self.rePfad2.fullmatch(werte[8+korrektur+1]):
					korrektur+=1
					pfad=werte[8+korrektur]
					neuePfadsyntax=True
				elif self.rePfad2.fullmatch(werte[8+korrektur+2]):
					korrektur+=2
					pfad=werte[8+korrektur]
					neuePfadsyntax=True
				elif self.rePfad2.fullmatch(werte[8+korrektur+3]):
					korrektur+=3
					pfad=werte[8+korrektur]
					neuePfadsyntax=True
				else:
					logger.error("Type mismatch kein Pfad '"+werte[8+korrektur]+"', '"+werte[8+korrektur+1]+"', '"+werte[8+korrektur+2]+"'")	
					brauchbar=False

				l=len(werte)
				if neuePfadsyntax==True and l>22:
					l=l-8
				if self.reDatum.fullmatch(werte[l-1]):
					publikationsdatum=werte[l-1]
				elif self.reDatum.fullmatch(werte[l-2]):
					publikationsdatum=werte[l-2]
				else:
					logger.warning("Type mismatch letzter und vorletzter Eintrag kein Publikationsdatum '"+werte[len(werte)-1]+"', '"+werte[len(werte)-2]+"'")
					publikationsdatum=""


				if len(werte)>10+korrektur and self.reRG.fullmatch(werte[9+korrektur]):
					rechtsgebiet=werte[9+korrektur]
				elif len(werte)>11+korrektur and self.reRG.fullmatch(werte[10+korrektur]):
					rechtsgebiet=werte[10+korrektur]
				else:
					rechtsgebiet=""
					if len(werte)>10+korrektur:
						logger.warning("Type mismatch kein Rechtsgebiet '"+werte[9+korrektur]+"', '"+werte[10+korrektur]+"'")
					else:
						logger.warning("Type mismatch kein Rechtsgebiet '"+werte[9+korrektur]+"'")

				if brauchbar:
					numstr = num.replace(" ", "_")
					#Ist die Signatur nicht eindeutig, so muss hier differenziert werden
					signatur, gericht, kammer=self.detect("",vkammer,num)
				
					vgericht=gericht
					if not vkammer:
						vkammer=kammer
					
					item = {
						'Kanton': self.kanton_kurz,
						'Num':num ,
						'Kammer':kammer,
						'EDatum': entscheiddatum,
						'PDatum': publikationsdatum,
						'Titel': titel,
						'Leitsatz': leitsatz,
						'Rechtsgebiet': rechtsgebiet,
						'DocId':id_,
						'Raw': content,
						'Signatur': signatur, 
						'Gericht': gericht,
						'VGericht': vgericht,
						'VKammer': vkammer
					}				
				
					logger.info("Pfad: "+pfad)
					
					html_request=None
					if self.HOLE_AUCH_HTML:
						body=self.HTML_REQUEST.format(id_)
						html_request=scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.hole_html, errback=self.errback_httpbin, meta={"item":item})
								
					if self.ENCRYPTED:
						if neuePfadsyntax:
							pfad=numstr+"_"+pfad+"|dossiernummer|"+numstr
						elif self.ASCII_ENCRYPTED:
							ascii_pfad=''
							for c in pfad:
								ascii_pfad += '|'+str(ord(c))
							pfad=ascii_pfad.replace("|92|92","|92")
						body=self.DECRYPT_START+pfad+self.DECRYPT_END
						logger.info("Decrypt-Body: "+body)
						yield scrapy.Request(url=self.DECRYPT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.decrypt_path, errback=self.errback_httpbin, meta={"item":item, "html_request":html_request})
					else:
						href = self.PDF_PATTERN.format(self.DOWNLOAD_URL, numstr, id_,self.PDF_PATH, id_, numstr)
						item['PDFUrls']=[href]
						if html_request:
							yield html_request
						else:
							yield item
				else:
					logger.error("Parse Fehler bei Treffer "+str(self.page_nr)+" String: "+content)
			else:
				logger.warning("0 Treffer")
			if self.page_nr < min(self.trefferzahl, self.MAX_PAGES):
				body = self.get_next_request()
				yield scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body=body, headers=self.HEADERS, callback=self.parse_page, errback=self.errback_httpbin)
		else:
			logger.error("ungültige Antwort")

	def decrypt_path(self, response):
		logger.info("Decrypt-Request: "+response.request.url)
		item=response.meta['item']
		html_request=response.meta['html_request']
		logger.info("Decrypt-Path für DocID "+item['DocId'])
		if response.status == 200:
			logger.info("Rohergebnis Decrypt: "+response.text)
			code=self.reDecrypt.search(response.text)
			if code:
				numstr = item['Num'].replace(" ", "_")
				href=self.PDF_PATTERN.format(self.DOWNLOAD_URL,numstr,item['DocId'],code.group(),numstr)
				logger.info("PDF-URL: "+href)
				item['PDFUrls']=[href]
				if html_request:
					yield html_request
				else:
					yield item
			else:
				code=self.reDecrypt2.search(response.text)
				if code:
					href=self.PDF_PATTERN.format(self.DOWNLOAD_URL,code.group("p1")+code.group("p2"),code.group("p2"),code.group("p4"))
					logger.info("V2 PDF-URL: "+href)
					item['PDFUrls']=[href]
					if html_request:
						yield html_request
					else:
						yield item
					
				else:
					logger.error("Gecrypteter Pfad konnte nicht geparst werden.")
					if html_request:
						yield html_request
					
		else:
			logger.error("Keine Antwort für gecrypteten Pfad")
			if html_request:
				yield html_request
			
	def hole_html(self, response):
		logger.info("HTML-Request: "+response.request.url)
		item=response.meta['item']
		content = self.reVor.sub('',response.text)
		logger.info("HTMLseite: "+content)
		werte=self.reAll.findall(content)
		xhtml=[i for i,v in enumerate(werte) if v=="xhtml"]
		if xhtml:
			item['HTMLUrls']=[response.request.url]
			html_string=werte[xhtml[0]+1]
			html_string=self.reDecode.sub(lambda m: chr(int(m.group(1), 16)),html_string)
			html_string=html_string.replace("\n","")
			logger.info("html: "+html_string)
			PH.write_html(html_string, item, self)
		yield item
			


