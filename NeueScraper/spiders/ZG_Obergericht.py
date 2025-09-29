# -*- coding: utf-8 -*-
import scrapy
import re
import logging
from NeueScraper.spiders.tribuna import TribunaSpider

logger = logging.getLogger(__name__)

class ZG_Obergericht(TribunaSpider):
	name = 'ZG_Obergericht'
	
	RESULT_PAGE_URL = 'https://obergericht.zg.ch/tribunavtplus/loadTable'
	# Hole immer nur ein Dokument um Probleme mit Deduplizierung und unterschiedlichen Reihenfolgen zu verringern
	RESULT_QUERY_TPL = r'''7|0|54|https://obergericht.zg.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|0;false|5;true|ae27a207d77ff462df22bfdb11ee0bde1343fda0f8b4a0efe3c5cab28d326b295112c9a07eeb9414ce1c6cae49f479a9|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|1|{page_nr}|-1|11|11|9|1034|9|0|9|-1|14|15|16|17|0|18|18|5|19|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|11|5|34|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|11|54|11|11|12|12|0|'''

	RESULT_QUERY_TPL_AB = r'''7|0|55|https://obergericht.zg.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|search|java.lang.String/2004016611|java.util.ArrayList/4159755760|Z|I|java.lang.Integer/3438268394|java.util.Map||0|TRI|{datum}|0;false|5;true|ae27a207d77ff462df22bfdb11ee0bde1343fda0f8b4a0efe3c5cab28d326b295112c9a07eeb9414ce1c6cae49f479a9|1|java.util.HashMap/1797211028|decisionDate|Entscheiddatum|dossierNumber|Dossier|classification|Zusatzeigenschaft|indexCode|Quelle|dossierObject|Betreff|law|Rechtsgebiet|shortText|Vorschautext|department|createDate|Erfasst am|creater|Ersteller|judge|Richter|executiontype|Erledigungsart|legalDate|Rechtskraftdatum|objecttype|Objekttyp|typist|Schreiber|description|Beschreibung|reference|Referenz|relevance|Relevanz|de|1|2|3|4|46|5|5|6|7|6|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|5|8|8|8|5|5|9|9|9|5|5|5|5|7|10|5|5|5|5|5|5|5|11|12|6|0|0|6|1|5|13|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|11|14|1|{page_nr}|-1|11|11|9|1034|9|0|9|-1|15|16|17|18|0|19|18|5|20|5|21|5|22|5|23|5|24|5|25|5|26|5|27|5|28|5|29|5|30|5|31|5|32|5|33|5|34|5|11|5|35|5|36|5|37|5|38|5|39|5|40|5|41|5|42|5|43|5|44|5|45|5|46|5|47|5|48|5|49|5|50|5|51|5|52|5|53|5|54|11|55|11|11|12|12|0|'''

	HEADERS = { 'Content-type': 'text/x-gwt-rpc; charset=utf-8'
			  , 'X-GWT-Permutation': 'C8CE51A1CBF8D3F8785E0231E597C2B4'
			  , 'X-GWT-Module-Base': 'https://obergericht.zg.ch/tribunavtplus/'
			  , 'Origin': 'https://obergericht.zg.ch'
			  , 'Referer': 'https://obergericht.zg.ch/'
			  , 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:79.0) Gecko/20100101 Firefox/79.0'
			  }

	MINIMUM_PAGE_LEN = 100
	DOWNLOAD_URL = 'https://entscheidsuche.ch/zg_helper/download.php?pfad=/tribunavtplus/ServletDownload/'
	PDF_PATTERN = "{}{}?path={}&pathIsEncrypted=1&dossiernummer={}"
	ENCRYPTED = True

	DECRYPT_PAGE_URL = "https://obergericht.zg.ch/tribunavtplus/loadTable"
	DECRYPT_START = "7|0|11|https://obergericht.zg.ch/tribunavtplus/|CAC80118FB77794F1FDFC1B51371CC63|tribunavtplus.client.zugriff.LoadTableService|urlEncodingTribuna|java.util.Map|java.util.HashMap/1797211028|java.lang.String/2004016611|partURL|"
	DECRYPT_END = "|1|2|3|4|1|5|6|2|7|8|7|9|7|10|7|11|"

	reNum=re.compile('[A-Z0-9]{1,3}\s(19|20)\d\d\s\d+')

#https://obergericht.zg.ch/tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&pathIsEncrypted=1&dossiernummer=BZ_2024_130
#https://obergericht.zg.ch/tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&pathIsEncrypted=1&dossiernummer=BZ_2024_130
#https://obergericht.zg.ch/tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?pathIsEncrypted=1&dossiernummer=BZ_2024_130
#/zg_helper/download.php?pfad=
#						  /tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&pathIsEncrypted=1&dossiernummer=BZ_2024_130
#https://obergericht.zg.ch/tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&pathIsEncrypted=1&dossiernummer=BZ_2024_130
#https://obergericht.zg.ch/tribunavtplus/ServletDownload/S_2021_24_fdd7631f3f812fe9da3ea4c19349bdaa4ad9f818e66b02e241cc62b8113001c69ae2edbea2cbde9157ed4a4dedcc4f34dbad36dda8a8ce42b7bb9d7d82216052?path=fdd7631f3f812fe9da3ea4c19349bdaa4ad9f818e66b02e241cc62b8113001c69ae2edbea2cbde9157ed4a4dedcc4f34dbad36dda8a8ce42b7bb9d7d82216052?pathIsEncrypted=1&dossiernummer=S_2021_24
#https://entscheidsuche.ch/zg_helper/download.php?pfad=/tribunavtplus/ServletDownload/BZ_2024_130_fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a?path=fdd7631f3f812fe9da3ea4c19349bdaaa04ed574f0c9c5a894aff5666e1bee347eb09199f6f2e628448e5fd9306e16a66148e46bd88c26d9cb3e1b50aa1f027a&pathIsEncrypted=1&dossiernummer=BZ_2024_130
