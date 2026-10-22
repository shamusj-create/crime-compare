#!/usr/bin/env python3
"""Build dated, standalone discovery HTML from the public crime snapshots.

Standard library only; no network access or source-data mutation. Regenerate the
committed semantic manifest with --write-manifest after meaningful content/data
changes. --check needs no build directory; --check --output dist also verifies
the generated release. Normal --output dist publication requires a current
manifest and an already-built Vite index containing the discovery-root markers.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC = ROOT / "public"
BASE = "https://crime.compare"
MANIFEST = "discovery-manifest.json"
SCHEMA = "crime-compare-discovery-1.0.0"
ROOT_START = "<!--discovery-root:start-->"
ROOT_END = "<!--discovery-root:end-->"
META_START = "<!--discovery-meta:start-->"
META_END = "<!--discovery-meta:end-->"
AREA_ID = re.compile(r"[EW]\d{8}")
CATEGORY_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iso_day(value):
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise ValueError("Expected an ISO calendar date")
    return date.fromisoformat(value)


def readable_date(value):
    value = iso_day(value)
    return f"{value.day} {value.strftime('%B')} {value.year}"


def safe_url(value):
    if not isinstance(value, str) or re.search(r"[\x00-\x20\\]", value):
        raise ValueError("Invalid public link")
    parsed = urlsplit(value)
    if value.startswith("/") and not value.startswith("//"):
        if parsed.scheme or parsed.netloc or any(part in {".", ".."} for part in parsed.path.split("/")):
            raise ValueError("Unsafe local link")
        return value
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only local paths and HTTPS public sources are allowed")
    return value


def link(url, label, class_name=None):
    class_attribute = f' class="{esc(class_name)}"' if class_name else ""
    return f'<a href="{esc(safe_url(url))}"{class_attribute}>{esc(label)}</a>'


def comparison_url(area=None, category="all-crime", monthly=False):
    if not CATEGORY_ID.fullmatch(category):
        raise ValueError("Unsafe comparison category")
    params = []
    if area:
        if not AREA_ID.fullmatch(area["id"]):
            raise ValueError("Unsafe comparison area")
        params.append(("area", area["id"]))
        if area["type"] == "region":
            params.append(("areas", "region"))
    params.append(("crime", category))
    if monthly:
        params.append(("source", "monthly"))
    return "/?" + urlencode(params)


def number(value, decimals=0):
    if value is None:
        return "Unavailable"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid non-negative public statistic")
    return f"{value:,.{decimals}f}"


def rate(metric, category, area):
    value = metric.get("rate")
    if value is None or not area.get("comparisonEligible", False):
        return "Unavailable"
    denominator = category.get("ratePer", 1000)
    if denominator not in {1000, 100000}:
        raise ValueError("Unexpected rate denominator")
    # The public snapshots store all rates per 1,000, including rare measures.
    scaled = value * (denominator / 1000)
    if isinstance(value, bool) or not math.isfinite(scaled) or scaled < 0:
        raise ValueError("Invalid public resident rate")
    # Match categoryRate(): Math.round(value * multiplier * 10) / 10.
    rounded = math.floor(scaled * 10 + 0.5) / 10
    return f"{rounded:.1f} per {denominator:,}"


def change(metric):
    value = metric.get("changePercent")
    if value is None:
        reason = metric.get("changeSuppressedReason")
        return "Unavailable" + (f" — {esc(reason)}" if reason else "")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Invalid published percentage change")
    if value != 0 and abs(value) < 0.05:
        return '&lt;0.1% ' + ('decrease' if value < 0 else 'increase')
    # Match JavaScript Math.abs(value).toFixed(1), including binary float ties.
    absolute = Decimal.from_float(float(abs(value))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    sign = '-' if value < 0 else '+' if value > 0 else ''
    return f"{sign}{absolute:.1f}%"


def area_route(area):
    if not AREA_ID.fullmatch(area["id"]):
        raise ValueError("Unsafe area identifier")
    return f'/areas/{area["id"]}/'


def crime_route(category):
    if not CATEGORY_ID.fullmatch(category["id"]):
        raise ValueError("Unsafe category identifier")
    return f'/crime/{category["id"]}/'


def route_file(route):
    if route == "/":
        return "index.html"
    if route in {"/areas/", "/crime/", "/methodology/", "/sources/", "/privacy/"}:
        return route.lstrip("/") + "index.html"
    if re.fullmatch(r"/areas/[EW]\d{8}/", route) or re.fullmatch(r"/crime/[a-z][a-z0-9]*(?:-[a-z0-9]+)*/", route):
        return route.lstrip("/") + "index.html"
    raise ValueError(f"Unowned discovery route: {route}")


def is_owned_path(path):
    if path in {"index.html", "areas/index.html", "crime/index.html", "methodology/index.html", "sources/index.html", "privacy/index.html"}:
        return True
    return bool(re.fullmatch(r"(?:areas/[EW]\d{8}|crime/[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/index\.html", path))


@dataclass(frozen=True)
class Page:
    route: str
    title: str
    description: str
    kind: str
    body: str
    breadcrumbs: tuple
    snapshot_end: str | None = None

    @property
    def content_hash(self):
        # Asset hashes, generation/check times and build timestamps are absent.
        return sha256(json_bytes({"title": self.title, "description": self.description,
                                  "body": self.body, "breadcrumbs": self.breadcrumbs}))


def snapshot_note(dataset):
    coverage = dataset["coverage"]
    return ('<p class="discovery-meta">Dated official snapshot: '
            f'<time datetime="{esc(coverage["start"])}">{readable_date(coverage["start"])}</time> to '
            f'<time datetime="{esc(coverage["end"])}">{readable_date(coverage["end"])}</time>. '
            f'Source published {readable_date(coverage["sourcePublishedAt"])}.</p>'
            '<p class="discovery-note">This page contains a published snapshot. '
            'The interactive comparison shows the latest validated data and its actual dates. '
            'Monthly source checks do not create new monthly official observations.</p>')


def hero(eyebrow, title, description):
    return (f'<header class="discovery-hero"><p class="discovery-eyebrow">{esc(eyebrow)}</p>'
            f'<h1>{esc(title)}</h1><p class="discovery-intro">{esc(description)}</p></header>')


def section(title, body):
    return f'<section class="discovery-section"><h2>{esc(title)}</h2>{body}</section>'


def note_list(values):
    return '<ul class="discovery-list">' + "".join(f'<li>{esc(value)}</li>' for value in values) + '</ul>'


def source_links(sources):
    rows = []
    for source in sources:
        suffix = f' — published {readable_date(source["publishedAt"])}' if source.get("publishedAt") else ""
        rows.append(f'<li>{link(source["url"], source["title"])}{suffix}</li>')
    return '<ul class="discovery-list">' + "".join(rows) + '</ul>'


def map_svg(area, geography):
    shape = geography.get("areas", {}).get(area.get("code", area["id"]))
    if not shape:
        return ""
    viewbox = geography.get("viewBox", "")
    outline, selected = geography.get("outline", ""), shape.get("path", "")
    if not re.fullmatch(r"[0-9.\s-]+", viewbox) or len(viewbox.split()) != 4:
        raise ValueError("Invalid public map viewBox")
    for path in [outline, selected]:
        if not path or not re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE+.,\s-]+", path):
            raise ValueError("Invalid public map path")
    return (f'<figure class="discovery-map"><svg viewBox="{esc(viewbox)}" role="img" aria-labelledby="map-{esc(area["id"])}">'
            f'<title id="map-{esc(area["id"])}">{esc(area["name"])} within England and Wales</title>'
            f'<path d="{esc(outline)}" fill="#e8edf5" stroke="#bdc9dc" stroke-width="0.5"/>'
            f'<path d="{esc(selected)}" fill="#0a3fb7" stroke="#ffffff" stroke-width="0.6"/>'
            '</svg><figcaption>Simplified ONS boundary. '
            f'{link("/data/geography-sources.json", "Boundary sources and attribution")}</figcaption></figure>')


def metric_table(areas, category):
    rows = []
    for area in sorted(areas, key=lambda row: (row["name"].casefold(), row["id"])):
        metric = area.get("metrics", {}).get(category["id"], {})
        rows.append(f'<tr><th scope="row">{link(area_route(area), area["name"])}</th>'
                    f'<td>{number(metric.get("count"))}</td><td>{esc(rate(metric, category, area))}</td>'
                    f'<td>{change(metric)}</td></tr>')
    return ('<div class="discovery-table-wrapper"><table class="discovery-table">'
            '<thead><tr><th scope="col">Area</th><th scope="col">Recorded offences</th>'
            '<th scope="col">Resident-population rate</th><th scope="col">Year-on-year change</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')


def area_metric_table(area, categories):
    rows = []
    for category in categories:
        metric = area.get("metrics", {}).get(category["id"], {})
        rows.append(f'<tr><th scope="row">{link(crime_route(category), category["label"])}</th>'
                    f'<td>{number(metric.get("count"))}</td><td>{esc(rate(metric, category, area))}</td>'
                    f'<td>{change(metric)}</td></tr>')
    return ('<div class="discovery-table-wrapper"><table class="discovery-table">'
            '<caption>Official rolling-year snapshot; categories overlap and must not be added together.</caption>'
            '<thead><tr><th scope="col">Crime measure</th><th scope="col">Recorded offences</th>'
            '<th scope="col">Resident-population rate</th><th scope="col">Year-on-year change</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')


def stat(label, value):
    return f'<div class="discovery-stat"><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>'


def make_pages(public_dir=DEFAULT_PUBLIC):
    public_dir = Path(public_dir)
    data = read_json(public_dir / "data/crime.json")
    monthly_path = public_dir / "data/monthly.json"
    monthly = read_json(monthly_path) if monthly_path.is_file() else None
    geo_path = public_dir / "data/geography.json"
    geography = read_json(geo_path) if geo_path.is_file() else {}
    coverage = data["coverage"]
    for field in ["start", "end", "sourcePublishedAt"]:
        iso_day(coverage[field])
    categories = data["categories"]
    areas = [row for row in data["areas"] if row["type"] in {"force", "region"}]
    if not areas or not categories or len({row["id"] for row in areas}) != len(areas) or len({row["id"] for row in categories}) != len(categories):
        raise ValueError("Empty or duplicate public discovery identifiers")
    for area in areas:
        area_route(area)
    for category in categories:
        crime_route(category)
        if category.get("ratePer", 1000) not in {1000, 100000}:
            raise ValueError("Unexpected category rate denominator")
    total = next((row for row in categories if row["id"] == "all-crime"), None)
    if not total:
        raise ValueError("Missing all-crime category")
    nations = [row for row in data["areas"] if row["type"] == "nation"]
    national = next((row for row in nations if row["id"] == data.get("baselineId")), nations[0] if nations else None)
    by_id = {row["id"]: row for row in areas}
    monthly_areas = {row["id"]: row for row in monthly["areas"]} if monthly else {}
    pages = {}
    def add(route, title, description, kind, body, crumbs):
        route_file(route)
        pages[route] = Page(route, title, description, kind, body, tuple(crumbs), coverage["end"])
    home_crumb = [("Home", "/")]
    dates = snapshot_note(data)
    headline = "Compare crime across England and Wales"
    body = hero("The public crime record", headline, "Explore official police-recorded crime by area and offence, with population rates, dated evidence and clear limitations.")
    body += dates + '<div class="discovery-grid">'
    for route, label, detail in [("/areas/", "Explore areas", f'{len([a for a in areas if a["type"] == "force"])} police force areas and {len([a for a in areas if a["type"] == "region"])} regional units.'), ("/crime/", "Explore crime measures", f'{len(categories)} official measures, with definitions and their stated rate denominators.'), ("/methodology/", "Understand the comparisons", "Read what counts, how rates work and where comparisons are limited.")]:
        body += f'<article class="discovery-card"><h2>{link(route, label)}</h2><p>{esc(detail)}</p></article>'
    body += '</div><p>' + link('/#comparison', 'Open the interactive comparison', 'discovery-cta') + '</p>'
    body += section("Keep the meaning in view", '<p>Recorded crime is not all crime, an individual risk estimate or a measure of police effectiveness. Official quarterly statistics and provisional monthly Police.uk records are separate series.</p>' + link('/sources/', 'Read the official sources'))
    add('/', 'Compare crime in England and Wales — CrimeLedger', 'Compare police-recorded crime across England and Wales by police force area, region and crime type. Read dated counts, population rates and official evidence.', 'home', body, home_crumb)

    body = hero("Find a place", "Police force areas and regions", "Each area has a readable official snapshot, crime-type breakdown and links to the interactive comparison.") + dates
    for kind, heading in [('force', 'Police force areas'), ('region', 'Regions and Wales')]:
        cards = ''.join(f'<li class="discovery-card"><h3>{link(area_route(a), a["name"])}</h3><p>{"Police force area" if kind == "force" else "Regional unit"}{" · resident-rate comparison unavailable" if not a.get("comparisonEligible") else ""}</p></li>' for a in sorted(areas, key=lambda a: a['name'].casefold()) if a['type'] == kind)
        body += section(heading, '<ul class="discovery-grid">' + cards + '</ul>')
    add('/areas/', 'Police force areas and regions — CrimeLedger', 'Find crime statistics for police force areas and regions across England and Wales. Explore counts, population rates, source dates and comparison notes.', 'area-directory', body, home_crumb + [('Areas', '/areas/')])

    for area in areas:
        label = 'Police force area' if area['type'] == 'force' else 'Regional unit'
        metric = area.get('metrics', {}).get('all-crime', {})
        title = f'{area["name"]}: {label.lower()} crime statistics — CrimeLedger'
        description = f'Police-recorded crime for the {area["name"]} {label.lower()}: official counts, population rates and source notes for the year ending {readable_date(coverage["end"])}.'
        body = hero(label, f'Crime in {area["name"]}', description) + dates
        body += '<dl class="discovery-stats">' + stat('All recorded offences, excluding fraud', number(metric.get('count'))) + stat('Offences per 1,000 residents', rate(metric, total, area).replace(' per 1,000', '')) + stat('Resident population', f'{number(area.get("population"))} ({area.get("populationYear", "year unavailable")})') + '</dl>'
        body += '<p>' + link(comparison_url(area), f'Open {area["name"]} in the comparison', 'discovery-cta') + '</p>' + map_svg(area, geography)
        if area.get('regionId') in by_id:
            region = by_id[area['regionId']]
            body += '<p>Regional context: ' + link(area_route(region), region['name']) + '.</p>'
        if area.get('quality'):
            body += section('Area coverage and interpretation', note_list(area['quality']))
        body += section('Recorded crime by type', area_metric_table(area, categories))
        body += '<p class="discovery-note">Rates use the stated denominator for each measure. Main groups, detailed components and weapon collections overlap. Unavailable values and suppressed changes are not zero. These figures do not measure personal safety.</p>'
        history = metric.get('history', [])
        if history:
            rows = ''.join(f'<tr><th scope="row">{readable_date(p["periodEnd"])}</th><td>{number(p.get("count"))}</td><td>{esc(rate(p, total, area))}</td></tr>' for p in history)
            body += section('All recorded crime: published history', '<div class="discovery-table-wrapper"><table class="discovery-table"><caption>Each row is a rolling 12-month total, not the offences in a single quarter.</caption><thead><tr><th scope="col">Year ending</th><th scope="col">Recorded offences</th><th scope="col">Rate</th></tr></thead><tbody>' + rows + '</tbody></table></div>')
        if area['type'] == 'region':
            children = [row for row in areas if row.get('regionId') == area['id']]
            body += section('Police force areas in this region', '<ul class="discovery-list">' + ''.join(f'<li>{link(area_route(row), row["name"])}</li>' for row in sorted(children, key=lambda row: row['name'].casefold())) + '</ul>')
        monthly_area = monthly_areas.get(area['id'])
        if monthly and monthly_area:
            current = monthly_area.get('metrics', {}).get('all-crime', {})
            mc = monthly['coverage']
            mb = f'<p>Separate provisional Police.uk record for the rolling year {readable_date(mc["start"])} to {readable_date(mc["end"])}; archive published {readable_date(mc["sourcePublishedAt"])}.</p>'
            if monthly_area.get('monthlyCoverage', {}).get('currentComplete') is False:
                mb += '<p class="discovery-note">The latest rolling year is incomplete. Its count, rate and ranking are unavailable; missing submissions never become zero.</p>'
            else:
                mb += f'<p>Recorded offences: <strong>{number(current.get("count"))}</strong>. Resident rate: <strong>{esc(rate(current, total, monthly_area))}</strong>.</p>'
            mb += '<p>Monthly mapping categories and coverage differ from the official series. Do not splice these totals into the official history.</p>'
            mb += '<p>' + link(comparison_url(area, monthly=True), 'Open the separate monthly comparison') + '</p>'
            body += section('Separate monthly update', mb)
        body += section('Official evidence', source_links(data['sources']) + link('/methodology/', 'How to read these figures'))
        add(area_route(area), title, description, 'area', body, home_crumb + [('Areas', '/areas/'), (area['name'], area_route(area))])

    body = hero('Choose one measure', 'Crime types and definitions', 'Main groups, their detailed components and separate weapon collections overlap. Compare one measure at a time.') + dates
    groups = list(dict.fromkeys(category.get('group', 'Crime measures') for category in categories))
    for group in groups:
        cards = ''.join(f'<li class="discovery-card"><h3>{link(crime_route(c), c["label"])}</h3><p>Rates per {c.get("ratePer", 1000):,} residents.</p><p>{esc(c.get("description", ""))}</p></li>' for c in categories if c.get('group', 'Crime measures') == group)
        body += section(group, '<ul class="discovery-grid">' + cards + '</ul>')
    add('/crime/', 'Crime types and definitions — CrimeLedger', 'Explore official crime measures, definitions, resident-rate denominators and overlap warnings for England and Wales.', 'crime-directory', body, home_crumb + [('Crime types', '/crime/')])

    for category in categories:
        description = f'{category["label"]} in England and Wales: definition, official area counts and rates per {category.get("ratePer", 1000):,} residents, with dated sources and limitations.'
        body = hero(category.get('group', 'Crime measure'), category['label'], category.get('description', description)) + dates
        body += '<p>' + link(comparison_url(category=category['id']), f'Compare {category["label"].lower()} interactively', 'discovery-cta') + '</p>'
        if national:
            metric = national.get('metrics', {}).get(category['id'], {})
            body += section('England and Wales reference', '<dl class="discovery-stats">' + stat('Recorded offences', number(metric.get('count'))) + stat('Resident-population rate', rate(metric, category, national)) + '</dl>' + ('<p>The national reference includes British Transport Police. Territorial force and regional totals exclude it.</p>' if category.get('nationalIncludesBtp', True) else '<p>This national firearm reference excludes British Transport Police.</p>'))
        for kind, heading in [('force', 'Police force areas'), ('region', 'Regions and Wales')]:
            body += section(heading, metric_table([area for area in areas if area['type'] == kind], category))
        body += '<p class="discovery-note">Areas are alphabetical. Counts cover the stated rolling year. Rates are unavailable where resident-population comparison is unsuitable; published percentage-change suppressions are retained. Categories overlap and must not be summed.</p>'
        if category['id'] in {'knife-enabled', 'firearms'}:
            body += section('Weapon-collection history', '<p>These are separate collections which overlap other offence groups. Published annual observations and the latest equivalent rolling years retain their actual dates; no intervening quarters are invented. Open an area comparison for its dated history and recording caveats.</p>')
        body += section('Notes and official sources', note_list(data.get('notes', [])) + source_links(data['sources']))
        add(crime_route(category), f'{category["label"]} statistics — CrimeLedger', description, 'crime', body, home_crumb + [('Crime types', '/crime/'), (category['label'], crime_route(category))])

    body = hero('Behind the numbers', 'How the crime comparisons work', 'One measure, one period and a clear view of what recorded crime can and cannot tell you.') + dates
    body += section('The official series', note_list(data.get('methodology', [])))
    body += section('Rates, coverage and overlap', '<p>A rate divides offences by the resident population, then multiplies by 1,000 or 100,000 as stated. Regional rates divide total offences by total residents; they are not the average of force rates. Visitors and commuters can affect comparisons. The City of London remains visible by count but is not ranked by resident rate.</p>' + note_list(data.get('notes', [])))
    if monthly:
        body += section('The separate monthly series', note_list(monthly.get('notes', [])))
    body += '<p>' + link('/sources/', 'Inspect the sources and downloadable data', 'discovery-cta') + '</p>'
    add('/methodology/', 'Crime comparison methodology — CrimeLedger', 'Understand police-recorded crime, population-adjusted rates, suppressed values, quarterly and monthly coverage, and limits on regional comparisons.', 'methodology', body, home_crumb + [('Methodology', '/methodology/')])

    body = hero('The evidence', 'Official sources and public data', 'Go from each published comparison to the source release, population denominator and reusable snapshot.') + dates
    body += section('Official quarterly statistics', source_links(data['sources']) + '<p>' + link('/data/crime.json', 'Download the dated official JSON') + ' · ' + link('/data/source-manifest.json', 'Official source manifest') + '</p>')
    if monthly:
        body += section('Separate provisional monthly record', '<p>Police.uk mapping data is a different series, with separate categories and submission gaps.</p>' + source_links(monthly['sources']) + '<p>' + link('/data/monthly.json', 'Download the monthly JSON') + ' · ' + link('/data/monthly-manifest.json', 'Monthly source manifest') + '</p>')
    body += section('Geography and reuse', '<p>' + link('/data/geography-sources.json', 'ONS boundary attribution') + ' · ' + link('https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/', 'Open Government Licence v3.0') + '</p><p>New source checks do not change a figure’s observation period. Revisions can alter older observations; each public snapshot retains its source evidence. These pages cover England and Wales, not a harmonised UK league table.</p>')
    add('/sources/', 'Crime statistics sources and downloads — CrimeLedger', 'Read the ONS, Home Office and Police.uk sources behind CrimeLedger, with public JSON, source manifests, geography attribution and licensing.', 'sources', body, home_crumb + [('Sources', '/sources/')])

    privacy = (public_dir / 'privacy/index.html').read_text(encoding='utf-8')
    title = re.search(r'<title>(.*?)</title>', privacy, re.S | re.I)
    description = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', privacy, re.I)
    main = re.search(r'<main\b[^>]*>(.*?)</main>', privacy, re.S | re.I)
    if not all([title, description, main]):
        raise ValueError('Privacy source lacks title, description or main content')
    pages['/privacy/'] = Page('/privacy/', html.unescape(title.group(1)), html.unescape(description.group(1)), 'privacy', main.group(1), tuple(home_crumb + [('Privacy', '/privacy/')]))
    return pages


def manifest_for(pages, previous=None, today=None):
    previous = previous or {}
    if previous and previous.get('schemaVersion') != SCHEMA:
        raise ValueError('Unsupported discovery manifest schema')
    today = today or date.today()
    records = {}
    for route, page in sorted(pages.items()):
        old = previous.get('pages', {}).get(route, {})
        lastmod = old.get('lastmod') if old.get('contentSha256') == page.content_hash else today.isoformat()
        if iso_day(lastmod) > today:
            raise ValueError('Discovery modification date is in the future')
        records[route] = {'path': route_file(route), 'title': page.title, 'description': page.description,
                          'kind': page.kind, 'contentSha256': page.content_hash, 'lastmod': lastmod}
    manifest = {'schemaVersion': SCHEMA, 'baseUrl': BASE, 'pages': records}
    manifest['sitemapSha256'] = sha256(sitemap_bytes(manifest))
    return manifest


def sitemap_bytes(manifest):
    rows = ''.join(f'<url><loc>{BASE}{esc(route)}</loc><lastmod>{esc(row["lastmod"])}</lastmod></url>\n' for route, row in sorted(manifest['pages'].items()))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '</urlset>\n').encode('utf-8')


def metadata(page, lastmod):
    url = BASE + page.route
    structured = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'WebSite', '@id': BASE + '/#website', 'url': BASE + '/',
         'name': 'CrimeLedger', 'description': 'Police-recorded crime comparisons for England and Wales, with official sources, population rates and trends.',
         'inLanguage': 'en-GB', 'publisher': {'@id': BASE + '/#publisher'}},
        {'@type': 'Organization', '@id': BASE + '/#publisher', 'name': 'DoubleTick Solutions Ltd', 'url': BASE + '/'},
        {'@type': 'WebPage', '@id': url + '#webpage', 'url': url, 'name': page.title,
         'description': page.description, 'inLanguage': 'en-GB', 'dateModified': lastmod,
         'isPartOf': {'@id': BASE + '/#website'}, 'publisher': {'@id': BASE + '/#publisher'},
         'breadcrumb': {'@id': url + '#breadcrumbs'}},
        {'@type': 'BreadcrumbList', '@id': url + '#breadcrumbs', 'itemListElement': [
            {'@type': 'ListItem', 'position': index, 'name': label, 'item': BASE + route}
            for index, (label, route) in enumerate(page.breadcrumbs, 1)]}]}
    encoded = json.dumps(structured, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    tags = [f'<title>{esc(page.title)}</title>', f'<meta name="description" content="{esc(page.description)}">',
            f'<link rel="canonical" href="{esc(url)}">', '<meta name="robots" content="index,follow,max-image-preview:large">']
    for name, value in [('type', 'website'), ('url', url), ('site_name', 'CrimeLedger'), ('title', page.title), ('description', page.description), ('image', BASE + '/social-card.png'), ('image:width', '1200'), ('image:height', '630'), ('image:alt', 'CrimeLedger — compare the public crime record')]:
        tags.append(f'<meta property="og:{name}" content="{esc(value)}">')
    for name, value in [('card', 'summary_large_image'), ('title', page.title), ('description', page.description), ('image', BASE + '/social-card.png'), ('image:alt', 'CrimeLedger — compare the public crime record')]:
        tags.append(f'<meta name="twitter:{name}" content="{esc(value)}">')
    tags.append(f'<script type="application/ld+json">{encoded}</script>')
    return '\n'.join(tags)


def with_metadata(shell, page, lastmod):
    block_pattern = re.escape(META_START) + r'.*?' + re.escape(META_END)
    if re.search(block_pattern, shell, re.S):
        return re.sub(block_pattern, lambda _: META_START + '\n' + metadata(page, lastmod) + '\n' + META_END, shell, flags=re.S)
    shell = re.sub(r'<title>.*?</title>', '', shell, flags=re.S | re.I)
    shell = re.sub(r'<meta\b[^>]*(?:name|property)=["\'](?:description|robots|og:[^"\']+|twitter:[^"\']+)["\'][^>]*>', '', shell, flags=re.I)
    shell = re.sub(r'<link\b[^>]*rel=["\']canonical["\'][^>]*>', '', shell, flags=re.I)
    shell = re.sub(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>', '', shell, flags=re.S | re.I)
    if shell.lower().count('</head>') != 1:
        raise ValueError('Expected exactly one HTML head')
    return re.sub(r'</head>', lambda _: META_START + '\n' + metadata(page, lastmod) + '\n' + META_END + '\n</head>', shell, flags=re.I)


def main_html(page):
    snapshot = f' data-snapshot-end="{esc(page.snapshot_end)}"' if page.snapshot_end else ''
    return f'<main class="discovery-main" data-discovery-page="{esc(page.route)}"{snapshot}>' + page.body + '</main>'


def standalone(page, lastmod):
    nav = ''.join(link(route, label) for route, label in [('/#comparison', 'Comparison'), ('/areas/', 'Areas'), ('/crime/', 'Crime types'), ('/methodology/', 'Methodology'), ('/sources/', 'Sources')])
    crumbs = '<nav class="discovery-breadcrumbs" aria-label="Breadcrumb">' + ' / '.join(link(route, label) for label, route in page.breadcrumbs) + '</nav>'
    return ('<!doctype html>\n<html lang="en-GB"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n' + metadata(page, lastmod) + '\n<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/discovery.css"></head>\n'
            '<body class="discovery-page"><header class="discovery-header">' + link('/', 'CrimeLedger.', 'discovery-brand') + '<nav class="discovery-nav" aria-label="Main navigation">' + nav + '</nav></header>' + crumbs + main_html(page) + '<footer class="discovery-footer"><p>CrimeLedger — clear comparisons of the public record.</p><p>' + link('/privacy/', 'Privacy and analytics choices') + ' · ' + link('https://politicians.compare', 'politicians.compare') + '</p><p>Contains public sector information licensed under the Open Government Licence v3.0.</p></footer></body></html>\n').encode('utf-8')


def root_html(shell, page, lastmod):
    if shell.count(ROOT_START) != 1 or shell.count(ROOT_END) != 1:
        raise ValueError('Vite index must contain exactly one discovery-root marker pair')
    start, end = shell.index(ROOT_START), shell.index(ROOT_END)
    if start >= end:
        raise ValueError('Discovery-root markers are out of order')
    fallback = main_html(page).replace('class="discovery-main"', 'class="discovery-main discovery-fallback"', 1)
    shell = shell[:start + len(ROOT_START)] + fallback + shell[end:]
    return with_metadata(shell, page, lastmod).encode('utf-8')


def checked_manifest(public_dir=DEFAULT_PUBLIC):
    public_dir = Path(public_dir)
    path = public_dir / MANIFEST
    if not path.is_file():
        raise ValueError('Discovery manifest missing; run --write-manifest')
    committed = read_json(path)
    pages = make_pages(public_dir)
    expected = manifest_for(pages, committed)
    if committed != expected or path.read_bytes() != json_bytes(expected):
        raise ValueError('Discovery manifest is stale or altered; run --write-manifest and review the change')
    return pages, expected


def safe_output_path(output, relative):
    output = Path(output).resolve()
    path = output / relative
    try:
        path.resolve().relative_to(output)
    except ValueError as error:
        raise ValueError('Generated path escapes output directory') from error
    current = path
    while current != output:
        if current.is_symlink():
            raise ValueError('Generated output cannot traverse symlinks')
        current = current.parent
    return path


def validate(output=None, public_dir=DEFAULT_PUBLIC):
    pages, manifest = checked_manifest(public_dir)
    if output is None:
        return manifest
    output, public_dir = Path(output), Path(public_dir)
    for relative, expected in [('sitemap.xml', sitemap_bytes(manifest)), (MANIFEST, json_bytes(manifest))]:
        path = safe_output_path(output, relative)
        if not path.is_file() or path.read_bytes() != expected:
            raise ValueError(f'Stale or altered discovery output: {relative}')
    for route, page in pages.items():
        relative = route_file(route)
        path = safe_output_path(output, relative)
        if not path.is_file():
            raise ValueError(f'Missing discovery output: {relative}')
        actual = path.read_bytes()
        if route == '/':
            expected = root_html(actual.decode('utf-8'), page, manifest['pages'][route]['lastmod'])
        elif route == '/privacy/':
            expected = with_metadata((public_dir / relative).read_text(encoding='utf-8'), page, manifest['pages'][route]['lastmod']).encode('utf-8')
        else:
            expected = standalone(page, manifest['pages'][route]['lastmod'])
        if actual != expected:
            raise ValueError(f'Stale or altered discovery output: {relative}')
    actual_paths = {str(path.relative_to(output)) for path in output.rglob('index.html') if is_owned_path(str(path.relative_to(output)))}
    if actual_paths != {route_file(route) for route in pages}:
        raise ValueError('Unexpected obsolete discovery pages in output')
    return manifest


def build(output, public_dir=DEFAULT_PUBLIC):
    pages, manifest = checked_manifest(public_dir)
    output, public_dir = Path(output), Path(public_dir)
    index_path = safe_output_path(output, 'index.html')
    if not index_path.is_file():
        raise ValueError('Build Vite before generating discovery pages')
    shell = index_path.read_text(encoding='utf-8')
    rendered = {}
    for route, page in pages.items():
        lastmod = manifest['pages'][route]['lastmod']
        if route == '/':
            rendered['index.html'] = root_html(shell, page, lastmod)
        elif route == '/privacy/':
            rendered[route_file(route)] = with_metadata((public_dir / route_file(route)).read_text(encoding='utf-8'), page, lastmod).encode('utf-8')
        else:
            rendered[route_file(route)] = standalone(page, lastmod)
    rendered['sitemap.xml'] = sitemap_bytes(manifest)
    rendered[MANIFEST] = json_bytes(manifest)
    # Validate every destination before writing or cleaning any generated file.
    for relative in rendered:
        safe_output_path(output, relative)
    obsolete = [path for path in output.rglob('index.html') if is_owned_path(str(path.relative_to(output))) and str(path.relative_to(output)) not in rendered]
    for path in obsolete:
        safe_output_path(output, str(path.relative_to(output)))
    for path in obsolete:
        path.unlink()
    for relative, value in rendered.items():
        path = safe_output_path(output, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    validate(output, public_dir)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-dir', type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument('--output', type=Path, help='Existing Vite output directory; omitted checks need no dist')
    parser.add_argument('--write-manifest', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not (args.write_manifest or args.check or args.output):
        parser.error('Choose --write-manifest, --check or --output dist')
    try:
        if args.write_manifest:
            path = args.public_dir / MANIFEST
            previous = read_json(path) if path.is_file() else {}
            path.write_bytes(json_bytes(manifest_for(make_pages(args.public_dir), previous)))
        if args.check:
            manifest = validate(args.output, args.public_dir)
        elif args.output:
            manifest = build(args.output, args.public_dir)
        else:
            manifest = validate(None, args.public_dir)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Discovery generation failed: {error}\n')
    print(f'Discovery {"verified" if args.check else "built" if args.output else "manifest written"}: {len(manifest["pages"])} URLs')


if __name__ == '__main__':
    main()
