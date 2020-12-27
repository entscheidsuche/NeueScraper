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
import json
import scrapy
import inspect
from scrapy.utils.python import to_bytes
from scrapy.utils.boto import is_botocore
from twisted.internet import defer, threads
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from io import BytesIO
from scrapy.utils.misc import md5sum
from lxml import etree
import datetime

filenamechars=re.compile("[^-a-zA-Z0-9]")
filenameparts=re.compile(r'/(?P<stamm>(?P<signatur>[^_]+_[^_]+_[^_]+)[^\.]+)\.(?P<endung>\w+)')
logger = logging.getLogger(__name__)

from urllib.parse import urlparse

from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.files import S3FilesStore
from scrapy.pipelines.files import FSFilesStore
from scrapy.pipelines.files import GCSFilesStore
from scrapy.pipelines.files import FTPFilesStore

logger = logging.getLogger(__name__)


class MyWriterPipeline:
	def open_spider(self,spider):
		logger.debug("pipeline open")

	def close_spider(self,spider):
		logger.debug("pipeline close")
		datestring=datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
		pfad_job=spider.name+"/Job_"+datestring+"_"+spider.scrapy_job.replace("/","-")+".json"
		pfad_index=spider.name+"/Index_"+datestring+"_"+spider.scrapy_job.replace("/","-")+".json"
		signaturen={}
		if spider.ab:
			job_typ="update"
		else:
			vorher=len(list(filter(lambda x:spider.previous_run['dateien'][x]['status'] in ['update',"anders_wieder_da","neu","identisch"], spider.previous_run['dateien']))) if 'dateien' in spider.previous_run else 0
			if vorher>0:
				gelesen=len(list(filter(lambda x:spider.files_written[x]['status'] in ['update',"anders_wieder_da","neu","identisch"] and not 'quelle' in spider.files_written[x], spider.files_written)))
				prozentsatz=gelesen/vorher*100
				if prozentsatz > 95:
					job_typ="komplett"
					logger.info("vorher {} Dateien, nun {} Dateien gelesen {:.2f}%".format(vorher, gelesen, prozentsatz))
				else:
					job_typ="unvollständig"
					logger.error("vorher {} Dateien, nun {} Dateien gelesen {:.2f}%".format(vorher, gelesen, prozentsatz))
			else:
				job_typ="neu"
				logging.info("keine Dokumente eines vorherigen Laufes gefunden.")

		gesamt={'gesamt':0}
		to_index={}
		for f in spider.files_written:
			# neu nicht mehr vorhandene Inhalte markieren
			if job_typ=="komplett" and 'quelle' in spider.files_written[f] and not spider.files_written[f]['status']=="nicht_mehr_da":
				spider.files_written[f]['status']='nicht_mehr_da'
				del spider.files_written[f]['quelle']
				if 'last_change' in spider.files_written[f]:
					del spider.files_written[f]['last_change']			
			s=filenameparts.search(f)
			if s is None:
				logging.error("Konnte Dateinamen "+f+" nicht aufteilen.")
			else:
				if s.group('endung')=='xml':
					if 'quelle' in spider.files_written[f]:
						count_group='vorher'
					else:
						count_group='aktuell'
					
					if spider.files_written[f]['status']=='nicht_mehr_da':
						count_typ='entfernt'
						if count_group=='aktuell':
							to_index[f]="delete"
					elif spider.files_written[f]['status'] in ['update']:
						count_typ='aktualisiert'
						if count_group=='aktuell':
							to_index[f]="update"
					elif spider.files_written[f]['status'] in ['neu', "anders_wieder_da"]:
						count_typ='neu'
						if count_group=='aktuell':
							to_index[f]="new"
					else:
						count_typ='identisch'
									
					count_eintrag=count_group+"_"+count_typ
					if not s.group('signatur') in signaturen:
						signaturen[s.group('signatur')]={'gesamt':0}
					if not count_eintrag in signaturen[s.group('signatur')]:
						signaturen[s.group('signatur')][count_eintrag]=1
					else:
						signaturen[s.group('signatur')][count_eintrag]=signaturen[s.group('signatur')][count_eintrag]+1
					if not count_eintrag in gesamt:
						gesamt[count_eintrag]=1
					else:
						gesamt[count_eintrag]=gesamt[count_eintrag]+1
					if not count_typ=='entfernt':
						signaturen[s.group('signatur')]['gesamt']=signaturen[s.group('signatur')]['gesamt']+1
						gesamt['gesamt']=gesamt['gesamt']+1			
		files_log={"spider": spider.name, "job": spider.scrapy_job, "jobtyp": job_typ, "time": datestring, "dateien": spider.files_written, 'signaturen': signaturen, 'gesamt': gesamt }
		json_content=json.dumps(files_log)
		MyS3FilesStore.shared_store.persist_file(pfad_job, BytesIO(json_content.encode(encoding='UTF-8')), info=None, ContentType='application/json', LogFlag=False)

		index_log={"spider": spider.name, "job": spider.scrapy_job, "jobtyp": job_typ, "time": datestring, "actions": to_index, 'signaturen': signaturen, 'gesamt': gesamt }
		json_content=json.dumps(index_log)
		MyS3FilesStore.shared_store.persist_file(pfad_index, BytesIO(json_content.encode(encoding='UTF-8')), info=None, ContentType='application/json', LogFlag=False)

	def process_item(self, item, spider):
		logger.debug("pipeline item")
		logFlag=True

		if 'Entscheidquellen' in item:
			upload_file_key="Entscheidquellen.csv"
			upload_file_content=item['Entscheidquellen']
			contentType="text/csv"
			logFlag=False
		elif 'Spiderliste' in item:
			upload_file_key="Spiderliste.xml"
			upload_file_content=item['Spiderliste']
			contentType='text/xml'
			logFlag=False
		elif 'Facetten' in item:
			upload_file_key="Facetten.json"
			upload_file_content=item['Facetten']
			contentType='application/json'
			logFlag=False
		
		else:					
			upload_file_content=PipelineHelper.make_xml(item,spider)
			contentType="text/xml"
			upload_file_key=PipelineHelper.file_path(item, spider)+".xml"

		MyS3FilesStore.shared_store.persist_file(upload_file_key, BytesIO(upload_file_content.encode(encoding='UTF-8')), info=None, spider=spider, meta=None, headers=None, item=item, ContentType=contentType, LogFlag=logFlag)
		
		return item
	

