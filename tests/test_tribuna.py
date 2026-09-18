"""Offline regression tests for Tribuna Base64 token parsing and path decryption.

Run with: python -m unittest discover -s tests
"""
import unittest
from unittest.mock import Mock

from scrapy.http import Request, TextResponse

from NeueScraper.spiders.FR_Gerichte import FR_Gerichte


class TribunaSpiderTests(unittest.TestCase):
    def setUp(self):
        self.spider = FR_Gerichte()
        self.spider.kanton_kurz = "FR"
        self.spider.detect = Mock(return_value=("FR_TC_001", "TC", "Cour d'appel civil"))

    def test_re_pfad2_matches_legacy_hex_and_base64(self):
        hex_token = "a" * 128
        self.assertTrue(bool(self.spider.rePfad2.fullmatch(hex_token)))

        base64_token_with_escape = (
            "AAAADO63ZKR6iKkHlm9L3YgtsHe8pv4TpPMP+OCvHXFtGi4E99rlBGMmgufpInL2Z8CaBHJdBtw"
            "PdilZ5u1jVIdFxOVLuzo6staSJ5UoZiX3Zuy5adHCDCm1n/Nr1af8x0nCXdU8crE\\x3D"
        )
        self.assertTrue(bool(self.spider.rePfad2.fullmatch(base64_token_with_escape)))

        base64_token_with_equal = base64_token_with_escape.replace("\\x3D", "=")
        self.assertTrue(bool(self.spider.rePfad2.fullmatch(base64_token_with_equal)))

        # Negative checks: short strings or ordinary text should not match
        self.assertFalse(bool(self.spider.rePfad2.fullmatch("TC")))
        self.assertFalse(bool(self.spider.rePfad2.fullmatch("Kantonsgericht")))

    def test_parse_page_handles_base64_pfad(self):
        # Sample response payload modeled after Tribuna GWT RPC search response
        payload = (
            '//OK[1,0,28,6,0,0,61,["java.util.ArrayList/4159755760",'
            '"tribunavtplus.client.db.ERGEBNISSTORE/1167561899","102","II. Zivilappellationshof",'
            '"","7f8c8c02679a4cedbd74262fc5ef8bbf",'
            '"Arrêt de la IIe Cour d\\x27appel civil du Tribunal cantonal","102 2026 139",'
            '"2026-08-20","-","TC","Kantonsgericht",'
            '"AAAADO63ZKR6iKkHlm9L3YgtsHe8pv4TpPMP+OCvHXFtGi4E99rlBGMmgufpInL2Z8CaBHJdBtw'
            'PdilZ5u1jVIdFxOVLuzo6staSJ5UoZiX3Zuy5adHCDCm1n/Nr1af8x0nCXdU8crE\\x3D",'
            '"Miete","0000-00-00","Gericht Broye","Bail à loyer","2026-09-18",'
            '"java.util.HashMap/1797211028","java.lang.String/2004016611"],0,7]'
        )
        request = Request("https://entscheidsuche.ch/fr_helper/loadTable.php", method="POST")
        response = TextResponse(request.url, body=payload.encode("utf-8"), encoding="utf-8", request=request)

        results = list(self.spider.parse_page(response))
        self.assertEqual(len(results), 1)

        decrypt_req = results[0]
        self.assertIsInstance(decrypt_req, Request)
        self.assertEqual(decrypt_req.url, self.spider.DECRYPT_PAGE_URL)

        # Ensure \\x3D in pfad is decoded to = before forming the GWT RPC request body
        body_text = decrypt_req.body.decode("utf-8")
        self.assertIn("crE=", body_text)
        self.assertNotIn(r"\x3D", body_text)

    def test_decrypt_path_quotes_base64_token(self):
        decrypt_payload = (
            '//OK[6,2,5,2,4,2,3,2,2,1,["java.util.HashMap/1797211028",'
            '"java.lang.String/2004016611","partURL",'
            '"102_2026_139_AAAADO63ZKR6iKkHlm9L3YgtsHe8pv4TpPMP+OCvHXFtGi4E99rlBGMmgufpInL2Z8CaBHJdBtw'
            'PdilZ5u1jVIdFxOVLuzo6staSJ5UoZiX3Zuy5adHCDCm1n/Nr1af8x0nCXdU8crE\\x3D",'
            '"dossiernummer","102_2026_139"],0,7]'
        )
        request = Request(self.spider.DECRYPT_PAGE_URL, meta={
            "item": {"DocId": "7f8c8c02679a4cedbd74262fc5ef8bbf", "Num": "102 2026 139"},
            "html_request": None,
        })
        response = TextResponse(request.url, body=decrypt_payload.encode("utf-8"), encoding="utf-8", request=request)

        results = list(self.spider.decrypt_path(response))
        self.assertEqual(len(results), 1)
        item = results[0]
        pdf_url = item["PDFUrls"][0]

        # Ensure + is percent-encoded to %2B and = is decoded/encoded to %3D in query param
        self.assertIn("path=AAAADO63ZKR6iKkHlm9L3YgtsHe8pv4TpPMP%2BOCv", pdf_url)
        self.assertTrue(pdf_url.endswith("crE%3D&pathIsEncrypted=1&dossiernummer=102_2026_139"))

    def test_decrypt_path_legacy_hex_token(self):
        hex_token = "a" * 128
        decrypt_payload = (
            f'//OK[6,2,5,2,4,2,3,2,2,1,["java.util.HashMap/1797211028",'
            f'"java.lang.String/2004016611","partURL",'
            f'"102_2026_139_{hex_token}",'
            f'"dossiernummer","102_2026_139"],0,7]'
        )
        request = Request(self.spider.DECRYPT_PAGE_URL, meta={
            "item": {"DocId": "7f8c8c02679a4cedbd74262fc5ef8bbf", "Num": "102 2026 139"},
            "html_request": None,
        })
        response = TextResponse(request.url, body=decrypt_payload.encode("utf-8"), encoding="utf-8", request=request)

        results = list(self.spider.decrypt_path(response))
        self.assertEqual(len(results), 1)
        pdf_url = results[0]["PDFUrls"][0]
        self.assertIn(f"path={hex_token}&", pdf_url)


if __name__ == "__main__":
    unittest.main()
