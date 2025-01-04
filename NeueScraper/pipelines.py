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
import operator
import pysftp
import posixpath
import pathlib
from scrapy.settings import Settings
from scrapy.exceptions import IgnoreRequest, NotConfigured
import requests
import hashlib


filenamechars=re.compile("[^-a-zA-Z0-9]")
filenameparts=re.compile(r'/(?P<stamm>(?P<signatur>[^_]+_[^_]+_[^_]+)[^\.]+)\.(?P<endung>\w+)')
logger = logging.getLogger(__name__)

from urllib.parse import urlparse

from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.files import S3FilesStore
from scrapy.pipelines.files import FSFilesStore
from scrapy.pipelines.files import GCSFilesStore
from scrapy.pipelines.files import FTPFilesStore

class MyWriterPipeline:
	def open_spider(self,spider):
		logger.debug("pipeline open")

	def close_spider(self,spider):
		logger.debug("pipeline close")
		datestring=datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
		pfad_job="Jobs/"+spider.name+"/Job_"+datestring+"_"+spider.scrapy_job.replace("/","-")+".json"
		pfad_index="Index/"+spider.name+"/Index_"+datestring+"_"+spider.scrapy_job.replace("/","-")+".json"
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
				if spider.neu == 'neu':
					job_typ="neu"
					logger.info("Löschlauf")
				else:
					job_typ="komplett"
					logger.info("keine Dokumente eines vorherigen Laufes gefunden.")

		gesamt={'gesamt':0}
		to_index={}
		toBeDeleted=[]
		for f in spider.files_written:
			# Konsistenz überprüfen, damit einzelne .json ohne .html oder .pdf files nicht übrig bleiben
			if f[-5:]=='.json':
				pdf_file=f[:-5]+".pdf"
				html_file=f[:-5]+".html"
				if not (pdf_file in spider.files_written or html_file in spider.files_written):
					#PDF und HTML fehlen und waren noch nie da:
					logger.error("Zu "+f+" fehlen HTML und PDF und waren noch nie da.")
					toBeDeleted.append(f)
