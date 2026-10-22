"""Offline live-verifier tests; fixtures contain no real audience information."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest

import verify_discovery_live as live


def cf_encode(text):
    key = 91
    return bytes([key, *(value ^ key for value in text.encode())]).hex()


class DiscoveryLiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name)
        self.routes = ["/", "/areas/", "/crime/", "/areas/E23000013/", "/areas/E23000014/", "/crime/robbery/", "/methodology/", "/sources/", "/privacy/"]
        self.manifest = {"schemaVersion": live.SCHEMA, "baseUrl": live.BASE, "pages": {}}
        self.remote = {}
        for index, route in enumerate(self.routes):
            path = "index.html" if route == "/" else route.lstrip("/") + "index.html"
            title = f"Comparison {index}"
            description = f"Recorded offences and source notes for page {index}."
            record = {"path": path, "title": title, "description": description, "kind": "page", "contentSha256": "a" * 64, "lastmod": "2026-10-22"}
            self.manifest["pages"][route] = record
            marker = "" if route == "/privacy/" else f' data-discovery-page="{route}" data-snapshot-end="2026-06-30"'
            structured = json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "WebPage", "url": live.BASE + route}, {"@type": "BreadcrumbList", "itemListElement": []}]})
            html = f'''<!doctype html><html><head><title>{title} | CrimeLedger</title>
<meta name="description" content="{description}"><link rel="canonical" href="{live.BASE}{route}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{description}">
<meta property="og:type" content="website"><meta property="og:url" content="{live.BASE}{route}">
<meta property="og:image" content="{live.BASE}/social-card.png"><meta property="og:image:alt" content="CrimeLedger map">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{live.BASE}/social-card.png">
<script type="application/ld+json">{structured}</script><script defer src="/audience.js"></script></head>
<body><main{marker}><h1>{title}</h1><p>Snapshot 30 June 2026: 1,234 offences.</p><a href="/?area=E23000013&amp;crime=robbery">Open comparison</a><p>Contact <a href="mailto:admin@example.test?subject=privacy">admin@example.test</a>.</p></main></body></html>'''
            target = self.site / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(html)
            self.remote[route] = html.encode()
        sitemap = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{live.BASE}{route}</loc><lastmod>2026-10-22</lastmod></url>' for route in self.routes) + '</urlset>'
        (self.site / 'sitemap.xml').write_text(sitemap)
        self.remote['/sitemap.xml'] = sitemap.encode()
        self.manifest['sitemapSha256'] = hashlib.sha256(sitemap.encode()).hexdigest()
        self.save_manifest()
        image = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR' + struct.pack('>II', 1200, 630) + b'fixture'
        (self.site / 'social-card.png').write_bytes(image)
        self.remote['/social-card.png'] = image

    def save_manifest(self):
        raw = (json.dumps(self.manifest, indent=2) + '\n').encode()
        (self.site / live.MANIFEST).write_bytes(raw)
        self.remote['/' + live.MANIFEST] = raw

    def fetch(self, url):
        route = live.urlsplit(url).path
        content_type = 'application/json' if route.endswith('.json') else 'application/xml' if route.endswith('.xml') else 'image/png' if route.endswith('.png') else 'text/html; charset=utf-8'
        return live.Response(url, self.remote[route], {'content-type': content_type})

    def assert_rejected(self, message, **kwargs):
        with self.assertRaisesRegex(live.VerificationError, message):
            live.verify(self.site, fetcher=self.fetch, **kwargs)

    def test_representative_and_all_pages_match_without_executing_javascript(self):
        self.assertEqual(live.verify(self.site, fetcher=self.fetch), {'manifestPages': 9, 'verifiedPages': 8, 'socialImages': 1})
        self.assertEqual(live.verify(self.site, fetcher=self.fetch, all_pages=True)['verifiedPages'], 9)

    def test_all_mode_checks_additional_detail_pages(self):
        self.remote['/areas/E23000014/'] = self.remote['/areas/E23000014/'].replace(b'1,234 offences', b'9,999 offences')
        self.assertEqual(live.verify(self.site, fetcher=self.fetch)['verifiedPages'], 8)
        self.assert_rejected('visible_text differs', all_pages=True)

    def test_accessible_svg_title_is_not_a_second_document_title(self):
        route = '/areas/E23000013/'
        raw = self.remote[route].replace(b'</main>', b'<svg role="img"><title>Area within England and Wales</title><path d="M0 0L1 1"/></svg></main>')
        expected = live.Page(raw)
        self.assertEqual(len(expected.titles), 1)
        live.validate_page(expected, route, self.manifest['pages'][route])

    def test_cloudflare_email_transform_and_decoder_script_are_accepted(self):
        route = '/privacy/'
        original = self.remote[route].decode()
        protected = f'<a href="/cdn-cgi/l/email-protection#{cf_encode("admin@example.test?subject=privacy")}"><span class="__cf_email__" data-cfemail="{cf_encode("admin@example.test")}">[email&#160;protected]</span></a>'
        altered = original.replace('<a href="mailto:admin@example.test?subject=privacy">admin@example.test</a>', protected)
        altered = altered.replace('</body>', '<script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script></body>')
        self.remote[route] = altered.encode()
        self.assertEqual(live.verify(self.site, fetcher=self.fetch)['verifiedPages'], 8)

    def test_changed_visible_offence_count_is_rejected(self):
        self.remote['/areas/E23000013/'] = self.remote['/areas/E23000013/'].replace(b'1,234 offences', b'9,999 offences')
        self.assert_rejected('visible_text differs')

    def test_wrong_or_duplicate_canonical_is_rejected(self):
        self.remote['/'] = self.remote['/'].replace(b'href="https://crime.compare/"', b'href="https://crime.compare/?crime=robbery"')
        self.assert_rejected('canonical URL')

    def test_metadata_or_snapshot_mismatch_is_rejected(self):
        self.remote['/'] = self.remote['/'].replace(b'data-snapshot-end="2026-06-30"', b'data-snapshot-end="2025-06-30"')
        self.assert_rejected('markers differs')

    def test_unexpected_external_script_is_rejected(self):
        self.remote['/'] = self.remote['/'].replace(b'</body>', b'<script src="https://example.test/extra.js"></script></body>')
        self.assert_rejected('unexpected published script')

    def test_event_handler_and_inline_executable_script_are_rejected(self):
        for injection in [b'<img src="/bad.png" onerror="alert(1)">', b'<script>alert(1)</script>']:
            with self.subTest(injection=injection):
                initial = (self.site / 'index.html').read_bytes()
                self.remote['/'] = initial.replace(b'</body>', injection + b'</body>')
                self.assert_rejected('unsafe HTML')

    def test_noindex_meta_and_production_response_header_are_rejected(self):
        self.remote['/'] = self.remote['/'].replace(b'</head>', b'<meta name="robots" content="noindex,follow"></head>')
        self.assert_rejected('noindex')
        self.remote['/'] = (self.site / 'index.html').read_bytes()
        def noindex(url):
            result = self.fetch(url)
            return live.Response(result.url, result.body, {**result.headers, 'x-robots-tag': 'noindex'})
        with self.assertRaisesRegex(live.VerificationError, 'X-Robots-Tag'):
            live.verify(self.site, fetcher=noindex)
        self.assertEqual(live.verify(self.site, base_url='https://example.crime-compare.pages.dev', fetcher=noindex)['verifiedPages'], 8)

    def test_jsonld_query_url_is_rejected(self):
        self.remote['/'] = self.remote['/'].replace(b'"url": "https://crime.compare/"', b'"url": "https://crime.compare/?area=E23000013"')
        self.assert_rejected('JSON-LD contains a query')

    def test_manifest_byte_difference_is_rejected(self):
        self.remote['/' + live.MANIFEST] += b' '
        self.assert_rejected('manifest differs')

    def test_sitemap_whitespace_is_accepted_but_wrong_date_is_rejected(self):
        raw = self.remote['/sitemap.xml']
        self.remote['/sitemap.xml'] = raw.replace(b'><', b'>\n  <')
        self.assertEqual(live.verify(self.site, fetcher=self.fetch)['verifiedPages'], 8)
        self.remote['/sitemap.xml'] = raw.replace(b'2026-10-22', b'2026-10-23')
        self.assert_rejected('sitemap differs')

    def test_small_or_changed_social_card_is_rejected(self):
        self.remote['/social-card.png'] += b'changed'
        self.assert_rejected('social image differs')
        path = self.site / 'social-card.png'
        path.write_bytes(path.read_bytes()[:16] + struct.pack('>II', 300, 360))
        self.assert_rejected('1200 by 630')

    def test_response_type_and_unexpected_redirect_are_rejected(self):
        def wrong_type(url):
            result = self.fetch(url)
            return live.Response(result.url, result.body, {'content-type': 'text/plain'})
        with self.assertRaisesRegex(live.VerificationError, 'Content-Type'):
            live.verify(self.site, fetcher=wrong_type)
        def redirected(url):
            result = self.fetch(url)
            return live.Response('https://other.example/', result.body, result.headers)
        with self.assertRaisesRegex(live.VerificationError, 'unexpected redirect'):
            live.verify(self.site, fetcher=redirected)

    def test_manifest_file_cannot_escape_site_directory(self):
        self.manifest['pages']['/']['path'] = '../index.html'
        self.save_manifest()
        self.assert_rejected('Unsafe discovery file path')

    def test_unrelated_hosts_or_insecure_origin_are_rejected(self):
        for origin in ['http://crime.compare', 'https://other.pages.dev', 'https://crime.compare.evil.test', 'https://crime.compare/?x=1']:
            with self.subTest(origin=origin):
                self.assert_rejected('Verification origin', base_url=origin)


if __name__ == '__main__':
    unittest.main()
