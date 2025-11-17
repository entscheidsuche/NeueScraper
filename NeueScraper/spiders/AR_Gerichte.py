# -*- coding: utf-8 -*-
import scrapy
import re
import copy
import logging
import json
import datetime
from NeueScraper.pipelines import PipelineHelper as PH
from NeueScraper.spiders.weblawvaadin3 import WeblawVaadinSpider

logger = logging.getLogger(__name__)

class AR_Gerichte(WeblawVaadinSpider):
	name = 'AR_Gerichte'

	# SUCHFORM='/le/?v-browserDetails=1&theme=le3themeAR&v-sh=900&v-sw=1440&v-cw=1439&v-ch=793&v-curdate=1609113076640&v-tzo=-60&v-dstd=60&v-rtzo=-60&v-dston=false&v-vw=1439&v-vh=0&v-loc=https://rechtsprechung.ar.ch/le/&v-wn=le-3449-0.{}&v-1609113076640='
	# SUCHFORM={"sortOrder":"desc","sortField":"decisionDate","guiLanguage":"de","metadataKeywordsMap":{"treePath":"/Rechtsprechung AR","argvpBehoerde":"OG OR Verwaltung OR KG"},"userID":"","sessionDuration":1161,"aggs":{"fields":["entscheidKategorie","argvpBehoerde","gvpNumber","pubYearGvp","srCategoryList","lex-ch-bund-srList","ch-jurivocList","jud-ch-bund-bgeList","jud-ch-bund-bguList","jud-ch-bund-bvgeList","jud-ch-bund-bvgerList","jud-ch-bund-tpfList","jud-ch-bund-bstgerList","lex-ch-bund-asList","lex-ch-bund-bblList","lex-ch-bund-abList"],"size":"10"}}
	# SUCHFORM={"sortOrder":"desc","sortField":"decisionDate","guiLanguage":"de","userID":"","sessionDuration":41,"aggs":{"fields":["entscheidKategorie","argvpBehoerde","gvpNumber","pubYearGvp","srCategoryList","lex-ch-bund-srList","ch-jurivocList","jud-ch-bund-bgeList","jud-ch-bund-bguList","jud-ch-bund-bvgeList","jud-ch-bund-bvgerList","jud-ch-bund-tpfList","jud-ch-bund-bstgerList","lex-ch-bund-asList","lex-ch-bund-bblList","lex-ch-bund-abList"],"size":"10"},"chosenPaths":[],"size":11}
	# SUCHFORM={"sortOrder":"desc","sortField":"decisionDate","guiLanguage":"de","userID":"","sessionDuration":41,"aggs":{"fields":["entscheidKategorie","argvpBehoerde","gvpNumber","pubYearGvp","srCategoryList","lex-ch-bund-srList","ch-jurivocList","jud-ch-bund-bgeList","jud-ch-bund-bguList","jud-ch-bund-bvgeList","jud-ch-bund-bvgerList","jud-ch-bund-tpfList","jud-ch-bund-bstgerList","lex-ch-bund-asList","lex-ch-bund-bblList","lex-ch-bund-abList"],"size":"10"}}
	SUCHFORM={"sortOrder":"desc","sortField":"decisionDate","guiLanguage":"de","metadataDateMap":{"publicationDate":{"from":"{date}T00:00:00.000Z","to":"{date}T23:59:59.999Z"}},"userID":"","sessionDuration":41,"aggs":{"fields":["entscheidKategorie","argvpBehoerde","gvpNumber","pubYearGvp","srCategoryList","lex-ch-bund-srList","ch-jurivocList","jud-ch-bund-bgeList","jud-ch-bund-bguList","jud-ch-bund-bvgeList","jud-ch-bund-bvgerList","jud-ch-bund-tpfList","jud-ch-bund-bstgerList","lex-ch-bund-asList","lex-ch-bund-bblList","lex-ch-bund-abList"],"size":"10"}}

	STARTDATE="1900-01-01"
	INTERVALL=1024
	HOST ="https://rechtsprechung.ar.ch"
	HEADER1 = {
		"Content-Type": "text/plain;charset=utf-8",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0"}

	HEADER2 = {
		"Content-Type": "text/plain;charset=utf-8",
		"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:84.0) Gecko/20100101 Firefox/84.0",
		"Referer": "https://rechtsprechung.ar.ch/dashboard",
		"Origin": "https://rechtsprechung.ar.ch"}
		
	@classmethod
	def update_settings(cls, settings):
		super().update_settings(settings)
		settings.set("DUPEFILTER_DEBUG", True, priority="spider")
        
        