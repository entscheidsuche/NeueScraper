# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class SZ_Gerichte(TribunaSpider):
	name = 'SZ_Gerichte'
	
	RESULT_PAGE_URL = "https://gerichte.sz.ch/tribunavtplus/loadTable"

	RESULT_QUERY_TPL = r'''7|0|63|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1609607278978|reportname|Export_1609607278978|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''

	RESULT_QUERY_TPL_AB = r'''7|0|64|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1609607537523|reportname|Export_1609607537523|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|13|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''

	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'C73019EE7ED2BDCD2F31B86E73007B0F'
			  , 'X-GWT-Module-Base': 'https://gerichte.sz.ch/tribunavtplus/'
			  , 'Host': 'gerichte.sz.ch'
			  , 'Origin': '	https://gerichte.sz.ch'
			  , 'Referer': '	https://gerichte.sz.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://gerichte.sz.ch/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}_{}.pdf?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	DECRYPT_PAGE_URL = "https://gerichte.sz.ch/tribunavtplus/decrypt"
	DECRYPT_START ='7|0|7|https://gerichte.sz.ch/tribunavtplus/|C419D19919BD2D5CFB1CA8A5E0CD9913|tribunavtplus.client.zugriff.DecryptService|encrypt|java.lang.String/2004016611|'
	DECRYPT_END = "|IchBinDerSchlues|1|2|3|4|2|5|5|6|7|"

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')

