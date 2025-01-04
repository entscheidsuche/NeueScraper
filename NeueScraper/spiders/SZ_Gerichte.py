# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class SZ_Gerichte(TribunaSpider):
	name = 'SZ_Gerichte'
	
	RESULT_PAGE_URL = "https://gerichte.sz.ch/tribunavtplus/loadTable"

#	RESULT_QUERY_TPL = r'''7|0|63|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1665984873130|reportname|Export_1665984873130|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''
#	RESULT_QUERY_TPL = r'''7|0|63|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1669039452025|reportname|Export_1669039452025|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''
#	RESULT_QUERY_TPL = r'''7|0|63|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_{millis}|reportname|Export_{millis}|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|1|{page_nr}|13|14|15|16|0|17|5|5|18|5|19|5|20|5|21|5|22|5|10|5|23|5|24|5|25|5|26|17|18|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|10|63|10|10|11|11|0|'''
#	RESULT_QUERY_TPL = r'''7|0|60|https://gerichte.sz.ch/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|1|{page_nr}|-1|12|12|0|9|0|9|-1|15|16|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|75|71|92|92|115|117|105|115|115|101|46|102|116|115|17|0|18|5|5|19|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|20|10|1|50|5|21|10|0|5|22|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|95|49|54|56|52|52|51|52|50|54|54|50|50|53|5|23|10|22|34|69|120|112|111|114|116|95|34|49|54|56|52|52|51|52|50|54|54|50|50|53|18|18|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|12|60|12|12|13|13|0|'''
	RESULT_QUERY_TPL = r'''7|0|55|https://gerichte.sz.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|0;false|5;true|57ff49a267d6d777cb0fb9e30ad4179bacdde5c05101aed97db50ef8d6f2168b1a01324b59d02632e646985662d8478b|1|java.util.HashMap/1797211028|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|0|9|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|11|55|11|11|12|12|0|'''

