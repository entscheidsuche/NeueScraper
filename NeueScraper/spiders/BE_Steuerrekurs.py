# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class BE_Steuerrekurs(TribunaSpider):
	name = 'BE_Steuerrekurs'
	
	RESULT_PAGE_URL = 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	# RESULT_QUERY_TPL = r'''7|0|62|https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|StRK|0;false|5;true|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a2y\\a2ya-www-trbpub700web\\Reports\\Export_1596162913203|reportname|Export_1596162913203|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Sachgebiet|shortText|Vorschautext|department|Spruchkörper|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|-17|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|10|62|10|10|11|11|0|'''
	RESULT_QUERY_TPL = r'''7|0|54|https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|StRK|0;false|5;true|c830a94d9e718d657b87fa094d2d42af850d09eb38ee689ec1b4a96c69397b949ec47a04415ac573f819ae1aea9a0e1846d47f1da12fee92b51a76191eb1694b|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Sachgebiet|shortText|Vorschautext|department|Spruchkörper|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|0|9|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|-8|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|11|54|11|11|12|12|0|'''
	RESULT_QUERY_TPL_AB = ''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '1ABD52BDF54ACEC06A4E0EEDA12D4178'
			  , 'X-GWT-Module-Base': 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/'
			  }
	MINIMUM_PAGE_LEN = 148
	ENCRYPTED = True
	DOWNLOAD_URL = 'https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/ServletDownload/'
	PDF_PATH = 'E%3A%5C%5Cwebapps%5C%5Ca2y%5C%5Ca2ya-www-trbpub700web%5C%5Cpdf%5C'
	PDF_PATTERN = "{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"

	reNum=re.compile('\d{1,3}\s(19|20)\d\d\s\d+')

	DECRYPT_PAGE_URL = "https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable"
	DECRYPT_START ='7|0|11|https://www.strk-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|'
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"