#				elif pdf_file in spider.files_written and 'quelle' in spider.files_written[pdf_file]:
#					# Datei war schon mal da, fehlt aber jetzt oder ist beschädigt
#					logger.error("Zu "+f+" fehlen HTML und PDF, PDF war aber schon mal da.")
#					# so tun, als ob das Dokument nicht mehr gefunden worden wäre
#					spider.files_written[f]['quelle']=spider.files_written[pdf_file]['quelle']
#				elif html_file in spider.files_written and 'quelle' in spider.files.written[html_file]:
#					# Datei war schon mal da, fehlt aber jetzt oder ist beschädigt
#					logger.error("Zu "+f+" fehlen HTML und PDF, HTML war aber schon mal da.")
#					# so tun, als ob das Dokument nicht mehr gefunden worden wäre
#					spider.files_written[f]['quelle']=spider.files_written[html_file]['quelle']
		for f in toBeDeleted:
			del spider.files_written[f]

		for f in spider.files_written:
			# neu nicht mehr vorhandene Inhalte markieren
			if job_typ=="komplett" and 'quelle' in spider.files_written[f] and not spider.files_written[f]['status']=="nicht_mehr_da":
				spider.files_written[f]['status']='nicht_mehr_da'
				del spider.files_written[f]['quelle']
				if 'last_change' in spider.files_written[f]:
					del spider.files_written[f]['last_change']
			s=filenameparts.search(f)
			if s is None:
				logger.error("Konnte Dateinamen "+f+" nicht aufteilen.")
			else:
				logger.debug(f"Dateiname: {f} mit Endung {s.group('endung')}")
				if s.group('endung')=='json':
					logger.debug(f"Dateiname {f} ist json.")
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
		json_jobs=json.dumps(files_log)
		sitemaps=PipelineHelper.gen_sitemap(spider.files_written)
		zahl=1
		for sitemap in sitemaps:
			pfad_sitemap="Sitemaps/"+spider.name+"_"+str(zahl)+".xml"
			MyFilesPipeline.common_store.persist_file(pfad_sitemap, BytesIO(sitemap.encode(encoding='UTF-8')), info=None, ContentType='text/xml', LogFlag=False)
			zahl += 1
		MyFilesPipeline.common_store.persist_file(pfad_job, BytesIO(json_jobs.encode(encoding='UTF-8')), info=None, ContentType='application/json', LogFlag=False)
		index_log={"spider": spider.name, "job": spider.scrapy_job, "jobtyp": job_typ, "time": datestring, "actions": to_index, 'signaturen': signaturen, 'gesamt': gesamt }
		json_index=json.dumps(index_log)
		MyFilesPipeline.common_store.persist_file(pfad_index, BytesIO(json_index.encode(encoding='UTF-8')), info=None, ContentType='application/json', LogFlag=False)
		# Nachdem die Pipeline durchgelaufen ist, den Index-Request synchron machen
		try:
			antwort=requests.post("https://entscheidsuche.pansoft.de", data=json_jobs, headers= {'Content-Type': 'application/json'}, timeout=3600, verify=False)
			# logger.info("Indexierungsrequest mit Daten: "+json.dumps(json_jobs))
			logger.info("Indexierungsrequest mit Antwort: "+str(antwort.status_code))
			if antwort.status_code >=300:
				logger.error("Indexierungsfehler: "+antwort.text)
		except Exception as e:
			# Später hier zwischen Fehler und Timeout unterscheiden
			logger.error("Fehler beim Indexieren: " + str(e.__class__))

				
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
			upload_file_key="Facetten_alle.json"
			upload_file_content=item['Facetten']
			contentType='application/json'
			logFlag=False
		elif 'htaccess' in item:
			upload_file_key=".htaccess"
			upload_file_content=item['htaccess']
			contentType='text/plain'
			logFlag=False

		else:
			pfad=PipelineHelper.file_path(item, spider)
			if 'Num' in item:
				logger.info("Geschäftsnummer: "+item['Num'])
			else:
				logger.warning("keine Geschäftsnummer!")
				item['Num']='unknown'
			pdf_da = ('PDFFiles' in item and item['PDFFiles'])
			zweitnum=[]
			if pdf_da: # Schauen ob das PDF wirklich da ist
				if not (item['PDFFiles'][0]['path'] in spider.files_written):
					logger.error(item['PDFFiles'][0]['path']+" wurde nicht geschrieben.")
					pdf_da=False
				else:
					pdfpfad=item['PDFFiles'][0]['path'][:-4]
					if not(pdfpfad==pfad):
						logger.error("Pdf-file hat Pfad "+pdfpfad+" statt "+pfad+" und gehört bereits zu einem anderen Dokument.")
						if pdfpfad in spider.numliste:
							zweitnum=spider.numliste[pdfpfad]
							pfad=pdfpfad
						else:
							logger.error("Dokument "+pdfpfad+" noch nicht eingetragen, joinen daher nicht möglich.")
							raise DropItem(f"PDF hat Pfad {pdfpfad} statt {pfad} und Dateien können nicht zusammengeführt werden für {item['Num']}")
			if not(pdf_da) and not('HTMLFiles' in item and item['HTMLFiles']):
				logger.error("weder PDF noch HTML geholt ("+item['Num']+")")
				# Bei doppelten Dateien muss ich alle entfernen
				json_file_key=pfad+".json"
				if json_file_key in spider.files_written and not 'quelle' in spider.files_written[json_file_key]:
					if (pfad+".pdf" in spider.files_written and not 'quelle' in spider.files_written[pfad+".pdf"]) or (pfad+".html" in spider.files_written and not 'quelle' in spider.files_written[pfad+".html"]):
						logger.warning("zu einem defekten oder nicht vorhandenem pdf gibt es bereits ein .json mit korrektem .pdf oder .html. Daher bleib das json "+json_file_key)
					else:
						logger.warning("bereits geschriebenes json wegen fehlendem/kaputten PDF/HTML entfernt: "+item['Num']+", "+json_file_key+")")
						del spider.files_written[json_file_key];
				else:
					logger.warning("noch nicht bereits geschriebenes json bei fehlendem/kaputten PDF/HTML entfernt: "+item['Num']+", "+json_file_key+")")
					
				
				# Sollen wir Urteile ohne Text auch nehmen?
				raise DropItem(f"Missing File for {item['Num']}")
			else:
				#upload_file_content=PipelineHelper.make_xml(item,spider)
				#vorher noch das json Schreiben
				json_content, json_checksum = PipelineHelper.make_json(item,spider,pfad,zweitnum)
				json_contentType="application/json"
				json_file_key=pfad+".json"
				#MyS3FilesStore.shared_store.persist_file(json_file_key, BytesIO(json_content.encode(encoding='UTF-8')), info=None, spider=spider, meta=None, headers=None, item=item, ContentType=json_contentType, LogFlag=logFlag, checksum=json_checksum)
				MyFilesPipeline.common_store.persist_file(json_file_key, BytesIO(json_content.encode(encoding='UTF-8')), info=None, spider=spider, meta=None, headers=None, item=item, ContentType=json_contentType, LogFlag=logFlag, checksum=json_checksum)
			
				#contentType="text/xml"
				#upload_file_key=PipelineHelper.file_path(item, spider)+".xml"
				upload_file_key=None

		#MyS3FilesStore.shared_store.persist_file(upload_file_key, BytesIO(upload_file_content.encode(encoding='UTF-8')), info=None, spider=spider, meta=None, headers=None, item=item, ContentType=contentType, LogFlag=logFlag)
		if upload_file_key:
			MyFilesPipeline.common_store.persist_file(upload_file_key, BytesIO(upload_file_content.encode(encoding='UTF-8')), info=None, spider=spider, meta=None, headers=None, item=item, ContentType=contentType, LogFlag=logFlag)

		return item



