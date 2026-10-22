import copy
import json
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

import build_discovery_pages as discovery


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.public = self.root / 'public'
        self.output = self.root / 'dist'
        (self.public / 'data').mkdir(parents=True)
        (self.public / 'privacy').mkdir()
        self.output.mkdir()
        self.shell = ('<!doctype html><html><head><title>Old</title>'
                      '<meta name="description" content="Old"><meta property="og:title" content="Old">'
                      '<link rel="canonical" href="https://crime.compare/"></head><body><div id="root">'
                      + discovery.ROOT_START + '<p>Loading</p>' + discovery.ROOT_END
                      + '</div><script type="module" src="/assets/app.js"></script></body></html>')
        (self.output / 'index.html').write_text(self.shell)
        (self.public / 'privacy/index.html').write_text('<html><head><title>Privacy — CrimeLedger</title><meta name="description" content="Analytics choices."><link rel="canonical" href="https://crime.compare/privacy/"></head><body><main><h1>Privacy</h1><p>No permission, no analytics.</p></main><script src="/audience.js"></script></body></html>')
        self.categories = [
            {'id': 'all-crime', 'label': 'All recorded crime', 'description': 'Excludes fraud.', 'ratePer': 1000, 'group': 'Main groups', 'nationalIncludesBtp': True},
            {'id': 'homicide', 'label': 'Homicide', 'description': 'A rare offence.', 'ratePer': 100000, 'group': 'Details', 'nationalIncludesBtp': True},
        ]
        def area(identifier, name, kind, eligible=True, region=None):
            return {'id': identifier, 'code': identifier, 'name': name, 'type': kind,
                    'comparisonEligible': eligible, 'regionId': region, 'population': 100000,
                    'populationYear': 2025, 'quality': [] if eligible else ['Resident rates are suppressed.'],
                    'metrics': {'all-crime': {'count': 1000, 'rate': 128.45 if eligible else None, 'changePercent': -1.25,
                                               'history': [{'periodEnd': '2026-06-30', 'count': 1000, 'rate': 128.45 if eligible else None}]},
                                'homicide': {'count': 4, 'rate': 0.00501967 if eligible else None, 'changePercent': None,
                                             'changeSuppressedReason': 'ONS small-base suppression.', 'history': []}}}
        self.force = area('E23000039', 'Example', 'force', region='E12000009')
        self.region = area('E12000009', 'Example', 'region')
        self.city = area('E23000034', 'City of London', 'force', eligible=False)
        self.data = {'generatedAt': '2026-10-22T10:00:00Z', 'baselineId': 'K04000001',
                     'coverage': {'start': '2025-07-01', 'end': '2026-06-30', 'sourcePublishedAt': '2026-10-22'},
                     'categories': self.categories, 'areas': [area('K04000001', 'England and Wales', 'nation'), self.force, self.region, self.city],
                     'sources': [{'id': 'official', 'title': 'Official source', 'url': 'https://example.org/table?x=1&y=2', 'publishedAt': '2026-10-22'}],
                     'methodology': ['A rolling year, not one quarter.'], 'notes': ['Categories overlap.']}
        monthly_area = copy.deepcopy(self.force)
        monthly_area['metrics']['all-crime']['count'] = None
        monthly_area['metrics']['all-crime']['rate'] = None
        monthly_area['monthlyCoverage'] = {'currentComplete': False}
        self.monthly = {'generatedAt': '2026-10-22T10:00:00Z', 'coverage': {'start': '2025-09-01', 'end': '2026-08-31', 'sourcePublishedAt': '2026-09-30'},
                        'areas': [monthly_area], 'sources': self.data['sources'], 'notes': ['A separate provisional series.']}
        self.write_data()

    def write_data(self):
        (self.public / 'data/crime.json').write_text(json.dumps(self.data))
        (self.public / 'data/monthly.json').write_text(json.dumps(self.monthly))

    def write_manifest(self, previous=None):
        pages = discovery.make_pages(self.public)
        manifest = discovery.manifest_for(pages, previous)
        (self.public / discovery.MANIFEST).write_bytes(discovery.json_bytes(manifest))
        return manifest

    def build(self):
        self.write_manifest()
        return discovery.build(self.output, self.public)

    def test_canonical_metadata_schema_and_standalone_links(self):
        manifest = self.build()
        self.assertEqual(len(manifest['pages']), 11)
        self.assertEqual(len({row['title'] for row in manifest['pages'].values()}), 11)
        page = (self.output / 'areas/E23000039/index.html').read_text()
        self.assertEqual(page.count('rel="canonical"'), 1)
        self.assertIn('href="https://crime.compare/areas/E23000039/"', page)
        self.assertIn('police force area crime statistics', page)
        self.assertIn('href="/?area=E23000039&amp;crime=all-crime"', page)
        self.assertIn('href="/crime/homicide/"', page)
        self.assertIn('https://crime.compare/social-card.png', page)
        self.assertIn('"@type":"BreadcrumbList"', page)
        self.assertIn('"@type":"WebSite"', page)
        self.assertIn('"@type":"Organization"', page)
        self.assertNotIn('audience.js', page)
        self.assertNotIn('type="module"', page)
        self.assertIn('data-snapshot-end="2026-06-30"', page)
        self.assertIn('1 July 2025', page)
        self.assertIn('30 June 2026', page)

    def test_rates_match_js_rounding_units_and_change_precision(self):
        self.assertEqual(discovery.rate({'rate': 128.45}, self.categories[0], self.force), '128.5 per 1,000')
        self.assertEqual(discovery.rate({'rate': 0.00501967}, self.categories[1], self.force), '0.5 per 100,000')
        self.assertEqual(discovery.rate({'rate': 1.25}, self.categories[0], self.force), '1.3 per 1,000')
        self.assertEqual(discovery.change({'changePercent': -1.25}), '-1.3%')
        self.assertEqual(discovery.change({'changePercent': 2.55}), '+2.5%')
        self.assertEqual(discovery.change({'changePercent': -0.04}), '&lt;0.1% decrease')

    def test_suppression_and_missing_months_never_become_zero(self):
        self.build()
        page = (self.output / 'areas/E23000039/index.html').read_text()
        city = (self.output / 'areas/E23000034/index.html').read_text()
        self.assertIn('ONS small-base suppression.', page)
        self.assertIn('latest rolling year is incomplete', page)
        self.assertNotIn('Recorded offences: <strong>0</strong>', page)
        self.assertIn('Resident rates are suppressed.', city)
        self.assertIn('Unavailable', city)
        self.assertEqual(discovery.rate({'rate': 10}, self.categories[0], self.city), 'Unavailable')

    def test_generated_times_do_not_change_content_hashes_or_dates(self):
        manifest = self.write_manifest()
        for row in manifest['pages'].values():
            row['lastmod'] = '2026-01-01'
        manifest['sitemapSha256'] = discovery.sha256(discovery.sitemap_bytes(manifest))
        self.data['generatedAt'] = '2026-10-23T12:00:00Z'
        self.monthly['generatedAt'] = '2026-10-23T12:00:00Z'
        self.monthly['officialSnapshotGeneratedAt'] = '2026-10-23T12:00:00Z'
        self.write_data()
        expected = discovery.manifest_for(discovery.make_pages(self.public), manifest)
        self.assertEqual(expected, manifest)

    def test_changed_statistic_updates_only_meaningful_pages_and_requires_manifest(self):
        before = self.write_manifest()
        self.data['areas'][1]['metrics']['all-crime']['count'] = 1001
        self.write_data()
        with self.assertRaisesRegex(ValueError, 'manifest is stale'):
            discovery.validate(public_dir=self.public)
        after = discovery.manifest_for(discovery.make_pages(self.public), before)
        self.assertNotEqual(before['pages']['/areas/E23000039/']['contentSha256'], after['pages']['/areas/E23000039/']['contentSha256'])
        self.assertEqual(before['pages']['/privacy/'], after['pages']['/privacy/'])

    def test_privacy_body_changes_are_hashed_and_its_controller_is_preserved(self):
        before = self.build()
        path = self.public / 'privacy/index.html'
        path.write_text(path.read_text().replace('No permission, no analytics.', 'Updated choices and retention.'))
        after = self.write_manifest(before)
        self.assertNotEqual(before['pages']['/privacy/']['contentSha256'], after['pages']['/privacy/']['contentSha256'])
        discovery.build(self.output, self.public)
        page = (self.output / 'privacy/index.html').read_text()
        self.assertIn('Updated choices and retention.', page)
        self.assertIn('src="/audience.js"', page)
        self.assertEqual(page.count('rel="canonical"'), 1)

    def test_safe_escaping_of_text_links_and_jsonld(self):
        self.data['areas'][1]['name'] = 'A & B <script>alert(1)</script>'
        self.write_data()
        self.build()
        page = (self.output / 'areas/E23000039/index.html').read_text()
        self.assertIn('A &amp; B &lt;script&gt;', page)
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('\\u003cscript\\u003e', page)
        self.assertIn('https://example.org/table?x=1&amp;y=2', page)
        for url in ['javascript:alert(1)', '//evil.example/path', '/../../private', 'http://example.org', 'https://user:secret@example.org']:
            with self.assertRaises(ValueError):
                discovery.safe_url(url)

    def test_sitemap_has_exact_clean_canonical_routes_and_hash(self):
        manifest = self.build()
        raw = (self.output / 'sitemap.xml').read_bytes()
        parsed = ElementTree.fromstring(raw)
        urls = [row.text for row in parsed.findall('{*}url/{*}loc')]
        self.assertEqual(set(urls), {discovery.BASE + route for route in manifest['pages']})
        self.assertEqual(len(urls), len(set(urls)))
        self.assertTrue(all('?' not in url and '#' not in url for url in urls))
        self.assertEqual(discovery.sha256(raw), manifest['sitemapSha256'])
        (self.output / 'sitemap.xml').write_text('<urlset/>')
        with self.assertRaisesRegex(ValueError, 'sitemap.xml'):
            discovery.validate(self.output, self.public)

    def test_root_fallback_is_meaningful_preserves_bundle_and_rebuild_is_idempotent(self):
        self.build()
        root = (self.output / 'index.html').read_text()
        self.assertIn('data-discovery-page="/"', root)
        self.assertIn('href="/areas/"', root)
        self.assertIn('src="/assets/app.js"', root)
        self.assertNotIn('<p>Loading</p>', root)
        before = {str(p.relative_to(self.output)): p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        discovery.build(self.output, self.public)
        self.assertEqual(before, {str(p.relative_to(self.output)): p.read_bytes() for p in self.output.rglob('*') if p.is_file()})

    def test_obsolete_owned_pages_removed_without_deleting_unowned_content(self):
        self.build()
        old = self.output / 'areas/E23000999/index.html'
        old.parent.mkdir()
        old.write_text('obsolete')
        custom = self.output / 'areas/editorial/index.html'
        custom.parent.mkdir()
        custom.write_text('preserved')
        with self.assertRaisesRegex(ValueError, 'obsolete'):
            discovery.validate(self.output, self.public)
        discovery.build(self.output, self.public)
        self.assertFalse(old.exists())
        self.assertEqual(custom.read_text(), 'preserved')

    def test_paths_symlinks_and_unsafe_source_links_fail_before_writes(self):
        for route in ['/areas/../../private/', '/areas/E23000039/?q=x', '/crime/evil.html/', '//example.org/']:
            with self.assertRaises(ValueError):
                discovery.route_file(route)
        self.write_manifest()
        external = self.root / 'external'
        external.mkdir()
        (self.output / 'areas').symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'escapes|symlink'):
            discovery.build(self.output, self.public)
        self.assertEqual(list(external.iterdir()), [])
        self.data['sources'][0]['url'] = 'javascript:alert(1)'
        self.write_data()
        with self.assertRaises(ValueError):
            discovery.make_pages(self.public)

    def test_missing_manifest_markers_and_future_dates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'manifest missing'):
            discovery.validate(public_dir=self.public)
        manifest = self.write_manifest()
        for row in manifest['pages'].values():
            row['lastmod'] = '2999-01-01'
        with self.assertRaisesRegex(ValueError, 'future'):
            discovery.manifest_for(discovery.make_pages(self.public), manifest)
        (self.output / 'index.html').write_text('<html><head></head><body>No slot</body></html>')
        with self.assertRaisesRegex(ValueError, 'marker'):
            discovery.build(self.output, self.public)


if __name__ == '__main__':
    unittest.main()
