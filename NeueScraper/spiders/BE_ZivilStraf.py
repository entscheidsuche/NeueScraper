# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)
		
class BE_ZivilStraf(TribunaSpider):
	name = 'BE_ZivilStraf'
	
	RESULT_PAGE_URL = 'https://www.zsg-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	RESULT_QUERY_TPL = r'''7|0|67|https://www.zsg-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|OG|BM|BJS|EO|O|0;false|5;true|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Reports\\Export_1592254990808|reportname|Export_1592254990808|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Gericht|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|5|5|12|5|13|5|14|5|15|5|16|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|17|18|19|20|0|21|5|5|22|5|23|5|24|5|25|5|26|5|10|5|27|5|28|5|29|5|30|21|18|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|5|64|5|65|5|66|10|67|10|10|11|11|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|68|https://www.zsg-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|OG|BM|BJS|EO|O|{datum}|0;false|5;true|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a2y\\a2ya-www-trbpub100web\\Reports\\Export_1595357657961|reportname|Export_1595357657961|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Gericht|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|5|5|12|5|13|5|14|5|15|5|16|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|17|1|{page_nr}|18|19|20|21|0|22|5|5|23|5|24|5|25|5|26|5|27|5|10|5|28|5|29|5|30|5|31|22|18|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|5|64|5|65|5|66|5|67|10|68|10|10|11|11|0|'''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'C56BCDCE0FCCE64CB5164DE7BBAF017B'
			  , 'X-GWT-Module-Base': 'https://www.zsg-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/'
			  }
	MINIMUM_PAGE_LEN = 148
	DOWNLOAD_URL = 'https://www.zsg-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/ServletDownload/'
	PDF_PATH = 'E%3A%5C%5Cwebapps%5C%5Ca2y%5C%5Ca2ya-www-trbpub100web%5C%5Cpdf%5C'
	PDF_PATTERN = "{}{}_{}.pdf?path={}{}.pdf&dossiernummer={}"

	reNum=re.compile('\D{2,3}\s\d\d\d\d\s\d+')
	
