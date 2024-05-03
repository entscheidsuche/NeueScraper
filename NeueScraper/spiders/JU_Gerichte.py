# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class JU_Gerichte(TribunaSpider):
	name = 'JU_Gerichte'
	
	RESULT_PAGE_URL = 'https://entscheidsuche.ch/ju_helper/loadTable.php'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
#	RESULT_QUERY_TPL = r'''7|0|64|https://jurisprudence.jura.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|TPI|0;false|5;true|C:\\DeltaLogic\\Publikation\\Thesaurus\\suisseFR.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Publikation\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Publikation\\Reports\\Export_1648375044146|reportname|Export_1648375044146|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Attr. supplémentaire|indexCode|Source|dossierObject|Objet|law|Nature juridique|shortText|Texte d'aperçu|department|Section|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Mode de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Greffier|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|2|5|12|5|13|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
	RESULT_QUERY_TPL = r'''7|0|56|https://jurisprudence.jura.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TC|TPI|0;false|5;true|3613730c5bff07159093e019f4866a1fcd955672703a8598b0fb641a55bef20ef2dc5c9ce5d7233d2335c2d83d7dcf5a1158da448ea78beeb249fe7a2a740656|1|java.util.HashMap/1797211028|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Classification|indexCode|Source|dossierObject|Objet|law|Matière|shortText|Texte d'aperçu|department|Département|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Manière de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Auteur|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|2|5|13|5|14|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|0|9|0|9|-1|15|16|17|18|0|19|18|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|11|56|11|11|12|12|0|'''

#	RESULT_QUERY_TPL_AB = r'''7|0|65|https://jurisprudence.jura.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|TPI|{datum}|0;false|5;true|C:\\DeltaLogic\\Publikation\\Thesaurus\\suisseFR.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Publikation\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Publikation\\Reports\\Export_1648375044146|reportname|Export_1648375044146|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Attr. supplémentaire|indexCode|Source|dossierObject|Objet|law|Nature juridique|shortText|Texte d'aperçu|department|Section|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Mode de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Greffier|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|2|5|12|5|13|10|10|10|14|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|15|16|17|18|0|19|5|5|20|5|21|5|22|5|23|5|24|5|10|5|25|5|26|5|27|5|28|19|18|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|5|64|10|65|10|10|11|11|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|57|https://jurisprudence.jura.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TC|TPI|{datum}|0;false|5;true|3613730c5bff07159093e019f4866a1fcd955672703a8598b0fb641a55bef20ef2dc5c9ce5d7233d2335c2d83d7dcf5a1158da448ea78beeb249fe7a2a740656|1|java.util.HashMap/1797211028|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Classification|indexCode|Source|dossierObject|Objet|law|Matière|shortText|Texte d'aperçu|department|Département|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Manière de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Auteur|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|2|5|13|5|14|11|11|11|15|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|9|933|9|0|9|-1|16|17|18|19|0|20|18|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|11|57|11|11|12|12|0|'''

	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'C8CE51A1CBF8D3F8785E0231E597C2B4'
			  , 'X-GWT-Module-Base': 'https://jurisprudence.jura.ch/tribunavtplus/'
			  , 'Origin': 'https://jurisprudence.jura.ch'
			  , 'Referer': 'https://jurisprudence.jura.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://entscheidsuche.ch/ju_helper/download.php?pfad=/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}&path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
#	obwohl der Decrypt-Aufruf nun auch ein loadTable Aufruf geworden ist, bleibt das getrennt um Race Conditions zu vermeiden
	DECRYPT_PAGE_URL = "https://entscheidsuche.ch/ju_helper/decrypt.php"
#	DECRYPT_START = "7|0|7|https://jurisprudence.jura.ch/tribunavtplus/|C419D19919BD2D5CFB1CA8A5E0CD9913|tribunavtplus.client.zugriff.DecryptService|encrypt|java.lang.String/2004016611|"
	DECRYPT_START = "7|0|11|https://jurisprudence.jura.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|"
#	DECRYPT_END = "|IchBinDerSchlues|1|2|3|4|2|5|5|6|7|"
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"
	COOKIE = True
	COOKIE_INIT ="https://entscheidsuche.ch/ju_helper/getCookie.php"
	COOKIE_HEADERS = { 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en', 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0', 'Accept-Encoding': 'gzip, deflate'}
	zyte_smartproxy_enabled = True
	zyte_smartproxy_apikey = 'a88daef01f664ec3b39f5fd43fdcd685'

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')
	
	
