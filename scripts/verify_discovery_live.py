#!/usr/bin/env python3
"""Read-only checks of published discovery pages against a verified static build.

HTML is compared semantically because Cloudflare rewrites contact email links.
The manifest and social image are compared byte for byte; sitemap XML permits
insignificant whitespace only. No JavaScript is executed or analytics sent.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import struct
import time
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BASE = "https://crime.compare"
MANIFEST = "discovery-manifest.json"
SCHEMA = "crime-compare-discovery-1.0.0"
MAX_BYTES = 3_000_000
CF_EMAIL_SCRIPT = re.compile(r"^/cdn-cgi/scripts/[A-Za-z0-9]+/cloudflare-static/email-decode\.min\.js$")


class VerificationError(ValueError):
    """The public response cannot be reconciled with the candidate build."""


def compact(value: str) -> str:
    return " ".join(value.split())


def decode_cf_email(value: str) -> str:
    try:
        raw = bytes.fromhex(value)
        if len(raw) < 2:
            raise ValueError
        return bytes(part ^ raw[0] for part in raw[1:]).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise VerificationError("Invalid Cloudflare email protection markup") from exc


def normalise_href(value: str) -> str:
    prefix = "/cdn-cgi/l/email-protection#"
    return "mailto:" + decode_cf_email(value[len(prefix):]) if value.startswith(prefix) else value


class Page(HTMLParser):
    """The public facts, metadata and links that must survive CDN transforms."""

    def __init__(self, raw: bytes):
        super().__init__(convert_charrefs=True)
        self.titles: list[str] = []
        self.canonicals: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.links: list[str] = []
        self.images: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.structured: list[object] = []
        self.markers: list[tuple[str, str | None]] = []
        self.text: list[str] = []
        self.unsafe: list[str] = []
        self._title: list[str] | None = None
        self._script: list[str] | None = None
        self._script_type = ""
        self._body = False
        self._head = False
        self._ignored: list[str] = []
        self._cf_depth = 0
        try:
            self.feed(raw.decode("utf-8"))
            self.close()
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VerificationError("Invalid UTF-8 HTML or JSON-LD") from exc

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for key, value in attrs:
            if key.lower().startswith("on") or (value and re.match(r"\s*(?:javascript|vbscript):", value, re.I)):
                self.unsafe.append(key)
        if self._cf_depth:
            self._cf_depth += 1
        elif tag == "span" and "__cf_email__" in (values.get("class") or "").split():
            self.text.append(decode_cf_email(values.get("data-cfemail") or ""))
            self._cf_depth = 1
        if tag == "body":
            self._body = True
        if tag == "head":
            self._head = True
        if tag == "title" and self._head:
            self._title = []
        if tag == "meta":
            key = values.get("name") or values.get("property")
            if key:
                self.meta.setdefault(key.lower(), []).append(values.get("content") or "")
        if tag == "link" and "canonical" in (values.get("rel") or "").lower().split():
            self.canonicals.append(values.get("href") or "")
        if tag == "a":
            self.links.append(normalise_href(values.get("href") or ""))
        if tag == "img":
            self.images.append((values.get("src") or "", values.get("alt") or ""))
        if values.get("data-discovery-page") is not None:
            self.markers.append((values["data-discovery-page"] or "", values.get("data-snapshot-end")))
        if tag == "script":
            self._script = []
            self._script_type = (values.get("type") or "").lower()
            if values.get("src"):
                self.scripts.append(values["src"] or "")
            self._ignored.append(tag)
        elif tag in {"style", "template"}:
            self._ignored.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        # HTML void elements do not have matching end tags.
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title is not None:
            self.titles.append(compact("".join(self._title)))
            self._title = None
        if tag == "script" and self._script is not None:
            source = "".join(self._script).strip()
            if self._script_type == "application/ld+json":
                self.structured.append(json.loads(source))
            elif source:
                self.unsafe.append("inline executable script")
            self._script = None
        if self._ignored and tag == self._ignored[-1]:
            self._ignored.pop()
        if tag == "body":
            self._body = False
        if tag == "head":
            self._head = False
        if self._cf_depth:
            self._cf_depth -= 1

    def handle_data(self, value: str) -> None:
        if self._title is not None:
            self._title.append(value)
        if self._script is not None:
            self._script.append(value)
        if self._body and not self._ignored and not self._cf_depth:
            self.text.append(value)

    @property
    def visible_text(self) -> str:
        return compact(" ".join(self.text))


def one(page: Page, name: str) -> str:
    values = page.meta.get(name, [])
    if len(values) != 1 or not values[0].strip():
        raise VerificationError(f"Expected one nonempty {name} tag")
    return values[0]


def canonical_url(value: str, *, origin: str = BASE) -> str:
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != urlsplit(origin).netloc or parsed.query or parsed.fragment or parsed.username:
        raise VerificationError(f"Unsafe or noncanonical metadata URL: {value}")
    return value


def validate_jsonld(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            validate_jsonld(item)
    elif isinstance(value, list):
        for item in value:
            validate_jsonld(item)
    elif isinstance(value, str):
        if re.match(r"\s*(?:javascript|vbscript):", value, re.I):
            raise VerificationError("Unsafe JSON-LD URL")
        if value.startswith(("http://", "https://")) and urlsplit(value).query:
            raise VerificationError("JSON-LD contains a query URL")


def validate_page(page: Page, route: str, record: dict) -> None:
    if page.unsafe:
        raise VerificationError(f"{route}: unsafe HTML: {page.unsafe[0]}")
    if len(page.titles) != 1 or not page.titles[0] or str(record["title"]) not in page.titles[0]:
        raise VerificationError(f"{route}: missing or incorrect title")
    if page.canonicals != [BASE + route]:
        raise VerificationError(f"{route}: missing, duplicate or incorrect canonical URL")
    canonical_url(page.canonicals[0])
    if one(page, "description") != record["description"]:
        raise VerificationError(f"{route}: description differs from discovery manifest")
    if one(page, "og:url") != BASE + route:
        raise VerificationError(f"{route}: incorrect Open Graph URL")
    for name in ["og:title", "og:description", "og:type", "og:image", "twitter:card"]:
        one(page, name)
    canonical_url(one(page, "og:image"))
    if "twitter:image" in page.meta and one(page, "twitter:image") != one(page, "og:image"):
        raise VerificationError(f"{route}: social image tags disagree")
    for name in ["robots", "googlebot", "bingbot"]:
        if any(re.search(r"(?:^|[\s,])(?:noindex|none)(?:$|[\s,])", item, re.I) for item in page.meta.get(name, [])):
            raise VerificationError(f"{route}: discovery page is marked noindex")
    if not page.structured:
        raise VerificationError(f"{route}: missing JSON-LD")
    for value in page.structured:
        validate_jsonld(value)
    if not page.visible_text:
        raise VerificationError(f"{route}: missing visible initial HTML")
    if route != "/privacy/":
        if len(page.markers) != 1 or page.markers[0][0] != route or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", page.markers[0][1] or ""):
            raise VerificationError(f"{route}: missing or incorrect snapshot marker")


def compare_pages(expected: Page, actual: Page, route: str, record: dict) -> None:
    validate_page(actual, route, record)
    for name in ["titles", "canonicals", "meta", "structured", "markers", "links", "images", "visible_text"]:
        if getattr(expected, name) != getattr(actual, name):
            raise VerificationError(f"{route}: published {name} differs from the verified build")
    actual_scripts = [source for source in actual.scripts if not CF_EMAIL_SCRIPT.fullmatch(source)]
    if actual_scripts != expected.scripts:
        raise VerificationError(f"{route}: unexpected published script")


def sitemap_records(raw: bytes) -> list[tuple[str, str | None]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise VerificationError("Invalid sitemap XML") from exc
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag != namespace + "urlset":
        raise VerificationError("Invalid sitemap root")
    rows = []
    for element in root:
        if element.tag != namespace + "url" or len(element.findall(namespace + "loc")) != 1:
            raise VerificationError("Invalid sitemap URL entry")
        if any(child.tag not in {namespace + "loc", namespace + "lastmod"} for child in element) or len(element.findall(namespace + "lastmod")) > 1:
            raise VerificationError("Unexpected sitemap fields")
        location = (element.findtext(namespace + "loc") or "").strip()
        canonical_url(location)
        lastmod = element.findtext(namespace + "lastmod")
        rows.append((location, lastmod.strip() if lastmod else None))
    if len(rows) != len(set(location for location, _ in rows)):
        raise VerificationError("Duplicate sitemap URL")
    return rows


def safe_file(site: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise VerificationError("Unsafe discovery file path")
    candidate = (site / relative).resolve()
    if not candidate.is_relative_to(site.resolve()) or not candidate.is_file():
        raise VerificationError("Missing or unsafe discovery file")
    return candidate


@dataclass(frozen=True)
class Response:
    url: str
    body: bytes
    headers: dict[str, str]
    status: int = 200


def fetch(url: str) -> Response:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 CrimeCompareDiscoveryVerification/1.0", "Cache-Control": "no-cache", "Accept-Encoding": "identity"})
    with urlopen(request, timeout=30) as result:
        raw = result.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise VerificationError("Published response exceeds verification size limit")
        return Response(result.url, raw, {key.lower(): value for key, value in result.headers.items()}, result.status)


def response(fetcher: Callable[[str], Response], origin: str, route: str, content_type: str) -> Response:
    result = fetcher(origin + route)
    expected = urlsplit(origin + route)
    actual = urlsplit(result.url)
    if result.status != 200 or (actual.scheme, actual.netloc, actual.path) != (expected.scheme, expected.netloc, expected.path) or actual.query or actual.fragment:
        raise VerificationError(f"{route}: unsuccessful response or unexpected redirect")
    received_type = result.headers.get("content-type", "").lower().split(";", 1)[0].strip()
    allowed_types = {"application/xml", "text/xml"} if content_type == "xml" else {content_type}
    if received_type not in allowed_types:
        raise VerificationError(f"{route}: incorrect Content-Type")
    # Pages previews may add noindex at the CDN; production must remain indexable.
    if urlsplit(origin).hostname in {"crime.compare", "www.crime.compare"} and re.search(r"\b(?:noindex|none)\b", result.headers.get("x-robots-tag", ""), re.I):
        raise VerificationError(f"{route}: production X-Robots-Tag prevents indexing")
    return result


def load_candidate(site: Path) -> tuple[dict, dict[str, Page]]:
    manifest = json.loads((site / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != SCHEMA or manifest.get("baseUrl") != BASE or not isinstance(manifest.get("pages"), dict):
        raise VerificationError("Invalid discovery manifest schema or canonical origin")
    pages = {}
    titles = set()
    for route, record in manifest["pages"].items():
        if not re.fullmatch(r"/(?:[A-Za-z0-9-]+/)*", route) or not isinstance(record, dict):
            raise VerificationError("Unsafe discovery route or page record")
        page = Page(safe_file(site, record["path"]).read_bytes())
        validate_page(page, route, record)
        if page.titles[0] in titles:
            raise VerificationError("Duplicate discovery page title")
        titles.add(page.titles[0])
        pages[route] = page
    sitemap = (site / "sitemap.xml").read_bytes()
    if hashlib.sha256(sitemap).hexdigest() != manifest.get("sitemapSha256"):
        raise VerificationError("Local sitemap hash differs from discovery manifest")
    rows = sitemap_records(sitemap)
    expected_rows = {(BASE + route, record["lastmod"]) for route, record in manifest["pages"].items()}
    if set(rows) != expected_rows:
        raise VerificationError("Sitemap and discovery manifest page sets/dates disagree")
    return manifest, pages


def representative_routes(pages: dict[str, Page], all_pages: bool) -> list[str]:
    required = ["/", "/areas/", "/crime/", "/methodology/", "/sources/", "/privacy/"]
    for prefix in ["/areas/", "/crime/"]:
        candidates = sorted(route for route in pages if route.startswith(prefix) and route != prefix)
        if not candidates:
            raise VerificationError(f"Missing {prefix} detail pages")
        required.append(candidates[0])
    if any(route not in pages for route in required):
        raise VerificationError("Required discovery directory/reference page missing")
    return sorted(pages) if all_pages else required


def verify(site: Path, *, base_url: str = BASE, all_pages: bool = False, fetcher: Callable[[str], Response] = fetch) -> dict[str, int]:
    origin = base_url.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment or parsed.username or not parsed.hostname or (parsed.netloc not in {"crime.compare", "www.crime.compare", "crime-compare.pages.dev"} and not parsed.hostname.endswith(".crime-compare.pages.dev")):
        raise VerificationError("Verification origin must be HTTPS crime.compare or its Cloudflare Pages deployment")
    manifest, pages = load_candidate(site)
    remote_manifest = response(fetcher, origin, "/" + MANIFEST, "application/json").body
    if remote_manifest != (site / MANIFEST).read_bytes():
        raise VerificationError("Published discovery manifest differs from the verified build")
    remote_sitemap = response(fetcher, origin, "/sitemap.xml", "xml").body
    if sitemap_records(remote_sitemap) != sitemap_records((site / "sitemap.xml").read_bytes()):
        raise VerificationError("Published sitemap differs from the verified build")
    selected = representative_routes(pages, all_pages)
    def check(route: str) -> set[str]:
        actual = Page(response(fetcher, origin, route, "text/html").body)
        compare_pages(pages[route], actual, route, manifest["pages"][route])
        return {one(actual, "og:image")}
    with ThreadPoolExecutor(max_workers=6) as pool:
        images = set().union(*pool.map(check, selected))
    for image in sorted(images):
        path = urlsplit(canonical_url(image)).path
        expected = safe_file(site, path.lstrip("/")).read_bytes()
        if len(expected) < 24 or expected[:8] != b"\x89PNG\r\n\x1a\n" or expected[12:16] != b"IHDR" or struct.unpack(">II", expected[16:24]) != (1200, 630):
            raise VerificationError("Social image must be a 1200 by 630 PNG")
        received = response(fetcher, origin, path, "image/png").body
        if received != expected:
            raise VerificationError("Published social image differs from the verified build")
    return {"manifestPages": len(pages), "verifiedPages": len(selected), "socialImages": len(images)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", "--output", type=Path, default=Path("dist"))
    parser.add_argument("--base-url", "--origin", default=BASE, help="production origin or exact HTTPS Cloudflare deployment URL; canonical metadata remains crime.compare")
    parser.add_argument("--all", action="store_true", dest="all_pages", help="check every sitemap HTML page instead of representative pages")
    parser.add_argument("--attempts", type=int, choices=range(1, 7), default=3)
    args = parser.parse_args()
    # Reproduce source-bound semantic output before making any network request.
    from build_discovery_pages import validate
    try:
        validate(args.site_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit(f"Discovery candidate validation failed: {exc}") from None
    for attempt in range(args.attempts):
        try:
            result = verify(args.site_dir, base_url=args.base_url, all_pages=args.all_pages)
            print(f"Discovery verified: {result['verifiedPages']} HTML pages, {result['manifestPages']} sitemap/manifest records and {result['socialImages']} social image(s)")
            return
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if attempt + 1 == args.attempts:
                raise SystemExit(f"Discovery verification failed: {exc}") from None
            time.sleep(5)


if __name__ == "__main__":
    main()
