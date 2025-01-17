# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class BE_Anwaltsaufsicht(TribunaSpider):
	name = 'BE_Anwaltsaufsicht'
	
	RESULT_PAGE_URL = 'https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	#RESULT_QUERY_TPL = r'''7|0|63|https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|OG_AA|0;false|5;true|E:\\webapps\\a2y\\a2ya-www-trbpub999web\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|E:\\webapps\\a2y\\a2ya-www-trbpub999web\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|E:\\webapps\\a2y\\a2ya-www-trbpub999web\\Reports\\Export_1596180801143|reportname|Export_1596180801143|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''
	RESULT_QUERY_TPL = r'''7|0|55|https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|OG_AA|0;false|5;true|c4892be059dbbbe2ab13725f999aaabb84c52f17ba96bb16efdbdf2989d96162d587da060318278e7ef57e9a49d83197544a2dfc1e2a3dd93844f2d9d933ce27|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|0|9|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|11|55|11|11|12|12|0|'''
	RESULT_QUERY_TPL_AB = ''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '1ABD52BDF54ACEC06A4E0EEDA12D4178'
			  , 'X-GWT-Module-Base': 'https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/'
			  }
	MINIMUM_PAGE_LEN = 148
	ENCRYPTED= True
	DOWNLOAD_URL = 'https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/ServletDownload/'
	PDF_PATH = 'E%3A%5C%5Cwebapps%5C%5Ca2y%5C%5Ca2ya-www-trbpub999web%5C%5Cpdf%5C'
	PDF_PATTERN = "{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"

	DECRYPT_PAGE_URL = "https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/loadTable"
	DECRYPT_START ='7|0|11|https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|'
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"

	reNum=re.compile('AA\s(19|20)\d\d\s\d+')
	
#https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/ServletDownload/AA_2023_150_c4892be059dbbbe2ab13725f999aaabb84c52f17ba96bb16efdbdf2989d96162c99e9d3f4141539fd103a4cfb614e4afbde059ce0b851215672cb2cf80227b774a6f9dc27d20f0abc00a91cc5094fdc6a134501981d11016a0224f049f967410?path=c4892be059dbbbe2ab13725f999aaabb84c52f17ba96bb16efdbdf2989d96162c99e9d3f4141539fd103a4cfb614e4afbde059ce0b851215672cb2cf80227b774a6f9dc27d20f0abc00a91cc5094fdc6a134501981d11016a0224f049f967410&pathIsEncrypted=1&dossiernummer=AA_2023_150
#7|0|11|https://www.aa-entscheide.apps.be.ch/tribunapublikation/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|AA_2023_150_c4892be059dbbbe2ab13725f999aaabb84c52f17ba96bb16efdbdf2989d96162c99e9d3f4141539fd103a4cfb614e4afbde059ce0b851215672cb2cf80227b774a6f9dc27d20f0abc00a91cc5094fdc6a134501981d11016a0224f049f967410|dossiernummer|AA_2023_150|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|
#//OK[6,2,5,2,4,2,3,2,2,1,["java.util.HashMap/1797211028","java.lang.String/2004016611","partURL","AA_2023_150_c4892be059dbbbe2ab13725f999aaabb84c52f17ba96bb16efdbdf2989d96162c99e9d3f4141539fd103a4cfb614e4afbde059ce0b851215672cb2cf80227b774a6f9dc27d20f0abc00a91cc5094fdc6a134501981d11016a0224f049f967410","dossiernummer","AA_2023_150"],0,7]