#	RESULT_QUERY_TPL_AB = r'''7|0|64|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1665984873130|reportname|Export_1665984873130|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|13|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
#	RESULT_QUERY_TPL_AB = r'''7|0|64|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_1669039452025|reportname|Export_1669039452025|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|13|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
#	RESULT_QUERY_TPL_AB = r'''7|0|64|https://gerichte.sz.ch/tribunavtplus/|9012D0DA9E934A747A7FE70ABB27518D|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.util.Map||0|TRI|{datum}|0;false|5;true|C:\\Deltalogic\\Thesaurus\\KG\\suisse.fts|1|java.util.HashMap/1797211028|reportpath|C:\\Deltalogic\\Reports\\KG\\ExportResults.jasper|viewtype|2|reporttitle|reportexportpath|C:\\Deltalogic\\Reports\\KG\\Export_{millis}|reportname|Export_{millis}|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|41|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|5|5|5|5|7|9|9|5|5|5|5|5|5|5|10|11|6|0|0|6|1|5|12|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|10|13|1|{page_nr}|14|15|16|17|0|18|5|5|19|5|20|5|21|5|22|5|23|5|10|5|24|5|25|5|26|5|27|18|18|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|5|61|5|62|5|63|10|64|10|10|11|11|0|'''
#	RESULT_QUERY_TPL_AB = r'''7|0|61|https://gerichte.sz.ch/tribunavtplus/|650CC7EFF80D4E2F1340EDCB95B99785|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|[B/3308590456|java.util.Map||0|TRI|{datum}|0;false|5;true|1|java.util.HashMap/1797211028|reportpath|viewtype|reporttitle|reportexportpath|reportname|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|47|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|10|5|7|11|11|5|5|5|5|5|5|5|12|13|6|0|0|6|1|5|14|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|12|15|1|{page_nr}|-1|12|12|9|2207|9|0|9|-1|16|17|10|41|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|84|104|101|115|97|117|114|117|115|92|92|75|71|92|92|115|117|105|115|115|101|46|102|116|115|18|0|19|5|5|20|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|82|101|115|117|108|116|115|46|106|97|115|112|101|114|5|21|10|1|50|5|22|10|0|5|23|10|48|67|58|92|92|68|101|108|116|97|108|111|103|105|99|92|92|82|101|112|111|114|116|115|92|92|75|71|92|69|120|112|111|114|116|95|49|54|56|52|52|51|52|52|49|48|56|53|48|5|24|10|22|34|69|120|112|111|114|116|95|34|49|54|56|52|52|51|52|52|49|48|56|53|48|19|18|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|5|56|5|57|5|58|5|59|5|60|12|61|12|12|13|13|0|'''
	RESULT_QUERY_TPL_AB = r'''7|0|56|https://gerichte.sz.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|{datum}|0;false|5;true|57ff49a267d6d777cb0fb9e30ad4179bacdde5c05101aed97db50ef8d6f2168b1a01324b59d02632e646985662d8478b|1|java.util.HashMap/1797211028|decisionDate|Urteilsdatum|dossierNumber|Dossier|classification|Klassierung|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|Abteilung|createDate|Erstelldatum|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|14|1|{page_nr}|-1|11|11|9|2328|9|0|9|-1|15|16|17|18|0|19|18|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|5|55|11|56|11|11|12|12|0|'''
	
	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': '8AF5705066F952B29FA749FC5DB6C65D'
			  , 'X-GWT-Module-Base': 'https://gerichte.sz.ch/tribunavtplus/'
			  , 'Host': 'gerichte.sz.ch'
			  , 'Origin': '	https://gerichte.sz.ch'
			  , 'Referer': '	https://gerichte.sz.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }
	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://gerichte.sz.ch/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True
	ASCII_ENCRYPTED = True
	
	DECRYPT_PAGE_URL = "https://gerichte.sz.ch/tribunavtplus/loadTable"
	DECRYPT_START ='7|0|11|https://gerichte.sz.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|'
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"

	# 7|0|11|https://gerichte.sz.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|BEK_2023_89_eb9cb516b72ea9d822b390383b5bf9d2209a489e87c9c817f684b9581011c5f445690a4d596044549f8c6f5dbf1be654e484258efc2e016c1d2300034d5ba0de|dossiernummer|BEK_2023_89|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|
	# 7|0|5|https://gerichte.sz.ch/tribunavtplus/|27D15B82643FBEE798506E3AEC7D40C0|tribunavtplus.client.zugriff.DecryptService|encrypt|[B/3308590456|1|2|3|4|2|5|5|5|58|67|58|92|68|101|108|116|97|108|111|103|105|99|92|68|111|99|115|92|75|71|92|97|49|51|99|54|102|97|49|98|55|98|48|52|102|50|51|97|54|51|52|99|52|98|55|101|52|97|53|53|49|54|55|46|112|100|102|5|16|109|51|81|110|38|111|37|37|76|105|122|119|111|67|53|51|
    # 7|0|5|https://gerichte.sz.ch/tribunavtplus/|27D15B82643FBEE798506E3AEC7D40C0|tribunavtplus.client.zugriff.DecryptService|encrypt|[B/3308590456|1|2|3|4|2|5|5|5|58|67|58|67|58|92|68|101|108|116|97|108|111|103|105|99|92|68|111|99|115|92|75|71|92|52|51|56|51|101|57|56|54|49|97|57|51|52|52|100|55|98|57|52|101|56|48|53|99|50|100|52|48|99|98|48|56|46|112|100|102|5|16|109|51|81|110|38|111|37|37|76|105|122|119|111|67|53|51|
    # 7|0|5|https://verwaltungsgericht.zg.ch/tribunavtplus/|27D15B82643FBEE798506E3AEC7D40C0|tribunavtplus.client.zugriff.DecryptService|encrypt|[B/3308590456|1|2|3|4|2|5|5|5|62|67|58|92|68|101|108|116|97|108|111|103|105|99|92|68|111|99|115|92|75|71|92|52|51|56|51|101|57|56|54|49|97|57|51|52|52|100|55|98|57|52|101|56|48|53|99|50|100|52|48|99|98|48|56|46|112|100|102|5|16|109|51|81|110|38|111|37|37|76|105|122|119|111|67|53|51|
	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')

