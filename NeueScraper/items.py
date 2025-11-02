# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NeuescraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    Signatur = scrapy.Field()
    Spider = scrapy.Field()
    Job = scrapy.Field()
    Kanton = scrapy.Field()
    Gericht = scrapy.Field()
    VGericht = scrapy.Field()
    Kammer = scrapy.Field()
    VKammer = scrapy.Field()
    Num = scrapy.Field()
    Num2 = scrapy.Field()
    noNumDisplay=scrapy.Field()
    EDatum = scrapy.Field()
    Titel = scrapy.Field()
    Leitsatz = scrapy.Field()
    PDatum = scrapy.Field()
    SDatum = scrapy.Field()
    Rechtsgebiet = scrapy.Field()
    Normen = scrapy.Field()
    DocID = scrapy.Field()
    PDFUrls = scrapy.Field()
    HTMLUrls = scrapy.Field()
    PDFFiles = scrapy.Field()
    ProxyUrls = scrapy.Field()
    PdfHeaders = scrapy.Field()
    HTMLFiles = scrapy.Field()
    Raw = scrapy.Field()
    Gerichtsbarkeit = scrapy.Field()
    Weiterzug = scrapy.Field()
    Entscheidart = scrapy.Field()
    Sammlung = scrapy.Field()
    LeitsatzKurz = scrapy.Field()
    Pos = scrapy.Field()
    html = scrapy.Field()
    Formal_de=scrapy.Field()
    Formal_fr=scrapy.Field()
    Formal_it=scrapy.Field()
    Abstract=scrapy.Field()
    Abstract_de=scrapy.Field()
    Abstract_fr=scrapy.Field()
    Abstract_it=scrapy.Field()
    Formal_org=scrapy.Field()
    Sprache=scrapy.Field()
    Upload=scrapy.Field()
    CookieJar=scrapy.Field()
    # pass


"""
<Entscheid>
	<Metainfos>
		<Signatur>...</Signatur>!
		<Spider>...</Spider>!
		<Job>...</Job>!
		<Kanton>...</Kanton>!
		<Gericht>...</Gericht>!
		<Kammer>...</Kammer>?
		<Geschaeftsnummer>...</Geschaeftsnummer>?
		<EDatum>...</EDatum>?
		<PDFFile>PDF-Dateiname</PDFFile>?
		<HTMLFile>HTML-Dateiname</HTMLFile>?
		<Sprache>de|fr|it</Sprache>?
	</Metainfos>
	<Treffer>
		<Quelle>
			<Gerichtsbarkeit>...</Gerichtsbarkeit>?
			<Gericht>...</Gericht>!
			<Kammer>...</Kammer>?
			<Geschaeftsnummer>...</Geschaeftsnummer>?
			<Sammlung>...</Sammlung>?
			<EDatum>...</EDatum>?
		</Quelle>
		<Kurz>
			<Titel>...</Titel>?
			<Leitsatz>...</Leitsatz>?
			<Rechtsgebiet>...</Rechtsgebiet>?
			<Entscheidart>...</Entscheidart>?
		</Kurz>
		<Sonst>
			<PDatum>...</PDatum>?
			<Weiterzug>...</Weiterzug>?
		</Sonst>
		<Source>
			<DocID>...</DocID>?
			<PdfUrl>...</PdfUrl>*
			<HtmlUrl>...</HtmlUrl>*
			<Raw>...</Raw>?
		</Source>
	</Treffer>
</Entscheid>"""
			
			
			