class MyS3FilesStore(S3FilesStore):
	AWS_ENDPOINT_URL = "s3://entscheidsuche.ch"
	AWS_REGION_NAME = "eu-west-3"
	AWS_USE_SSL = None
	AWS_VERIFY = None
	shared_s3_client = None
	shared_s3_bucket = None
	shared_s3_prefix = None
	shared_store = None

	POLICY = 'private'  # Overriden from settings.FILES_STORE_S3_ACL in FilesPipeline.from_settings
	HEADERS = {
		'Cache-Control': 'max-age=172800',
	}

	def __init__(self,uri=None):
		if uri is None:
			logger.debug("__init__ ohne uri aufgerufen")
			uri='s3://entscheidsuche.ch/scraper'
		else:
			logger.debug("__init__ mit uri '"+uri+"' aufgerufen")		

		self.is_botocore = is_botocore()
		if self.is_botocore:
			import botocore.session
			session = botocore.session.get_session()
			self.s3_client = session.create_client(
				's3',
				aws_access_key_id=self.AWS_ACCESS_KEY_ID,
				aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY,
				endpoint_url=self.AWS_ENDPOINT_URL,
				region_name=self.AWS_REGION_NAME,
				use_ssl=self.AWS_USE_SSL,
				verify=self.AWS_VERIFY
			)
			MyS3FilesStore.shared_s3_client=self.s3_client #Damit auch die anderen Schreiboperationen diesen Client mit nutzen können
		else:
			from boto.s3.connection import S3Connection
			self.S3Connection = S3Connection(self.AWS_ACCESS_KEY_ID, self.AWS_SECRET_ACCESS_KEY)
		if not uri.startswith("s3://"):
			raise ValueError(f"Incorrect URI scheme in {uri}, expected 's3'")
		self.bucket, self.prefix = uri[5:].split('/', 1)
		MyS3FilesStore.shared_s3_bucket=self.bucket
		MyS3FilesStore.shared_s3_prefix=self.prefix
		MyS3FilesStore.shared_store=self
		
	def stat_file(self, path, info):
		def _onsuccess(boto_key):
			if self.is_botocore:
				checksum = boto_key['ETag'].strip('"')
				last_modified = boto_key['LastModified']
				modified_stamp = time.mktime(last_modified.timetuple())
			else:
				checksum = boto_key.etag.strip('"')
				last_modified = boto_key.last_modified
				modified_tuple = parsedate_tz(last_modified)
				modified_stamp = int(mktime_tz(modified_tuple))
			return {'checksum': checksum, 'last_modified': modified_stamp}
		return self._get_boto_key(path).addCallback(_onsuccess)

	def persist_file(self, path, buf, info=None, meta=None, headers=None, item=None, spider=None, ContentType=None, LogFlag=True, checksum=None):
		if meta==None:
			meta={}

		if (not spider) and info:
			spider=info.spider
		# Keine Tags machen sondern Metadaten, da Tags teuer sind.
		if spider:
			PipelineHelper.get_meta(item, spider,meta)

		# Upload file to S3 storage
		key_name = f'{self.prefix}{path}'
		logger.debug("pf key_name: "+key_name)
		buf.seek(0)
		if checksum is None:
			checksum=md5sum(buf)
			buf.seek(0)
		existiert_bereits=False
		if LogFlag and spider:
			neustatus='neu'
			last_change=None
			if spider.previous_run:
				if path in spider.previous_run['dateien']:
					oldfile=spider.previous_run['dateien'][path]
					if 'status' in oldfile and 'checksum' in oldfile:
						altstatus=oldfile['status']
						altchecksum=oldfile['checksum']
						altlast_change=oldfile['last_change'] if 'last_change' in oldfile else None
						if altchecksum==checksum:
							if altstatus == "nicht_mehr_da":
								neustatus="identisch_wieder_da"
							else:
								neustatus="identisch"
								last_change=altlast_change if altlast_change else spider.previous_job
							existiert_bereits=True
						else:
							if altstatus =="nicht_mehr_da":
								neustatus="anders_wieder_da"
							else:
								neustatus="update"
			if last_change:
				spider.files_written[path]={'checksum': checksum, "status": neustatus, "last_change": last_change}
			else:
				spider.files_written[path]={'checksum': checksum, "status": neustatus}
		if not existiert_bereits:
			if self.is_botocore:
				logger.debug("pf is_botocore")
				extra = self._headers_to_botocore_kwargs(self.HEADERS)
				if headers:
					extra.update(self._headers_to_botocore_kwargs(headers))
				logger.debug("pf schreibe nun")
				return threads.deferToThread(
					self.s3_client.put_object,
					Bucket=self.bucket,
					Key=key_name,
					Body=buf,
					Metadata={k: str(v) for k, v in (meta or {}).items()},
					ACL=self.POLICY,
					ContentType=ContentType,
					**extra)
			else: #ohne botocore noch keine Metadaten und Tags
				logger.debug("pf not is_botocore")
				b = self._get_boto_bucket()
				k = b.new_key(key_name)
				if meta:
					for metakey, metavalue in meta.items():
						k.set_metadata(metakey, str(metavalue))
				h = self.HEADERS.copy()
				if headers:
					h.update(headers)
				return threads.deferToThread(
					k.set_contents_from_string, buf.getvalue(),
					headers=h, policy=self.POLICY)
		
	def _get_boto_bucket(self):
		logger.debug("AWS_ACCESS_KEY_ID: "+self.AWS_ACCESS_KEY_ID+"AWS_SECRET_ACCESS_KEY"+self.AWS_SECRET_ACCESS_KEY)
		# disable ssl (is_secure=False) because of this python bug:
		# https://bugs.python.org/issue5103
		c = self.S3Connection(self.AWS_ACCESS_KEY_ID, self.AWS_SECRET_ACCESS_KEY, is_secure=False)
		return c.get_bucket(self.bucket, validate=False)

	def _get_boto_key(self, path):
		key_name = f'{self.prefix}{path}'
		logger.debug("gbk key_name: "+key_name)
		if self.is_botocore:
			logger.debug("gbk is_botocore")
			return threads.deferToThread(
				self.s3_client.head_object,
				Bucket=self.bucket,
				Key=key_name)
		else:
			logger.debug("gkb not is_botocore")
			b = self._get_boto_bucket()
			return threads.deferToThread(b.get_key, key_name)


