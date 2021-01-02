# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
from scrapy.http.cookies import CookieJar
import datetime
import random
from NeueScraper.spiders.basis import BasisSpider
from NeueScraper.pipelines import PipelineHelper as PH

logger = logging.getLogger(__name__)

class WeblawVaadinSpider(BasisSpider):
	
	custom_settings = {
        'COOKIES_ENABLED': True
    }

	TREFFERLISTE_URL='/le/UIDL/?v-uiId=0'
	TREFFERLISTE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","resize",["793","1429","1429","793"]],["'
	TREFFERLISTE_p2=b'","com.vaadin.shared.ui.button.ButtonServerRpc","click",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"10", "clientX":"728", "relativeY":"17", "clientY":"47", "button":"LEFT", "type":"1"}]]]'
	NEXTPAGE_p1=b'\x1d[["0","com.vaadin.shared.ui.ui.UIServerRpc","scroll",["535","0"]],["'
	NEXTPAGE_p2=b'","com.vaadin.shared.ui.orderedlayout.AbstractOrderedLayoutServerRpc","layoutClick",[{"metaKey":false, "altKey":false, "shiftKey":false, "ctrlKey":false, "relativeX":"66", "clientX":"284", "relativeY":"13", "clientY":"716", "button":"LEFT", "type":"8"},null]]]'
		
	reNum=re.compile(r' href="[^"]+">(?P<Num>[^<]+)</a>')
	reTreffer=re.compile(r'Resultat\s+(?P<von>\d+)-(?P<bis>\d+)\s+von\s+(?P<gesamt>\d+)')
	reKlammer=re.compile(r"^(?:<a[^>]+>)?\s*(?P<vor>[^\s(<][^(<]*[^\s(<])\s*(?:\((?P<in>[^)]+)\)\s*)?(?:</a>)?$")
	
	def generate_request(self):
		request=scrapy.Request(url=self.HOST+self.SUCHFORM.format(str(random.randint(1000000000000000,9999999999999999))), method="POST", callback=self.parse_suchform, errback=self.errback_httpbin)
		return request
	
	def __init__(self, ab=None):
		super().__init__()
		self.request_gen = [self.generate_request()]

	def parse_suchform(self, response):
		logger.info("parse_suchform response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_suchform Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.debug("parse_suchform Rohergebnis: "+antwort[:30000])
		struktur=json.loads(antwort)
		antwort_uidl=struktur['uidl']
		struktur_uidl=json.loads(antwort_uidl)
		logger.debug("uidl: "+json.dumps(struktur_uidl))
		self.vaadin_key=struktur_uidl["Vaadin-Security-Key"]
		logger.info("Vaadin-Key: "+self.vaadin_key)
		state=struktur_uidl["state"]
		logger.debug("state: "+json.dumps(state))
		self.searchbutton=[i for i in state if "clickShortcutKeyCode" in state[i]][0]
		logger.info("searchbutton: "+str(self.searchbutton))
		self.contentid=[i for i in state if 'spacing' in state[i] and state[i]['spacing']==True and 'width' in state[i] and state[i]['width']=="100.0%"][0]
		logger.info("contentid: "+str(self.contentid))
		request=scrapy.Request(url=self.HOST+self.TREFFERLISTE_URL, headers=self.HEADER , method="POST", body=self.vaadin_key.encode('utf-8')+self.TREFFERLISTE_p1+str(self.searchbutton).encode("utf-8")+self.TREFFERLISTE_p2, callback=self.parse_trefferliste, errback=self.errback_httpbin)
		logger.info(b"Request: "+request.body)
		yield request
		

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_trefferliste Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+antwort)
		
		struk=json.loads(antwort[8:])
		# Statt über die Hierarchie könnte man auch über types gehen alle Einträge haben type 1
		members=struk[0]['hierarchy'][str(self.contentid)]
		logger.info("members "+json.dumps(members))
		children_last_member=struk[0]['hierarchy'][members[-1]]
		weiterkey="0"
		treffer=""
		for i in children_last_member:
			if 'text' in struk[0]['state'][i]:
				treffer += struk[0]['state'][i]['text']
			# Weiterkey finden - aber nicht versehentlich den Zurückkey nehmen
			if 'registeredEventListeners' in struk[0]['state'][i] and int(weiterkey)<int(i):
				weiterkey=i
		logger.info("Treffer: "+treffer+", weiterkey: "+weiterkey)
		tm=self.reTreffer.search(treffer)
		if tm is None:
			logger.error("Treffer nicht erkannt: "+treffer)
		else:
			vonTreffer=tm.group("von")
			bisTreffer=tm.group("bis")
			gesamtTreffer=tm.group("gesamt")
			for entscheid in range(1,len(members)-1):
				item=self.lese_entscheid(struk,members[entscheid])
				if item:
					if 'HTMLUrls' in item and item['HTMLUrls'][0]:
						request = scrapy.Request(url=item['HTMLUrls'][0], callback=self.parse_document, errback=self.errback_httpbin, meta={'item': item})
						yield request
					else:
						yield item
				
			if int(bisTreffer)<int(gesamtTreffer):
				request=scrapy.Request(url=self.HOST+self.TREFFERLISTE_URL, headers=self.HEADER , method="POST", body=self.vaadin_key.encode('utf-8')+self.NEXTPAGE_p1+weiterkey.encode("utf-8")+self.NEXTPAGE_p2, callback=self.parse_trefferliste, errback=self.errback_httpbin)
				logger.info("Hole jetzt die Treffer nach "+bisTreffer)
				logger.info(request.body)
				yield request
			else:
				logger.info("Fertig nach "+gesamtTreffer)

	def parse_document(self, response):
		logger.info("parse_document response.status "+str(response.status))
		antwort=response.body_as_unicode()
		logger.info("parse_document Rohergebnis "+str(len(antwort))+" Zeichen")
		logger.info("parse_document Rohergebnis: "+antwort[:20000])
		
		item=response.meta['item']
		PH.write_html(antwort, item, self)
		yield(item)
	
		
	def lese_hierarchie(self, struk,obj,hierarchie):
		logger.debug("Hole "+hierarchie+" von "+str(obj))
		trail=str(obj)
		for p in hierarchie.split("-"):
			if obj in struk[0]['hierarchy'] and len(struk[0]['hierarchy'][obj])>int(p):
				obj=struk[0]['hierarchy'][obj][int(p)]
				trail+="["+p+"]->"+str(obj)
			else:
				if obj in struk[0]['hierarchy']:
					logger.warning("Fehler beim Hierarchietrail "+trail+" beim Pfad "+hierarchie+".  Objekt "+str(obj)+" hat nur "+str(len(struk[0]['hierarchy'][obj]))+" Elemente so dass "+str(obj)+"["+p+"] ins Leere geht.")
				else:
					logger.error("Hierarchiefehler: "+hierarchie+" (bislang "+trail+") deutet auf "+str(obj)+", welches nicht in der Hierarchie enthalten ist.")
				break
		return obj
	
	def lese_text(self,struk,los,hierarchie,pfad='text'):
		trail="lese_text für "+str(los)+"["+hierarchie+"]"
		obj=self.lese_hierarchie(struk,los,hierarchie)
		knoten=struk[0]['state'][obj]
		trail+="="+str(obj)+"/"+pfad+", welches folgenden Objektbaum hat: "+json.dumps(knoten)
		logger.debug(trail)
		trail+="\n["+str(obj)+"]"
		for p in pfad.split("/"):
			if p in knoten:
				knoten=knoten[p]
				trail+="/"+p
			else:
				logger.warning(trail+" '"+p+"' nicht gefunden, dort gibt es nur folgende Objekte: "+json.dumps(knoten))
				return ""
		logger.info(trail+": "+json.dumps(knoten))
		return knoten.strip()
		
	def lese_alle_metadaten(self, struk, los):
		knoten=self.hole_alle_knoten(struk, los)
		ergebnis={}
		for k in knoten:
			if k in struk[0]['state']:
				obj=struk[0]['state'][k]
				if 'description' in obj:
					d=obj['description']
					name=d.split(": ")[0]
					if 'text' in obj:
						ergebnis[name]=obj['text'].strip()
					else:
						ergebnis[name]=''
		return ergebnis
				
		
		
	def hole_alle_knoten(self,struk, los):
		knoten=[los]
		if los in struk[0]['hierarchy']:
			for kind in struk[0]['hierarchy'][los]:
				knoten+=self.hole_alle_knoten(struk,kind)
		else:
			logger.error("Knoten '"+los+"' nicht in Hierarchie")
		return knoten
			
		
		
		
		
