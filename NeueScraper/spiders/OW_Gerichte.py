# -*- coding: utf-8 -*-
import scrapy
import copy
import logging
import json
import re
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.spiders.weblawvaadin import WeblawVaadinSpider

logger = logging.getLogger(__name__)

class OW_Gerichte(WeblawVaadinSpider):
	name = 'OW_Gerichte'
	
	SUCHFORM='/le/?v-browserDetails=1&theme=le3themeAR&v-sh=900&v-sw=1440&v-cw=1439&v-ch=793&v-curdate=1609113076640&v-tzo=-60&v-dstd=60&v-rtzo=-60&v-dston=false&v-vw=1439&v-vh=0&v-loc=http://rechtsprechung.ow.ch/le/&v-wn=le-3449-0.{}&v-1609113076640='
	HOST ="http://rechtsprechung.ow.ch"
	HEADER = {
		"Content-Type": "text/plain;charset=utf-8",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0",
		"Referer": "http://rechtsprechung.ow.ch/le/",
		"Origin": "http://rechtsprechung.ow.ch"}
		
	def lese_entscheid(self, struk,entscheid):
		item={}
		abstract=self.lese_text(struk,entscheid,"0-0")
		num=self.lese_text(struk,entscheid,"1")
		html=self.lese_text(struk,entscheid,"3-1-0","resources/href/uRL")
		meta=self.lese_alle_metadaten(struk,entscheid)
		logger.info("Entscheid "+num+", "+abstract+", "+json.dumps(meta))
		if html[-4:]!=".htm":
			logger.warning("kein HTML hinterlegt ("+html+"). Ignoriere den Entscheid "+num+", "+abstract+", "+json.dumps(meta))
			return None
		else:
			item['HTMLUrls']=[self.HOST+html]
			klammerNum=self.reKlammer.search(num)
			if klammerNum:
				item['Num']=klammerNum.group('vor')
				if klammerNum.group('in'):
					item['Num2']=klammerNum.group('in')
				if('Datum letzter Änderung') in meta:
					item['PDatum']=self.norm_datum(meta['Datum letzter Änderung'])
				if('Dokumentsprache') in meta:
					item['Sprache']=meta['Dokumentsprache']
				if abstract:
					item['Abstract']=abstract
				item['Signatur'], item['Gericht'], item['Kammer'] = self.detect("","",item['Num'])
				return item
			else:
				logger.warning("Geschäftsnummer nicht erkannt in: "+num)
				return None
