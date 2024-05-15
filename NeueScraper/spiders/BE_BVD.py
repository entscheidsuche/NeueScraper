# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class BE_BVD(TribunaSpider):
	name = 'BE_BVD'
	
	RESULT_PAGE_URL = 'https://www.bvd-entscheide.apps.be.ch/tribunavtplus/loadTable'
	# RESULT_QUERY_TPL = r'''7|0|62|https://www.bvd-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\reports\\Export_1617673125570|reportname|Export_1617673125570|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Gemeinde|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|-17|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|10|62|10|10|11|11|0|'''
	# RESULT_QUERY_TPL_AB = r'''7|0|63|https://www.bvd-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a3u\\a3ua-www-tribunapublikation\\app\\reports\\Export_1617673333940|reportname|Export_1617673333940|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Gemeinde|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|13|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|-17|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''

	RESULT_QUERY_TPL = r'''7|0|54|https://www.bvd-entscheide.apps.be.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|0;false|5;true|4972bec2d082d7d76ff5f9d219a518a7ef36f216cd46141f92a919e671c77f61e3e4c4e69c20b5c95ef0840e2639ff3e908caa20f749a2faf192ff5a2f4b4d36f0e0911220b6bdc43a0a8850d623127e|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Gemeinde|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|0|9|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|-8|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|11|54|11|11|12|12|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|55|https://www.bvd-entscheide.apps.be.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|{datum}|0;false|5;true|4972bec2d082d7d76ff5f9d219a518a7ef36f216cd46141f92a919e671c77f61e3e4c4e69c20b5c95ef0840e2639ff3e908caa20f749a2faf192ff5a2f4b4d36f0e0911220b6bdc43a0a8850d623127e|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Gemeinde|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|14|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|9|1751|9|0|9|-1|15|16|17|18|0|19|18|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|-9|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|11|55|11|11|12|12|0|'''


	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'C73019EE7ED2BDCD2F31B86E73007B0F'
			  , 'X-GWT-Module-Base': 'https://www.bvd-entscheide.apps.be.ch/tribunavtplus/'
			  , 'Host': 'www.bvd-entscheide.apps.be.ch'
			  , 'Origin': 'https://www.bvd-entscheide.apps.be.ch'
			  , 'Referer': 'https://www.bvd-entscheide.apps.be.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://www.bvd-entscheide.apps.be.ch/tribunavtplus/ServletDownload/'
	# PDF_PATTERN = "{}{}_{}.pdf?path={}&pathIsEncrypted=1&dossiernummer={}"
	PDF_PATTERN ="{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	DECRYPT_PAGE_URL = "https://www.bvd-entscheide.apps.be.ch/tribunavtplus/loadTable"
	DECRYPT_START ='7|0|11|https://www.bvd-entscheide.apps.be.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|'
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')