class NeuescraperPipeline:
    def process_item(self, item, spider):
        return item

class PipelineHelper:
	@staticmethod
	def write_html(html_content, item, spider):
		html_pfad=PipelineHelper.file_path(item, spider)+".html"
		logger.debug("html_pfad: "+html_pfad)
		# Die md5-Checksum bereits vorher berechnen, da das Abspeichern deferred erfolgt.
		buf=BytesIO(html_content.encode(encoding='UTF-8'))
		buf.seek(0)
		checksum=md5sum(buf)
		buf.seek(0)
		MyS3FilesStore.shared_store.persist_file(html_pfad, buf, info=None, spider=spider, meta=None, headers=None, item=item, ContentType='text/html', checksum=checksum)
		item['HTMLFiles']=[{'url': item['HTMLUrls'][0], 'path': html_pfad, 'checksum': checksum}]
	
	@staticmethod
	def file_path(item, spider=None):
		try:
			num=item['Num']
			logger.debug('Geschäftsnummer: '+num)
			if (not 'EDatum' in item) or item['EDatum'] is None:
				if 'PDatum' in item and item['PDatum'] is not None:
					edatum=item['PDatum']
				else:
					edatum='nodate'
			else:
				edatum=item['EDatum']
			filename=filenamechars.sub('-',num)+"_"+filenamechars.sub('-',edatum)
			dir = "undefined"
			if spider:
				dir=spider.name
				logger.debug('Spider-Name: '+spider.name)
				prefix=item['Signatur']
			pfad=dir+"/"+prefix+"_"+filename
			logger.debug('Pfad: '+pfad)
			return pfad
		except Exception as e:
			exc_type, exc_value, exc_traceback = sys.exc_info()
			logger.error("Unexpected error: " + repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
			raise
			
	@staticmethod	
	def NC(string, replace="", info=None, warning=None, error=None):
		if string is None:
			if info:
				logger.info(info+ " [None found]")
			if warning:
				logger.warning(warning+ " [None found]")
			if error:
				logger.error(error+ " [None found]")
			string=replace
		return string

	@staticmethod
	def get_meta(item, spider,meta):
		meta['Spider']=spider.name
		meta['ScrapyJob']=spider.scrapy_job
		if 'Signatur' in item:
			meta['Signatur']=item['Signatur']
			meta['Kanton']=item['Signatur'][:2]
		if 'EDatum' in item:
			meta['Entscheiddatum']=item['EDatum']
		if 'Num' in item:
			meta['Geschaeftsnummer']=filenamechars.sub('-',item['Num'])
		if 'PDFFiles' in item and item['PDFFiles']:
			meta['PDF']='PDF'
		if 'HTMLFiles' in item and item['HTMLFiles']:
			meta['HTML']='HTML'
		logger.debug("Meta: "+json.dumps(meta))

	@staticmethod
	def xml_add_element(parent, key, value):
		element = etree.Element(key)
		element.text=value
		parent.append(element)
		return element

	@staticmethod
	def make_xml(item,spider):
		# Alles auskommentieren, was vom Spiderlauf abhängig ist.	
		if 'Num' in item:
			logger.info("Geschäftsnummer: "+item['Num'])

		if not('PDFFiles' in item and item['PDFFiles']) and not('HTMLFiles' in item and item['HTMLFiles']):
			logger.warning("weder PDF noch HTML geholt")
			#DropItem später nur dann, wenn auch kein HTML geholt
			raise DropItem(f"Missing File for {item['Num']}")

		root = etree.Element('Entscheid')
		meta = etree.Element('Metainfos')
		root.append(meta)
		PipelineHelper.xml_add_element(meta,'Signatur',item['Signatur'])
		PipelineHelper.xml_add_element(meta,'Spider',spider.name)
		#PipelineHelper.xml_add_element(meta,'Job',spider.scrapy_job)
		PipelineHelper.xml_add_element(meta,'Kanton',item['Signatur'][:2].lower())
		if spider.ebenen > 1 and 'Gericht' in item:
			PipelineHelper.xml_add_element(meta,'Gericht',item['Gericht'])
		if spider.ebenen > 2 and 'Kammer' in item:
			PipelineHelper.xml_add_element(meta,'Kammer',item['Kammer'])
		if 'Num' in item:
			PipelineHelper.xml_add_element(meta,'Geschaeftsnummer',item['Num'])
		if 'EDatum' in item:
			PipelineHelper.xml_add_element(meta,'EDatum',item['EDatum'])
		if 'PDFFiles' in item and item['PDFFiles']:
			PipelineHelper.xml_add_element(meta,'PDFFile',item['PDFFiles'][0]['path']).set('Checksum',item['PDFFiles'][0]['checksum'])
		if 'HTMLFiles' in item and item['HTMLFiles']:
			PipelineHelper.xml_add_element(meta,'HTMLFile',item['HTMLFiles'][0]['path']).set('Checksum',item['HTMLFiles'][0]['checksum'])
		

		treffer = etree.Element('Treffer')
		root.append(treffer)
		quelle = etree.Element('Quelle')
		treffer.append(quelle)
		if 'Gerichtsbarkeit' in item:
			PipelineHelper.xml_add_element(quelle,'Gerichtsbarkeit',item['Gerichtsbarkeit'])
		if 'VGericht' in item:
			PipelineHelper.xml_add_element(quelle,'Gericht',item['VGericht'])
		elif 'Gericht' in item:
			PipelineHelper.xml_add_element(quelle,'Gericht',item['Gericht'])	
		if 'VKammer' in item:
			PipelineHelper.xml_add_element(quelle,'Kammer',item['VKammer'])
		elif 'Kammer' in item:
			PipelineHelper.xml_add_element(quelle,'Kammer',item['Kammer'])
		if 'Num' in item:
			PipelineHelper.xml_add_element(quelle,'Geschaeftsnummer',item['Num'])
		if 'EDatum' in item:
			PipelineHelper.xml_add_element(quelle,'EDatum',item['EDatum'])
		if 'PDFFiles' in item and item['PDFFiles']:
			PipelineHelper.xml_add_element(quelle,'PDF','')
		if 'HTMLFiles' in item and item['HTMLFiles']:
			PipelineHelper.xml_add_element(quelle,'HTML','')
		
		kurz = etree.Element('Kurz')
		treffer.append(kurz)
		if 'Titel' in item:
			PipelineHelper.xml_add_element(kurz,'Titel',item['Titel'])
		if 'Leitsatz' in item:
			PipelineHelper.xml_add_element(kurz,'Leitsatz',item['Leitsatz'])
		if 'Rechtsgebiet' in item:
			PipelineHelper.xml_add_element(kurz,'Rechtsgebiet',item['Rechtsgebiet'])
		if 'Entscheidart' in item:
			PipelineHelper.xml_add_element(kurz,'Entscheidart',item['Entscheidart'])
		sonst = etree.Element('Sonst')
		treffer.append(sonst)
		if 'PDatum' in item:
			PipelineHelper.xml_add_element(sonst,'PDatum',item['PDatum'])
		if 'Weiterzug' in item:
			PipelineHelper.xml_add_element(sonst,'Weiterzug',item['Weiterzug'])
		source = etree.Element('Source')
		treffer.append(source)
		if 'DocID' in item:
			PipelineHelper.xml_add_element(source,'DocID',item['DocID'])
		if 'PdfUrl' in item:
			PipelineHelper.xml_add_element(source,'PdfUrl',item['PdfUrl'][0])
		if 'HtmlUrl' in item:
			PipelineHelper.xml_add_element(source,'HtmlUrl',item['HtmlUrl'][0])
#		if 'Raw' in item:
#			PipelineHelper.xml_add_element(source,'Raw',etree.CDATA(item['Raw'].replace("<","(").replace(">",")")))
	
		xml_content = '<?xml version="1.0" encoding="UTF-8"?><?xml-stylesheet type="text/xsl" href="/Entscheid.xsl"?>\n'
		xml_content = xml_content+str(etree.tostring(root, pretty_print=True),"ascii")
		return xml_content

class MyFilesPipeline(FilesPipeline):
	STORE_SCHEMES = {
		'': FSFilesStore,
		'file': FSFilesStore,
		's3': MyS3FilesStore,
		'gs': GCSFilesStore,
		'ftp': FTPFilesStore
	}

	def file_path(self, request, response=None, info=None, item=None):
		if item is None:
			item=request.meta['item']
		return PipelineHelper.file_path(item, info.spider if info is not None else None)+".pdf"

	def get_media_requests(self, item, info):
		urls = item[self.files_urls_field] if self.files_urls_field in item else []
		return [scrapy.Request(url=u, meta={"item":item}) for u in urls]
		

	def file_downloaded(self, response, request, info=None, item=None):
		if item is None:
			item=request.meta['item']
			logger.debug('item in file_downloaded gesetzt')
		else:
			logger.debug('item war in file_downloaded bereits gesetzt')		
		path = self.file_path(request, response, info, item=item)
		ContentType='application/pdf' if path[-4:]=='.pdf' else None
		buf = BytesIO(response.body)
		checksum = md5sum(buf)
		buf.seek(0)
		self.store.persist_file(path, buf, info, item=item, ContentType=ContentType) # Parameter item wurde hinzugefügt. store muss dazu angepasst werden (wurde hier für S3 getan)
		return checksum

	
