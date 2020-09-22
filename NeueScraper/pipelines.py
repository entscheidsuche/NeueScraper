# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import os
import logging
import re
import sys
import traceback
import hashlib
import scrapy
from scrapy.utils.python import to_bytes

filenamechars=re.compile("(?u)[^-\\w.]")

from urllib.parse import urlparse

from scrapy.pipelines.files import FilesPipeline


class NeuescraperPipeline:
    def process_item(self, item, spider):
        return item

class PipelineHelper:
	def file_path(self, request, response, spider=None):
		try:
			logging.info('Pipeline-Request: '+request.url)
			item=request.meta['item']
			if 'PDFUrls' in item and request.url in item['PDFUrls']:
				typ="pdf"
			elif 'HTMLUrls' in item and request.url in item['HTMLUrls']:
				typ="html"
			else:
				logging.error("Filetyp unbekannt für "+request.url)
				typ="xxx" 	
			num=item['Num']
			logging.info('Geschäftsnummer: '+num)
			edatum=item['EDatum']
			if edatum is None:
				edatum='nodate'
			filename=filenamechars.sub('_',num+"___"+edatum)+"."+typ
			dir = "undefined"
			if spider:
				dir=spider.name
				logging.info('Spider-Name: '+spider.name)	
			pfad=dir+"/"+filename
			logging.info('Pfad: '+pfad)
			return pfad
		except Exception as e:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			logging.error("Unexpected error: " + repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
			raise 



class MyFilesPipeline(FilesPipeline):
	def file_path(self, request, response=None, info=None):
		return PipelineHelper.file_path(self, request, response, info.spider if info is not None else None)

	def get_media_requests(self, item, info):
		urls = item[self.files_urls_field] if self.files_urls_field in item else []
		return [scrapy.Request(url=u, meta={"item":item}) for u in urls]