class SFTPFilesStore:
	SFTP_USERNAME = None
	SFTP_PASSWORD = None
	BASEDIR='/home/entsche1/public_html/entscheide/docs'
	instanz = None
	sftp_instanz = None
	sftp_instanz_dir = None
	sftp_usage_count = 0

	def __init__(self, uri=None):
		if uri is None:
			logger.debug("__init__ ohne uri aufgerufen")
			settings = Settings()
			if settings:
				uri=settings['FILES_STORE']
			else:
				logger.error("keine uri gesetzt und auch kein settings bekommen")
			uri='sftps://entscheidsuche.ch'
		else:
			logger.debug("__init__ mit uri '"+uri+"' aufgerufen")

		if not uri.startswith("sftp://"):
			logger.error(f"Incorrect URI scheme in {uri}, expected 'sftp'")
			raise ValueError(f"Incorrect URI scheme in {uri}, expected 'sftp'")
		SFTPFilesStore.instanz=self
		logger.info("SFTP Instanz gesetzt.")
		u = urlparse(uri)
		self.host = u.hostname
		self.username = u.username or self.SFTP_USERNAME
		self.password = u.password or self.SFTP_PASSWORD
		self.basedir = self.BASEDIR
		logger.info(f"init sftp: Username ({self.username}), Passwort({('*'*len(self.password))}) und Basedir({self.basedir}) gesetzt")

	def persist_file(self, path, buf, info=None, meta=None, headers=None, item=None, spider=None, ContentType=None, LogFlag=True, checksum=None):
		logger.info(f"SFTP-persist_file Pfad: {path}")
		if (not spider) and info:
			spider=info.spider

		# Upload file to SFTP
		existiert_bereits=PipelineHelper.checkfile(spider, path, buf, checksum,LogFlag)
		if not existiert_bereits:
			fullpath = f'{self.basedir}/{path}'
			SFTPFilesStore.sftp_store_file(path=fullpath, file=buf, host=self.host, username=self.username, password=self.password)

	def stat_file(self, path, info):
		return {}


	@staticmethod
	def sftp_makedirs_cwd(sftp, path, first_call=True):
		"""Set the current directory of the FTP connection given in the ``ftp``
		argument (as a ftplib.FTP object), creating all parent directories if they
		don't exist. The ftplib.FTP object must be already connected and logged in.
		"""
		
		logger.info(f"sftp_makedirs: Path {path}, first_call {first_call}")
		try:
			sftp.chdir(path)
		except:
			SFTPFilesStore.sftp_makedirs_cwd(sftp, posixpath.dirname(path), False)
			logger.info(f"mkdir {path}")
			sftp.mkdir(path)
			if first_call:
				sftp.chdir(path)

	@staticmethod
	def sftp_store_file(*, path, file, host, username, password):
		"""Opens a FTP connection with passed credentials,sets current directory
		to the directory extracted from given path, then uploads the file to server
		"""
		logger.info(f"sftp_store_file: Host: {host}, Path: {path}, Username ({username}), Passwort({('*'*len(password))}) gesetzt")
		cnopts=pysftp.CnOpts()
		# Eigentlich sollte hier auf ein Hostsfile zugegriffen werden, aber das geht nicht so einfach.
		cnopts.hostkeys = None
		try:
			sftp=None
			file.seek(0)
			dirname, filename = posixpath.split(path)
			sftp=None
			if SFTPFilesStore.sftp_instanz and SFTPFilesStore.sftp_instanz_dir == dirname:
				if SFTPFilesStore.sftp_usage_count > 1000: # ab und zu mal neue Verbindung verwenden
					sftp=None
					SFTPFilesStore.sftp_instanz=None
					SFTPFilesStore.sftp_instanz_dir = None
					SFTPFilesStore.sftp_usage_count = 0
					sftp.close()
				sftp=SFTPFilesStore.sftp_instanz
				try:
					logger.info(f"Schreibe nun in bereits geöfnnete sftp-Verbindung in Pfad {path} die Datei {filename}")
					sftp.putfo(file,filename, confirm=False)
					file.close()
				except:
					logger.error("Inner SFTP Exception mit bestehender Verbidnung " +str(e.__class__) +" occurred.")
					logger.info("versuche es erneut")
					file.seek(0)
					sftp=None
					SFTPFilesStore.sftp_instanz=None
					SFTPFilesStore.sftp_instanz_dir = None
			if sftp is None:
				sftp=pysftp.Connection(host=host, username=username, password=password, cnopts=cnopts, log=True)
				if sftp:
					try:
						SFTPFilesStore.sftp_makedirs_cwd(sftp, dirname)
						logger.info(f"Schreibe in neue Verbindung für Pfad {path} die Datei {filename}")
						sftp.putfo(file,filename, confirm=False)
						file.close()
						SFTPFilesStore.sftp_instanz=sftp
						SFTPFilesStore.sftp_instanz_dir = dirname
						SFTPFilesStore.sftp_usage_count = 0
					except Exception as e:
						logger.error("Inner SFTP Exception mit neuer Verbindung " +str(e.__class__) +" occurred.")
				else:
					logger.error("Konnte keine sftp-Verbindung öffnen.")
		except Exception as e:
			logger.error("Outer SFTP Exception " +str(e) +" occurred.")




