# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class SZ_Verwaltungsgericht(TribunaSpider):
	name = 'SZ_Verwaltungsgericht'
	
	RESULT_PAGE_URL = "https://gerichte.sz.ch/vg/tribunavtplus/loadTable"

	# RESULT_QUERY_TPL = r'''7|0|60|https://gerichte.sz.ch/vg/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|1|{page_nr}|-1|12|12|0|9|0|9|-1|15|16|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|75|71|92|92|115|117|105|115|115|101|46|102|116|115|17|0|18|5|5|19|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|20|10|1|50|5|21|10|0|5|22|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|95|49|54|56|52|52|51|52|50|54|54|50|50|53|5|23|10|22|34|69|120|112|111|114|116|95|34|49|54|56|52|52|51|52|50|54|54|50|50|53|18|18|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|12|60|12|12|13|13|0|'''
	RESULT_QUERY_TPL = r'''7|0|60|https://gerichte.sz.ch/vg/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|1|{page_nr}|-1|12|12|0|9|0|9|-1|15|16|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|86|71|92|92|115|117|105|115|115|101|46|102|116|115|17|0|18|5|5|19|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|86|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|20|10|1|50|5|21|10|0|5|22|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|86|71|92|69|120|112|111|114|116|95|49|55|48|54|53|50|49|53|49|49|55|57|54|5|23|10|22|34|69|120|112|111|114|116|95|34|49|55|48|54|53|50|49|53|49|49|55|57|54|18|18|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|12|60|12|12|13|13|0|'''
	
	# RESULT_QUERY_TPL_AB = r'''7|0|61|https://gerichte.sz.ch/vg/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|{datum}|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|15|1|{page_nr}|-1|12|12|9|2207|9|0|9|-1|16|17|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|75|71|92|92|115|117|105|115|115|101|46|102|116|115|18|0|19|5|5|20|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|21|10|1|50|5|22|10|0|5|23|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|95|49|54|56|52|52|51|52|52|49|48|56|53|48|5|24|10|22|34|69|120|112|111|114|116|95|34|49|54|56|52|52|51|52|52|49|48|56|53|48|19|18|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|12|61|12|12|13|13|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|61|https://gerichte.sz.ch/vg/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|{datum}|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|15|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|1|{page_nr}|-1|12|12|9|1673|9|0|9|-1|16|17|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|86|71|92|92|115|117|105|115|115|101|46|102|116|115|18|0|19|5|5|20|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|86|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|21|10|1|50|5|22|10|0|5|23|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|86|71|92|69|120|112|111|114|116|95|49|55|48|54|53|50|49|54|48|50|51|52|54|5|24|10|22|34|69|120|112|111|114|116|95|34|49|55|48|54|53|50|49|54|48|50|51|52|54|19|18|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|12|61|12|12|13|13|0|'''
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '6AC682AB32A2550405E5C0C850B33E15'
			  , 'X-GWT-Module-Base': 'https://gerichte.sz.ch/vg/tribunavtplus/'
			  , 'Host': 'gerichte.sz.ch'
			  , 'Origin': '	https://gerichte.sz.ch'
			  , 'Referer': '	https://gerichte.sz.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://gerichte.sz.ch/vg/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}_{}.pdf?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	ASCII_ENCRYPTED = True
	
	DECRYPT_PAGE_URL = "https://gerichte.sz.ch/vg/tribunavtplus/decrypt"
	DECRYPT_START ='7|0|5|https://gerichte.sz.ch/tribunavtplus/|27D15B82643FBEE798506E3AEC7D40C0|tribunavtplus.client.zugriff.DecryptService|encrypt|[B/3308590456|1|2|3|4|2|5|5|5|58'
	# DECRYPT_END = "|5|16|109|51|81|110|38|111|37|37|76|105|122|119|111|67|53|51|"
	DECRYPT_END = "|5|16|84|51|37|104|53|99|117|55|65|76|53|55|50|64|69|104|"
	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')
