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
from scrapy.utils.python import to_bytes

geschaeftsnummer=re.compile("(?<=dossiernummer=)[^=]+$")
filenamechars=re.compile("(?u)[^-\\w.]")

from urllib.parse import urlparse

from scrapy.pipelines.files import FilesPipeline


class NeuescraperPipeline:
    def process_item(self, item, spider):
        return item


class MyFilesPipeline(FilesPipeline):

	def file_path(self, request, response=None, info=None):
		try:
			logging.info('Pipeline-Request: '+request.url)
			match=geschaeftsnummer.search(request.url)
			num="<unknown>"
			if match:
				num=filenamechars.sub('',match.group())
			
			logging.info('Geschäftsnummer: '+num)
			filename=num+"___"+hashlib.sha1(to_bytes(request.url)).hexdigest()+".pdf"
			dir = "undefined"
			if info.spider:
				dir=info.spider.name
				logging.info('Spider-Name: '+info.spider.name)	
			pfad=dir+"/"+filename
			logging.info('Pfad: '+pfad)
			return pfad
		except Exception as e:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			logging.error("Unexpected error: " + repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
			raise 



