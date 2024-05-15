# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider


class FR_Gerichte(TribunaSpider):
	name = 'FR_Gerichte'
	
	RESULT_PAGE_URL = 'https://entscheidsuche.ch/fr_helper/loadTable.php'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	# RESULT_QUERY_TPL = r'''7|0|63|https://publicationtc.fr.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|0;false|5;true|D:\\Pub\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|D:\\Pub\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|D:\\Pub\\Reports\\Export_1595406157037|reportname|Export_1595406157037|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''
	RESULT_QUERY_TPL = r'''7|0|55|https://publicationtc.fr.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TC|0;false|5;true|4f8108014967aed158a7443a59b34b290b845678700185367b31fac016e506c0|1|java.util.HashMap/1797211028|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|9|12001|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|11|55|11|11|12|12|0|'''
	# RESULT_QUERY_TPL_AB = r'''7|0|64|https://publicationtc.fr.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TC|{datum}|0;false|5;true|D:\\Pub\\Thesaurus\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|D:\\Pub\\Reports\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|D:\\Pub\\Reports\\Export_1595406512439|reportname|Export_1595406512439|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|13|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|56|https://publicationtc.fr.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TC|{datum}|0;false|5;true|4f8108014967aed158a7443a59b34b290b845678700185367b31fac016e506c0|1|java.util.HashMap/1797211028|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|14|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|9|12001|0|9|-1|15|16|17|18|0|19|18|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|11|56|11|11|12|12|0|'''
	HEADERS = { 'Content-type': 'application/json;charset=utf-8'
			  , 'X-GWT-Permutation': '8AF5705066F952B29FA749FC5DB6C65D'
			  , 'X-GWT-Module-Base': 'https://publicationtc.fr.ch/tribunavtplus/'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://entscheidsuche.ch/fr_helper/download.php?pfad=/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	DECRYPT_PAGE_URL = "https://entscheidsuche.ch/fr_helper/decrypt.php"
	DECRYPT_START ='7|0|11|https://publicationtc.fr.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|'
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"
	
	PDF_PATTERN = "{}{}&path={}&pathIsEncrypted=1&dossiernummer={}"

	reNum=re.compile('[0-9A-Z]{1,3}\s(19|20)\d\d\s\d+')
	GERICHTSBARKEIT = ''
	KANTON = 'Fribourg'
