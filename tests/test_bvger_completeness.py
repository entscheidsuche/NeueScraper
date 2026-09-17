"""Offline callback and scrapelog regressions for incomplete BVGer responses.

Run with: python -m unittest discover -s tests
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scrapy import Request
from scrapy.http import HtmlResponse

from NeueScraper.pipelines import MyFilesPipeline, MyWriterPipeline
from NeueScraper.spiders.CH_BVGer import CH_BVGer


class BVGerCompletenessTests(unittest.TestCase):
    def setUp(self):
        self.spider = CH_BVGer(ab="2026", bis="2026")
        self.next_year = Request("https://example.test/next-year")
        self.spider.requeststack = [self.next_year]
        self.spider.fehler = 0
        self.spider.files_written = {}
        self.spider.kanton_kurz = "CH"
        self.spider.detect = Mock(return_value=("CH_BVGE_001", "BVGer", "IV"))

    def response(self, text):
        request = Request("https://example.test/results", meta={
            "ab": "01.01.2026", "bis": "31.12.2026",
            "jSession": "ABC", "iceSession": "test-session",
        })
        return HtmlResponse(request.url, body=text.encode(), encoding="utf-8", request=request)

    def report(self, expected_errors):
        with patch.object(MyFilesPipeline, "common_store", create=True) as store:
            MyWriterPipeline().on_spider_closed(self.spider, "finished")
            payload = json.loads(store.persist_file.call_args.args[1].getvalue())
        self.assertEqual(payload["fehler_dokumente"], expected_errors)
        self.assertEqual(payload["fehlerfrei"], expected_errors == 0)
        return payload

    def test_expired_session_is_not_reported_as_success(self):
        result = list(self.spider.trefferliste(self.response("<session-expired/>")))
        self.assertEqual(result, [self.next_year])
        self.report(1)

    def test_missing_initial_session_is_not_reported_as_success(self):
        result = list(self.spider.parse_suchform(self.response("<html>No session</html>")))
        self.assertEqual(result, [self.next_year])
        self.report(1)

    def test_explicit_empty_search_is_valid(self):
        result = list(self.spider.trefferliste(self.response(
            '<span style="color: red;">Kein Suchtreffer!</span>'
        )))
        self.assertEqual(result, [self.next_year])
        self.report(0)

    def header(self, last="2", page="1", pages="1", first="1"):
        return ('<span class="iceOutFrmt standard">2 Entscheide gefunden, zeige '
                f'{first} bis {last}. Seite {page} von {pages}. Resultat sortiert')

    def matches(self, count):
        # Isolate result accounting from the site's large document-row regex.
        rows = [dict(PDFUrl=f"/document/{i}", Pos=str(i), EDatum="01.01.2026",
                     VKammer="IV", LeitsatzKurz="", Num=f"D-{i+1}/2026")
                for i in range(count)]
        self.spider.reTreffer = SimpleNamespace(finditer=lambda _: [
            SimpleNamespace(groupdict=lambda row=row: dict(row)) for row in rows
        ])

    def test_nonempty_page_without_parsed_rows_is_incomplete(self):
        result = list(self.spider.trefferliste(self.response(self.header())))
        self.assertEqual(result, [self.next_year])
        self.report(1)

    def test_partial_page_keeps_documents_but_disables_removal(self):
        self.matches(1)
        result = list(self.spider.trefferliste(self.response(self.header())))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["Num"], "D-1/2026")
        self.assertIs(result[-1], self.next_year)
        self.report(1)

    def test_complete_page_keeps_success(self):
        self.matches(2)
        result = list(self.spider.trefferliste(self.response(self.header())))
        self.assertEqual(len(result), 3)
        self.report(0)

    def test_partial_nonfinal_page_still_continues_pagination(self):
        self.matches(1)
        result = list(self.spider.trefferliste(self.response(self.header(pages="2"))))
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[-1], Request)
        self.assertEqual(result[-1].callback, self.spider.trefferliste)
        self.assertEqual(self.spider.requeststack, [self.next_year])
        self.report(1)

    def test_thousands_separators_in_inclusive_range(self):
        self.matches(2)
        list(self.spider.trefferliste(self.response(self.header(first="1,000", last="1,001"))))
        self.report(0)


if __name__ == "__main__":
    unittest.main()