class MyS3FilesStore(S3FilesStore):
	AWS_ENDPOINT_URL = "s3://entscheidsuche.ch"
	AWS_REGION_NAME = "eu-west-3"
	AWS_USE_SSL = None
	AWS_VERIFY = None
	shared_s3_bucket = None
	shared_s3_prefix = None
	instanz = None

	POLICY = 'private'  # Overriden from settings.FILES_STORE_S3_ACL in FilesPipeline.from_settings
	HEADERS = {
		'Cache-Control': 'max-age=172800',
	}

	def __init__(self,uri=None):
		if uri is None:
			logger.debug("__init__ ohne uri aufgerufen")
			settings = Settings()
			if settings:
				uri=settings['FILES_STORE']
			else:
				logger.error("keine Store_uri gesetzt und auch kein settings bekommen")
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
		logger.info("_common_store_ in MyS3FilesStore gesetzt")
		MyS3FilesStore.insanz=self
		logger.info("SFTP Instanz gesetzt.")

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
		logger.info(f"S3-persist_file Pfad: {path}")
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
		existiert_bereits=PipelineHelper.checkfile(spider, path, buf, checksum,LogFlag)
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

	# Sprache des HTML erkennen, Header ggf. davor setzen und schreiben

	WOERTER={ "de": ["der","die","das","ein","eine","einer","er","sie","ihn","hat","hatte","hätte","ist","war","sind"],"fr": ["le","lui","elle","je","on","vous","nous","leur","qui","quand","parce","que","faire","sont","vont"], "it": ["della","del","di","casi","una","al","questa","più","primo","grado","che","diritto","leggi","corte"]}
	
	#REGS={l: re.compile(r"\b(?:"+"|".join(WOERTER[l])+r")\b") for l in WOERTER}

	
	der=re.compile(r"\b(?:"+"|".join(WOERTER["de"])+r")\b")
	dfr=re.compile(r"\b(?:"+"|".join(WOERTER["fr"])+r")\b")
	dit=re.compile(r"\b(?:"+"|".join(WOERTER["it"])+r")\b")

	REGS={'de': der, 'fr': dfr, 'it': dit}
	
	reDOCTYPE=re.compile(r"<!DOCTYPE ")
	reHTML=re.compile("<html",re.IGNORECASE)
	reHEAD=re.compile("<head>",re.IGNORECASE)
	reBODY=re.compile("<body",re.IGNORECASE)
	reMETA=re.compile("<meta",re.IGNORECASE)
	reUTF=re.compile('charset="utf-8"',re.IGNORECASE)

	@classmethod
	def write_html(self,html_content, item, spider):
		lang=max(self.REGS, key=lambda key: len(self.REGS[key].findall(html_content)))
		item['Sprache']=lang

		doctype=self.reDOCTYPE.search(html_content)
		html=self.reHTML.search(html_content)
		head=self.reHEAD.search(html_content)
		body=self.reBODY.search(html_content)
		meta=self.reMETA.search(html_content)
		utf=self.reUTF.search(html_content)

		if body is None:
			html_content='<!DOCTYPE html><html lang="'+lang+'"><head><meta charset="utf-8"/></head><body>'+html_content+"</body></html>"
		if utf is None:
			if meta:
				html_content=html_content[:meta.start()]+'<meta charset="utf-8"/>'+html_content[meta.start():]
			elif head:
				html_content=html_content[:head.span()[1]]+'<meta charset="utf-8"/>'+html_content[head.span()[1]:]
			else:
				html_content='<!DOCTYPE html><html lang="'+lang+'"><head><meta charset="utf-8"/></head>'+html_content+"</html>"
		else:
			if head is None:
				html_content='<!DOCTYPE html><html lang="'+lang+'"><head><meta charset="utf-8"/></head>'+html_content+"</html>"
			elif html is None:
				html_content='<!DOCTYPE html><html lang="'+lang+'">'+html_content+"</html>"
			elif doctype is None:
				html_content='<!DOCTYPE html>'+html_content

		html_pfad=PipelineHelper.file_path(item, spider)+".html"
		logger.info("html_pfad: "+html_pfad)
		# Die md5-Checksum bereits vorher berechnen, da das Abspeichern deferred erfolgt.
		buf=BytesIO(html_content.encode(encoding='UTF-8'))
		buf.seek(0)
		checksum=md5sum(buf)
		buf.seek(0)
		MyFilesPipeline.common_store.persist_file(html_pfad, buf, info=None, spider=spider, meta=None, headers=None, item=item, ContentType='text/html', checksum=checksum)
		item['HTMLFiles']=[{'url': item['HTMLUrls'][0], 'path': html_pfad, 'checksum': checksum}]

	@staticmethod
	def checkfile(spider, path, buf, checksum,LogFlag):
		scrapedate = datetime.datetime.now().strftime("%Y-%m-%d")
		buf.seek(0)
		if path[-4:]=='.pdf':
			ende = buf.getvalue()[-10:]
			if not (b'%%EOF' in ende):
				logger.error("Datei "+path+" enthält keine PDF-Endemarkierung in: "+ende.decode('iso-8859-1'))
				if path in spider.files_written:
					del spider.files_written[path]
				return True
			else:
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
						if 'last_change' in oldfile:
							altlast_change=oldfile['last_change']
						else:
							altlast_change=None
						if altchecksum==checksum:
							# Alle alten Scrapingdaten werden auf 1.1.2023 gesetzt
							if 'scrapedate' in oldfile:
								scrapedate=oldfile['scrapedate']
							else:
								scrapedate='2023-01-01'
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
				spider.files_written[path]={'checksum': checksum, "status": neustatus, "last_change": last_change, "scrapedate": scrapedate}
			else:
				spider.files_written[path]={'checksum': checksum, "status": neustatus, "scrapedate": scrapedate}
		return existiert_bereits

	@staticmethod
	def file_path(item, spider=None):
		try:
			num=item['Num']
			logger.info('Geschäftsnummer: '+num)
			if num=="":
				if 'PFDUrls' in item:
					num+=item['PDFUrls'][0]
				if 'HTMLUrls' in item:
					num+=item['HTMLUrls'][0]
				if 'Titel' in item:
					num+=item['Titel']
				if 'Leitsatz' in item:				
					num+=item['Leitsatz']
				if 'Rechtsgebiet' in item:
					num+=item['Rechtsgebiet']
				if 'VGericht' in item:
					num+=item['VGericht']
				if 'VKammer' in item:
					num+=item['VKammer']
				num=hashlib.md5(num.encode("UTF-8")).hexdigest()
			if (not 'EDatum' in item) or item['EDatum'] is None:
				if 'PDatum' in item and item['PDatum'] is not None:
					edatum=item['PDatum']
				else:
					edatum='nodate'
			else:
				edatum=item['EDatum']
			filename=filenamechars.sub('-',num[:20])+"_"+filenamechars.sub('-',edatum)
			dir = "undefined"
			if spider:
				dir=spider.name
				logger.debug('Spider-Name: '+spider.name)
				prefix=item['Signatur']
			pfad=dir+"/"+prefix+"_"+filename
			logger.info('Pfad: '+pfad)
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
		return string.strip()

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
	def make_json(item,spider,pfad,zweitnum):
		eintrag={}
		eintrag['Signatur']=item['Signatur']
		eintrag['Spider']=spider.name
		if 'Sprache' in item:
			eintrag['Sprache']=item['Sprache']
		akt_jahr=datetime.datetime.today().year
		if 'EDatum' in item and item['EDatum'] and item['EDatum']!="nodate" and int(item['EDatum'][:4])<=akt_jahr:
			eintrag['Datum']=item['EDatum']
		elif 'PDatum' in item and item['PDatum']  and item['PDatum']!="nodate" and int(item['PDatum'][:4])<=akt_jahr:
			eintrag['Datum']=item['PDatum']
		elif 'SDatum' in item and item['SDatum']  and item['SDatum']!="nodate" and int(item['SDatum'][:4])<=akt_jahr:
			eintrag['Datum']=item['SDatum']
		else:
			eintrag['Datum']=spider.ERSATZDATUM
		if len(eintrag['Datum'])==4:
			eintrag['Datum']+="-01-01"

		scrapedate = datetime.datetime.now().strftime("%Y-%m-%d")	
		if 'HTMLFiles' in item and item['HTMLFiles']:
			#Gibt es bereits einen Eintrag für die Datei in der Jobs-Liste?
			if spider.previous_run:
				path=item['HTMLFiles'][0]['path']
				if path in spider.previous_run['dateien']:
					oldfile=spider.previous_run['dateien'][path]
					if 'checksum' in oldfile:
						if item['HTMLFiles'][0]['checksum']==oldfile['checksum']:
							# Alle alten Scrapingdaten werden auf 1.1.2023 gesetzt
							if 'scrapedate' in oldfile:
								scrapedate=oldfile['scrapedate']
							else:
								scrapedate='2023-01-01'
			eintrag['HTML']={'Datei': item['HTMLFiles'][0]['path'], 'URL': item['HTMLFiles'][0]['url'], 'Checksum': item['HTMLFiles'][0]['checksum']}
		if 'PDFFiles' in item and item['PDFFiles']:
			#Gibt es bereits einen Eintrag für die Datei in der Jobs-Liste?
			if spider.previous_run:
				path=item['PDFFiles'][0]['path']
				if path in spider.previous_run['dateien']:
					oldfile=spider.previous_run['dateien'][path]
					if 'checksum' in oldfile:
						if item['PDFFiles'][0]['checksum']==oldfile['checksum']:
							# Alle alten Scrapingdaten werden auf 1.1.2023 gesetzt
							if 'scrapedate' in oldfile:
								scrapedate=oldfile['scrapedate']
							else:
								scrapedate='2023-01-01'
				eintrag['PDF']={'Datei': item['PDFFiles'][0]['path'], 'URL': item['PDFFiles'][0]['url'], 'Checksum': item['PDFFiles'][0]['checksum']}
		eintrag['Scrapedate']=scrapedate
		if 'Nums' in item:
			eintrag['Num']=item['Nums']+zweitnum		
		elif 'Num3' in item:
			eintrag['Num']=[item['Num'],item['Num2'], item['Num3']]+zweitnum		
		elif 'Num2' in item:
			eintrag['Num']=[item['Num'],item['Num2']]+zweitnum
		else:
			eintrag['Num']=[item['Num']]+zweitnum
		if len(eintrag['Num'])==1 and eintrag['Num'][0]=='':
			spider.numliste[pfad]=[]
		else:
			spider.numliste[pfad]=eintrag['Num']
			logger.info("Trage für "+pfad+" ein: "+json.dumps(eintrag['Num']))
		# über die Sprache iterieren
		kopfzeile=[]
		missing=[]
		meta=[]
		signatur=item['Signatur']
		spider_entries=spider.gerichte[spider.name]
		metamatches=[e for e in spider_entries if e['Signatur']==signatur]
		if len(metamatches)>1:
			logger.error("Mehrere Einträge für Signatur "+signatur+": "+json.dumps(metamatches))
		elif len(metamatches)==0:
			logger.error("Keine Einträge für Signatur "+signatur)
		else:
			metamatch=metamatches[0]
			for sp in spider.kantone: # Schleife über die Sprachen
				# Nur wenn die Daten vorhanden in dieser Sprache vorhanden sind...
				if metamatch['Stufe 2 '+sp]:
					anzeige=(spider.kanton[sp]+" " if spider.kanton_kurz!="CH" else "")
					if 'Upload' in item and item['Upload']==True and 'VGericht' in item:
						anzeige += item['VGericht']
						if 'VKammer' in item:
							anzeige += ' ' + item['VKammer']
					else:
						anzeige+=metamatch['Stufe 2 '+sp]+(" "+metamatch['Stufe 3 '+sp] if metamatch['Stufe 3 '+sp] else "")
					if 'EDatum' in item and item['EDatum'] and item['EDatum']!="nodate":
						if len(item['EDatum'])==10:
							anzeige+=" "+item['EDatum'][8:10]+"."+item['EDatum'][5:7]+"."+item['EDatum'][0:4]
						else:
							anzeige+=" "+item['EDatum']
					elif 'PDatum' in item and item['PDatum'] and item['PDatum']!="nodate":
						if len(item['PDatum'])==10:
							anzeige+=" "+item['PDatum'][8:10]+"."+item['PDatum'][5:7]+"."+item['PDatum'][0:4]
						else:
							anzeige+=" "+item['PDatum']
						anzeige+=" ("+spider.translation['publiziert'][sp]+")"
					anzeige+=" "+item['Num']
					if 'Num2' in item:
						anzeige+=" ("+item['Num2']+")"
					kopfzeile.append({'Sprachen': [sp], 'Text': anzeige})
				else:
					missing.append(sp)
			logger.debug("Eintrag: "+json.dumps(eintrag)+", missing: "+json.dumps(missing)+ ", kopfzeile: "+json.dumps(kopfzeile)+", metamatch: "+json.dumps(metamatch))
			kopfzeile[0]['Sprachen']+=missing
			logger.info("Setze Kopfzeile auf: "+json.dumps(kopfzeile))
			eintrag['Kopfzeile']=kopfzeile
		
			gesamttext=""
			for sp in spider.kantone:
				text=spider.kanton[sp]+" "+metamatch['Stufe 2 '+sp]+" "+metamatch['Stufe 3 '+sp]
				meta.append({'Sprachen': [sp], 'Text': text })
				gesamttext+="#"+text
		
			alle_meta=""	
			if 'VGericht' in item and item['VGericht'] and not(item['VGericht'] in gesamttext):
				alle_meta=item['VGericht']
			if 'VKammer' in item and item['VKammer'] and not(item['VKammer'] in gesamttext):
				alle_meta+=(" " if alle_meta else "") + item['VKammer']
			if alle_meta:
				meta.append({'Sprachen': ['de', 'fr', 'it'], 'Text': alle_meta})
			eintrag['Meta']=meta
			

		abstract=[]
		missing=[]
		# Falls es sprachabhängige Abstracts gibt:
		for sp in spider.kantone:
			if 'Abstract_'+sp in item:
				abstract.append({'Sprachen': [sp], 'Text': item['Abstract_'+sp]})
			else:
				missing.append(sp)
		if len(abstract)>0:
			abstract[0]['Sprachen']+=missing
		else:
			abstracts=[]
			if 'Titel' in item and item['Titel']:
				abstracts.append(item['Titel'])
			if 'Abstract' in item and item['Abstract']:
				abstracts.append(item['Abstract'])
			if 'Leitsatz' in item and item['Leitsatz']:
				abstracts.append(item['Leitsatz'])
			elif 'LeitsatzKurz' in item and item['LeitsatzKurz']:
				abstracts.append(item['LeitsatzKurz'])
			if 'Normen' in item and item['Normen']:
				abstracts.append(item['Normen'])
			if 'Rechtsgebiet' in item and item['Rechtsgebiet']:
				abstracts.append(item['Rechtsgebiet'])
			if len(abstracts)>0:
				abstract.append({'Sprachen': list(spider.kantone), 'Text': " | ".join(abstracts)})
		if len(abstract)>0:
			eintrag['Abstract']=abstract
		buf = BytesIO(json.dumps(eintrag).encode('UTF-8'))
		checksum = md5sum(buf)
		eintrag['ScrapyJob']=spider.scrapy_job
		eintrag['Zeit UTC']=datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
		eintrag['Checksum']=checksum
		
		return json.dumps(eintrag), checksum

	@staticmethod
	def make_xml(item,spider):
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
		if 'Num2' in item:
			PipelineHelper.xml_add_element(meta,'Geschaeftsnummer',item['Num2'])
		if 'EDatum' in item:
			PipelineHelper.xml_add_element(meta,'EDatum',item['EDatum'])
		if 'PDFFiles' in item and item['PDFFiles']:
			pdffile=PipelineHelper.xml_add_element(meta,'PDFFile',item['PDFFiles'][0]['path'])
			pdffile.set('Checksum',item['PDFFiles'][0]['checksum'])
			pdffile.set('URL',item['PDFFiles'][0]['url'])
		if 'HTMLFiles' in item and item['HTMLFiles']:
			htmlfile=PipelineHelper.xml_add_element(meta,'HTMLFile',item['HTMLFiles'][0]['path'])
			htmlfile.set('Checksum',item['HTMLFiles'][0]['checksum'])
			htmlfile.set('URL',item['HTMLFiles'][0]['url'])
		if 'Sprache' in item:
			PipelineHelper.xml_add_element(meta,'Sprache',item['Sprache'])
		elif spider.kantonssprachen[item['Signatur'][:2]]:
			PipelineHelper.xml_add_element(meta,'Sprache',spider.kantonssprachen[item['Signatur'][:2]])

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

	@staticmethod
	def gen_sitemap(files):
		dateien=[]
		datum = datetime.datetime.now().strftime("%Y-%m-%d")
		root=None
		zahl=0
		for f in files:
			if root is None:
				root = etree.Element('urlset')
				root.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
			if not(files[f]['status']=='nichtmehrda' or f[-5:]=='.json'):
				zahl+=1
				url = etree.Element('url')
				root.append(url)
				entscheid=pathlib.Path(f).stem
				PipelineHelper.xml_add_element(url,'loc','https://entscheidsuche.ch/view/'+entscheid)
				if not('last_change' in files[f]):
					PipelineHelper.xml_add_element(url,'lastmod',datum)
				if zahl>49998:
					dateien.append('<?xml version="1.0" encoding="UTF-8"?>'+str(etree.tostring(root, pretty_print=True),"ascii"))
					root=None
					zahl=0
		if zahl>0:
			dateien.append('<?xml version="1.0" encoding="UTF-8"?>'+str(etree.tostring(root, pretty_print=True),"ascii"))
		return dateien

	@staticmethod
	def mydumps(x):
		ergebnis=[]
		if isinstance(x,dict):
			for i in x:
				if isinstance(i,bytes):
					j=i.decode('ascii')
				else:
					j=str(i)
				ergebnis.append("'"+j+"': "+PipelineHelper.mydumps(x[i]))
			return("{"+", ".join(ergebnis)+"}")
		elif isinstance(x,(list,tuple)):
			for i in x:
				ergebnis.append(PipelineHelper.mydumps(i))
			return("["+", ".join(ergebnis)+"]")
		elif isinstance(x,str):
			return('"'+x+'"')
		elif isinstance(x,bytes):
			return("b'"+x.decode('ascii',"replace")+"'")
		elif isinstance(x,NoneType):
			return("<None>")
		else:
			return("<Unknown>")

		


