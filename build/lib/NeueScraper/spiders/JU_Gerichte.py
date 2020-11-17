# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class JU_Gerichte(TribunaSpider):
	name = 'JU_Gerichte'
	
	RESULT_PAGE_URL = 'https://jurisprudence.jura.ch/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	RESULT_QUERY_TPL = r'''7|0|64|https://jurisprudence.jura.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|TPI|0;false|5;true|C:\\DeltaLogic\\Publikation\\Thesaurus\\suisseFR.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Publikation\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Publikation\\Reports\\Export_1596546846893|reportname|Export_1596546846893|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Attr. supplémentaire|indexCode|Source|dossierObject|Objet|law|Nature juridique|shortText|Texte d'aperçu|department|Cour|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Mode de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Greffier|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|2|5|12|5|13|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|65|https://jurisprudence.jura.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|TPI|{datum}|0;false|5;true|C:\\DeltaLogic\\Publikation\\Thesaurus\\suisseFR.fts|1|java.util.HashMap/1797211028|reportpath|C:\\DeltaLogic\\Publikation\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\DeltaLogic\\Publikation\\Reports\\Export_1596546878825|reportname|Export_1596546878825|decisionDate|Date de l'arrêt|dossierNumber|Dossier|classification|Attr. supplémentaire|indexCode|Source|dossierObject|Objet|law|Nature juridique|shortText|Texte d'aperçu|department|Cour|createDate|Date de création|creater|Créateur|judge|Juge|executiontype|Mode de liquidation|legalDate|Date exécutoire|objecttype|Type d'objet|typist|Greffier|description|Description|reference|Référence|relevance|Pertinence|fr|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|2|5|12|5|13|10|10|10|14|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|15|16|17|18|0|19|5|5|20|5|21|5|22|5|23|5|24|5|10|5|25|5|26|5|27|5|28|19|18|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|5|64|10|65|10|10|11|11|0|'''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'A88BA8CB8D04B7CB3B9497E90DEBA9EB'
			  , 'X-GWT-Module-Base': 'https://jurisprudence.jura.ch/tribunavtplus/'
			  , 'Host': 'jurisprudence.jura.ch'
			  , 'Origin': 'https://jurisprudence.jura.ch'
			  , 'Referer': 'https://jurisprudence.jura.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://jurisprudence.jura.ch/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}_{}.pdf?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	DECRYPT_PAGE_URL = "https://jurisprudence.jura.ch/tribunavtplus/decrypt"
	DECRYPT_START = "7|0|7|https://jurisprudence.jura.ch/tribunavtplus/|C419D19919BD2D5CFB1CA8A5E0CD9913|tribunavtplus.client.zugriff.DecryptService|encrypt|java.lang.String/2004016611|"
	DECRYPT_END = "|IchBinDerSchlues|1|2|3|4|2|5|5|6|7|"

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')
