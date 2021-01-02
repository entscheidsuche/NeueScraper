# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
import datetime
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.spiders.weblawvaadin import WeblawVaadinSpider

logger = logging.getLogger(__name__)

class AR_Gerichte(WeblawVaadinSpider):
	name = 'AR_Gerichte'

	SUCHFORM='/le/?v-browserDetails=1&theme=le3themeAR&v-sh=900&v-sw=1440&v-cw=1439&v-ch=793&v-curdate=1609113076640&v-tzo=-60&v-dstd=60&v-rtzo=-60&v-dston=false&v-vw=1439&v-vh=0&v-loc=https://rechtsprechung.ar.ch/le/&v-wn=le-3449-0.{}&v-1609113076640='
	HOST ="https://rechtsprechung.ar.ch"
	HEADER = {
		"Content-Type": "text/plain;charset=utf-8",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0",
		"Referer": "https://rechtsprechung.ar.ch/le/",
		"Origin": "https://rechtsprechung.ar.ch"}
		
	def lese_entscheid(self, struk,entscheid):
		item={}
		abstract=self.lese_text(struk,entscheid,"0-0")
		num=self.lese_text(struk,entscheid,"1")
		pdf=self.lese_text(struk,entscheid,"3-1-0","resources/href/uRL")
		meta=self.lese_alle_metadaten(struk,entscheid)
		if pdf[-4:]!=".pdf":
			logger.warning("kein PDF hinterlegt ("+pdf+"). Ignoriere den Entscheid "+num+", "+abstract+", "+json.dumps(meta))
			return None
		else:
			item['PDFUrls']=[self.HOST+pdf]
			klammerNum=self.reKlammer.search(num)
			if klammerNum:
				item['Num']=klammerNum.group('vor')
				if klammerNum.group('in'):
					item['Num2']=klammerNum.group('in')
				if('Entscheiddatum') in meta:
					item['EDatum']=self.norm_datum(meta['Entscheiddatum'])
				if('Publikationsdatum') in meta:
					item['PDatum']=self.norm_datum(meta['Publikationsdatum'])
				if('Gericht') in meta:
					kurz=meta['Gericht']
					item['VGericht']=meta['Gericht']
				else:
					kurz=""
				if('Sprache') in meta:
					item['Sprache']=meta['Sprache']
				if abstract:
					item['Abstract']=abstract
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("",item['Num'],item['Num'])
				return item
			else:
				logger.warning("Geschäftsnummer nicht erkannt in: "+num)
				return None
		
