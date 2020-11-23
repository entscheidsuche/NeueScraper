# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from scrapy.http.cookies import CookieJar
import datetime
from NeueScraper.spiders.basis import BasisSpider

logger = logging.getLogger(__name__)

class GenfSpider(BasisSpider):
	name = 'GE_Gerichte'

	MINIMUM_PAGE_LEN = 148
	MAX_PAGES = 10000
	SUCH_URL='http://ge.ch/justice/donnees/decis/{gericht}/search?decision_from={datum}&sort_by=date&page_size=50&search_meta=dt_decision:[{datum} TO *]&Chercher=Chercher'
	gerichte={ 'capj': {'gericht': "Cour d'appel du Pouvoir judiciaire"},
				'acjc': {'gericht': "Cour de justice Cour civile", 'kammer': "Chambre civile"},
				'sommaires': {'gericht': "Cour de justice Cour civile", 'kammer': "Sommaires"},
				'caph': {'gericht': "Cour de justice Cour civile", 'kammer': "Chambre des prud'hommes"},
				'cabl': {'gericht': "Cour de justice Cour civile", 'kammer': "Chambre des baux et loyers"},
				'aj': {'gericht': "Cour de justice Cour civile", 'kammer': "Assistance Juridique"},
				'das': {'gericht': "Cour de justice Cour civile", 'kammer': "Chambre de surveillance"},
				'dcso': {'gericht': "Cour de justice Cour civile", 'kammer': "Chambre de surveillance en matière de poursuites et faillites"},
				'comtax': {'gericht': "Cour de justice Cour civile", 'kammer': "Commission de taxation des honoraires d'avocats"},
				'parp': {'gericht': "Cour de justive Cour pénale", 'kammer': "Chambre pénale d'appel et de révision"},
				'cjp': {'gericht': "Cour de justive Cour pénale", 'kammer': "Chambre pénale"},
				'pcpr': {'gericht': "Cour de justive Cour pénale", 'kammer': "Chambre pénale de recours"},
				'oca': {'gericht': "Cour de justive Cour pénale", 'kammer': "Chambre d'accusation"},
				'ata': {'gericht': "Cour de justice Cour de droit public", 'kammer': "Chambre administrative"},
				'atas': {'gericht': "Cour de justice Cour de droit public", 'kammer': "Chambre des assurances sociales"},
				'cst': {'gericht': "Cour de justice Cour de droit public", 'kammer': "Chambre constitutionnelle"},
				'jtp': {'gericht': "Tribunal pénal"},
				'dccr': {'gericht': "Tribunal administratif de première instance en matière fiscale"},
				'pjdoc': {'gericht': "Fiches de jurisprudence en matière de baux et loyers"}
	}
	
	
	def request_generator(self):
		""" Generates scrapy frist request
		"""
		# return [scrapy.Request(url=self.RESULT_PAGE_URL, method="POST", body= self.RESULT_PAGE_PAYLOAD.format(Jahr=self.START_JAHR), headers=self.HEADERS, callback=self.parse_trefferliste_unsortiert, errback=self.errback_httpbin)]
		# Erst einmal den Basisrequest machen, um Cookie zu setzen

		request_liste=[]
		start_datum=self.ab if self.ab else '01.01.1900'
		for g in self.gerichte:
			request=scrapy.Request(url=self.SUCH_URL.format(datum=start_datum, gericht=g), callback=self.parse_trefferliste, errback=self.errback_httpbin)
			request_liste.append(request)
		return [request_liste]

	def __init__(self, ab=None):
		super().__init__()
		if ab:
			self.ab=ab
		self.request_gen = self.request_generator()

	def parse_trefferliste(self, response):
		logger.info("parse_trefferliste response.status "+str(response.status))
		logger.info("parse_trefferliste Rohergebnis "+str(len(response.body))+" Zeichen")
		logger.info("parse_trefferliste Rohergebnis: "+response.body_as_unicode())


			


	def errback_httpbin(self, failure):
		# log all errback failures,
		# in case you want to do something special for some errors,
		# you may need the failure's type
		logger.error(repr(failure))