class MyFilesPipeline(FilesPipeline):
	common_store=None

	STORE_SCHEMES = {
		'': FSFilesStore,
		'file': FSFilesStore,
		's3': MyS3FilesStore,
		'gs': GCSFilesStore,
		'ftp': FTPFilesStore,
		'sftp': SFTPFilesStore
	}
	
	def __init__(self, store_uri=None, download_func=None, settings=None):
		if not store_uri:
			logger.info("keine store_uri gesetzt")
			if isinstance(settings, dict) or settings is None:
				settings = Settings(settings)
			if settings:
				store_uri=settings['FILES_STORE']
			else:
				logger.error("keine Store_uri gesetzt und auch kein settings-Parameter übergeben")
			raise NotConfigured

		super().__init__(store_uri, download_func=download_func, settings=settings)
	
	
	@classmethod
	def from_settings(cls, settings):
		s3store = cls.STORE_SCHEMES['s3']
		s3store.AWS_ACCESS_KEY_ID = settings['AWS_ACCESS_KEY_ID']
		s3store.AWS_SECRET_ACCESS_KEY = settings['AWS_SECRET_ACCESS_KEY']
		s3store.AWS_ENDPOINT_URL = settings['AWS_ENDPOINT_URL']
		s3store.AWS_REGION_NAME = settings['AWS_REGION_NAME']
		s3store.AWS_USE_SSL = settings['AWS_USE_SSL']
		s3store.AWS_VERIFY = settings['AWS_VERIFY']
		s3store.POLICY = settings['FILES_STORE_S3_ACL']

		gcs_store = cls.STORE_SCHEMES['gs']
		gcs_store.GCS_PROJECT_ID = settings['GCS_PROJECT_ID']
		gcs_store.POLICY = settings['FILES_STORE_GCS_ACL'] or None

		ftp_store = cls.STORE_SCHEMES['ftp']
		ftp_store.FTP_USERNAME = settings['FTP_USER']
		ftp_store.FTP_PASSWORD = settings['FTP_PASSWORD']
		ftp_store.USE_ACTIVE_MODE = settings.getbool('FEED_STORAGE_FTP_ACTIVE')

		sftp_store = cls.STORE_SCHEMES['sftp']
		sftp_store.SFTP_USERNAME = settings['SFTP_USERNAME']
		sftp_store.SFTP_PASSWORD = settings['SFTP_PASSWORD']

		store_uri = settings['FILES_STORE']
		store = cls(store_uri, settings=settings)
		return store

	def _get_store(self, uri):
		if os.path.isabs(uri):  # to support win32 paths like: C:\\some\dir
			scheme = 'file'
		else:
			scheme = urlparse(uri).scheme
		store_cls = self.STORE_SCHEMES[scheme]
		store=store_cls(uri)
		MyFilesPipeline.common_store=store.instanz
		if MyFilesPipeline.common_store:
			logger.info("Store instanz gesetzt")
		else:
			logger.error("Store instanz war None")
		return store


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
		self.common_store.persist_file(path, buf, info, item=item, ContentType=ContentType) # Parameter item wurde hinzugefügt. store muss dazu angepasst werden (wurde hier für S3 getan)
		return checksum


