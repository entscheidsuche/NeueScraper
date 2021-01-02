# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class ZG_Verwaltungsgericht(TribunaSpider):
	name = 'ZG_Verwaltungsgericht'
	
	RESULT_PAGE_URL = 'https://verwaltungsgericht.zg.ch/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	RESULT_QUERY_TPL = r'''7|0|62|https://verwaltungsgericht.zg.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|C:\\DeltaLogic\\Pub\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Pub\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Pub\\Reports\\Export_1609522279554|reportname|Export_1609522279554|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|-10|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|10|62|10|10|11|11|0|'''

	RESULT_QUERY_TPL_AB = r'''7|0|63|https://verwaltungsgericht.zg.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|C:\\DeltaLogic\\Pub\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Pub\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Pub\\Reports\\Export_1609522400769|reportname|Export_1609522400769|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|13|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|-10|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''

	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '1ABD52BDF54ACEC06A4E0EEDA12D4178'
			  , 'X-GWT-Module-Base': 'https://verwaltungsgericht.zg.ch/tribunavtplus/'
			  , 'Host': 'verwaltungsgericht.zg.ch'
			  , 'Origin': 'https://verwaltungsgericht.zg.ch'
			  , 'Referer': 'https://verwaltungsgericht.zg.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://verwaltungsgericht.zg.ch/tribunavtplus/ServletDownload/'

	PDF_PATH = 'C%3A%5CDeltaLogic%5CPub%5CDocs_VG%5C'

	PDF_PATTERN = "{}{}_{}.pdf?path={}{}.pdf&dossiernummer={}"

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')
	
	#Zug benötigt Cookies
	custom_settings = {
        'COOKIES_ENABLED': True
    }
