#!/usr/bin/env python3
"""Build an optional, separate monthly Police.uk provisional comparison.

Uses only the Python standard library. The first run downloads the current
Police.uk rolling archive (~1.7GB); it is cached outside the published site.
Only the most recent 24 months of England/Wales territorial-force street CSVs
are parsed. Official quarterly crime.json is never modified by this script.
"""
from __future__ import annotations

import argparse
import calendar
import collections
import copy
import datetime as dt
import email.utils
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.request
import zipfile
import csv


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "data"
CACHE = ROOT / ".cache" / "monthly"
API = "https://data.police.uk/api/crime-last-updated"
ARCHIVE = "https://data.police.uk/data/archive/latest.zip"
CHANGELOG = "https://data.police.uk/changelog/"
ABOUT = "https://data.police.uk/about/"
CITY = "E23000034"
NATION = "K04000001"
USER_AGENT = "CrimeCompare/1.0 (public Police.uk statistics; monthly refresh)"

FORCES = {
    "metropolitan": "E23000001", "cumbria": "E23000002", "lancashire": "E23000003",
    "merseyside": "E23000004", "greater-manchester": "E23000005", "cheshire": "E23000006",
    "northumbria": "E23000007", "durham": "E23000008", "north-yorkshire": "E23000009",
    "west-yorkshire": "E23000010", "south-yorkshire": "E23000011", "humberside": "E23000012",
    "cleveland": "E23000013", "west-midlands": "E23000014", "staffordshire": "E23000015",
    "west-mercia": "E23000016", "warwickshire": "E23000017", "derbyshire": "E23000018",
    "nottinghamshire": "E23000019", "lincolnshire": "E23000020", "leicestershire": "E23000021",
    "northamptonshire": "E23000022", "cambridgeshire": "E23000023", "norfolk": "E23000024",
    "suffolk": "E23000025", "bedfordshire": "E23000026", "hertfordshire": "E23000027",
    "essex": "E23000028", "thames-valley": "E23000029", "hampshire": "E23000030",
    "surrey": "E23000031", "kent": "E23000032", "sussex": "E23000033",
    "city-of-london": CITY, "devon-and-cornwall": "E23000035", "avon-and-somerset": "E23000036",
    "gloucestershire": "E23000037", "wiltshire": "E23000038", "dorset": "E23000039",
    "north-wales": "W15000001", "gwent": "W15000002", "south-wales": "W15000003",
    "dyfed-powys": "W15000004",
}
# Monthly labels deliberately follow Police.uk's broader categories. In
# particular, violence and sexual offences cannot be separated in this feed.
CATEGORY_ROWS = [
    ("violence-sexual-offences", "Violence and sexual offences", "Violence and sexual offences"),
    ("robbery", "Robbery", "Robbery"),
    ("burglary", "Burglary", "Burglary"),
    ("vehicle-crime", "Vehicle crime", "Vehicle crime"),
    ("theft-from-person", "Theft from the person", "Theft from the person"),
    ("shoplifting", "Shoplifting", "Shoplifting"),
    ("bicycle-theft", "Bicycle theft", "Bicycle theft"),
    ("other-theft", "Other theft", "Other theft"),
    ("criminal-damage", "Criminal damage and arson", "Criminal damage and arson"),
    ("drug-offences", "Drug offences", "Drugs"),
    ("weapons", "Possession of weapons", "Possession of weapons"),
    ("public-order", "Public order", "Public order"),
    ("other-crime", "Other crime", "Other crime"),
]
CATEGORIES = [{"id": "all-crime", "label": "All recorded crime", "description": "All crime records in the Police.uk monthly street-data feed, excluding anti-social behaviour incidents. Fraud is not supplied in this feed. This provisional series differs from the official quarterly statistics."}] + [
    {"id": code, "label": label, "description": (
        "Police.uk combines violence and sexual offences into one monthly category. It is not directly interchangeable with either separate official quarterly category."
        if code == "violence-sexual-offences" else
        "Police.uk monthly street-data category: " + source_label + ". Provisional published records; definitions differ from some official quarterly offence groups."
    )}
    for code, label, source_label in CATEGORY_ROWS
]
for category in CATEGORIES:
    if category["id"] in ("robbery", "shoplifting"):
        category["description"] += " A counting clarification from April 2025 records shop theft involving violence or threats, including during escape, as business robbery; this affects robbery and shoplifting trends."
CATEGORY_MAP = {source.casefold(): code for code, _, source in CATEGORY_ROWS}
CATEGORY_IDS = [c["id"] for c in CATEGORIES]


def open_url(url, method="GET", headers=None):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(request, timeout=90)


def fetch_small(url):
    for attempt in range(4):
        try:
            with open_url(url) as response:
                payload = response.read(2_000_000)
                if len(payload) == 2_000_000:
                    raise ValueError("Metadata response exceeded limit")
                return payload
        except Exception:
            if attempt == 3:
                raise
            time.sleep(min(2 ** attempt, 8))


def month_offset(month, offset):
    year, m = map(int, month[:7].split("-"))
    index = year * 12 + m - 1 + offset
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_end(month):
    year, m = map(int, month.split("-"))
    return dt.date(year, m, calendar.monthrange(year, m)[1]).isoformat()


def hash_archive(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            md5.update(block)
            sha.update(block)
    return md5.hexdigest(), sha.hexdigest()


def discover_archive(latest):
    for attempt in range(4):
        try:
            with open_url(ARCHIVE, method="HEAD") as response:
                url, headers = response.geturl(), dict(response.headers.items())
            lower = {k.lower(): v for k, v in headers.items()}
            archive_month = re.search(r"/(\d{4}-\d{2})\.zip(?:\?|$)", url)
            if not archive_month or archive_month.group(1) != latest:
                raise ValueError(f"Latest archive and API observation month disagree: {url} / {latest}")
            expected_md5 = lower.get("x-amz-meta-md5", "").strip('"').lower()
            if not re.fullmatch(r"[0-9a-f]{32}", expected_md5):
                raise ValueError("Archive lacks its published x-amz-meta-md5 checksum; refusing unverified download")
            size = int(lower["content-length"])
            if not 1_000_000 <= size <= 8_000_000_000:
                raise ValueError("Unexpected archive size")
            published = email.utils.parsedate_to_datetime(lower["last-modified"]).date().isoformat()
            return {"url": url, "bytes": size, "md5": expected_md5, "etag": lower.get("etag"),
                    "publishedAt": published, "latestMonth": latest,
                    "checksumSource": "Archive response x-amz-meta-md5; Police.uk documents archive MD5 verification at https://data.police.uk/about/#data-verification"}
        except Exception:
            if attempt == 3:
                raise
            time.sleep(min(2 ** attempt, 8))


def download_archive(record):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (record["latestMonth"] + ".zip")
    partial = path.with_suffix(".zip.part")
    # Cached archives are rehashed: a successful earlier run never makes a
    # truncated or externally modified source file trusted.
    if path.exists():
        md5, sha = hash_archive(path)
        if path.stat().st_size == record["bytes"] and md5 == record["md5"]:
            return path, sha
        path.unlink()
    for attempt in range(4):
        try:
            start = partial.stat().st_size if partial.exists() else 0
            if start > record["bytes"]:
                partial.unlink()
                start = 0
            if start < record["bytes"]:
                headers = {"Range": f"bytes={start}-"} if start else {}
                with open_url(record["url"], headers=headers) as response:
                    if start and response.status == 206:
                        if not response.headers.get("Content-Range", "").startswith(f"bytes {start}-"):
                            raise ValueError("Download resumed at an incorrect byte offset")
                        mode = "ab"
                    else:
                        mode, start = "wb", 0
                    with partial.open(mode) as stream:
                        for block in iter(lambda: response.read(1024 * 1024), b""):
                            stream.write(block)
                        stream.flush()
                        os.fsync(stream.fileno())
            if partial.stat().st_size != record["bytes"]:
                raise ValueError("Archive download length does not match the published size")
            md5, sha = hash_archive(partial)
            if md5 != record["md5"]:
                partial.unlink()
                raise ValueError("Archive MD5 does not match Police.uk checksum")
            os.replace(partial, path)
            return path, sha
        except Exception:
            if attempt == 3:
                raise
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError("Could not download archive")


def normalize_force(text):
    return re.sub(r"[^a-z]", "", text.casefold()).replace("and", "")


def parse_archive(path, latest, archive_sha):
    """Return only aggregate counts; never publish individual crime records."""
    count_cache = CACHE / (latest + ".counts.json")
    if count_cache.exists():
        cached = json.loads(count_cache.read_text())
        if cached.get("archiveSha256") == archive_sha and cached.get("parserVersion") == 1:
            return cached
    months = [month_offset(latest, i) for i in range(-23, 1)]
    wanted = set(months)
    counts = {code: {} for code in FORCES.values()}
    entries, total_rows, excluded_asb = [], 0, 0
    seen = set()
    pattern = re.compile(r"^(\d{4}-\d{2})/\1-(.+)-street\.csv$")
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            match = pattern.fullmatch(info.filename)
            if not match or match.group(1) not in wanted:
                continue
            month, slug = match.groups()
            if slug in ("btp", "british-transport", "british-transport-police", "psni", "northern-ireland"):
                continue
            if slug not in FORCES:
                raise ValueError("Unrecognised street-file force: " + slug)
            code = FORCES[slug]
            if (code, month) in seen:
                raise ValueError("Duplicate force-month CSV: " + info.filename)
            seen.add((code, month))
            category_counts = {cat: 0 for cat in CATEGORY_IDS}
            rows = 0
            with archive.open(info) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                reader = csv.DictReader(text)
                if not {"Month", "Reported by", "Crime type"}.issubset(reader.fieldnames or []):
                    raise ValueError("Unsupported monthly CSV columns: " + info.filename)
                for row in reader:
                    rows += 1
                    if row["Month"] != month:
                        raise ValueError("CSV observation month does not match file: " + info.filename)
                    # Police.uk defines both 'Reported by' and currently 'Falls
                    # within' as the reporting force. No coordinates are used.
                    reported = normalize_force(row["Reported by"])
                    if normalize_force(slug) not in reported:
                        raise ValueError("CSV reporting force does not match file: " + info.filename)
                    source_category = row["Crime type"].strip().casefold()
                    if source_category == "anti-social behaviour":
                        excluded_asb += 1
                        continue
                    category = CATEGORY_MAP.get(source_category)
                    if category is None:
                        raise ValueError("Unknown Police.uk crime category: " + row["Crime type"])
                    category_counts[category] += 1
                    category_counts["all-crime"] += 1
            # An empty upload is not evidence of zero crime for a force-month.
            if rows:
                counts[code][month] = category_counts
                entries.append({"name": info.filename, "crc32": f"{info.CRC:08x}", "rows": rows})
                total_rows += rows
    if not entries or not any(latest in force for force in counts.values()):
        raise ValueError("Archive has no usable current England/Wales street-data CSVs")
    result = {"parserVersion": 1, "archiveSha256": archive_sha, "months": months,
              "counts": counts, "entries": entries, "rows": total_rows, "excludedAsb": excluded_asb}
    atomic_json(count_cache, result)
    return result


def build_dataset(official, parsed, record, api_date, changelog_sha):
    months = parsed["months"]
    current_months, previous_months = months[-12:], months[:12]
    force_counts = parsed["counts"]
    forces = [a for a in official["areas"] if a["type"] == "force"]
    assert {a["id"] for a in forces} == set(FORCES.values()), "Official force geography mismatch"
    by_id = {a["id"]: a for a in official["areas"]}
    areas = []
    for source in official["areas"]:
        code = source["id"]
        if source["type"] == "force":
            members = [code]
        elif source["type"] == "region":
            members = [a["id"] for a in forces if a["regionId"] == code]
        else:
            members = [a["id"] for a in forces]
        if not members:
            raise ValueError("No force membership for area: " + code)
        missing = {member: [m for m in months if m not in force_counts[member]] for member in members}
        current_missing = {member: [m for m in absent if m in current_months] for member, absent in missing.items()}
        previous_missing = {member: [m for m in absent if m in previous_months] for member, absent in missing.items()}
        current_complete = not any(current_missing.values())
        previous_complete = not any(previous_missing.values())
        population = source["population"]

        def total(category, window):
            if any(m not in force_counts[member] for member in members for m in window):
                return None
            return sum(force_counts[member][m][category] for member in members for m in window)

        def per_capita(count):
            return None if count is None or code == CITY else round(count / population * 1000, 4)

        metrics = {}
        for category in CATEGORY_IDS:
            current = total(category, current_months)
            previous = total(category, previous_months)
            history = []
            for endpoint in range(11, len(months)):
                count = total(category, months[endpoint - 11:endpoint + 1])
                history.append({"periodEnd": month_end(months[endpoint]), "count": count, "rate": per_capita(count)})
            metrics[category] = {"count": current, "rate": per_capita(current), "previousCount": previous,
                                 "changePercent": None if current is None or not previous else round((current / previous - 1) * 100, 2),
                                 "history": history,
                                 "monthlyCounts": [{"month": m, "count": total(category, [m])} for m in months]}
        quality = ["Provisional Police.uk monthly street-data series. It differs from the official quarterly crime statistics and may not include later reclassifications or cancellations."]
        if not current_complete:
            parts = [f"{by_id[member]['name']}: {', '.join(absent)}" for member, absent in current_missing.items() if absent]
            quality.append("Latest rolling year is incomplete. Counts, rates and ranking are withheld because these force-month submissions are missing: " + "; ".join(parts) + ".")
        if not previous_complete:
            quality.append("The preceding rolling year has missing submissions; year-on-year change is unavailable.")
        if code == CITY:
            quality.append("City of London's resident-based rate is unsuitable for comparison because of its large visiting and commuter population; rates and rankings are suppressed.")
        if source["type"] in ("region", "nation"):
            quality.append("Aggregated from reporting territorial police forces. British Transport Police is excluded; these are not counts assigned by each crime's coordinates.")
        area = {k: copy.deepcopy(source[k]) for k in ("id", "code", "name", "type", "regionId", "population", "populationYear") if k in source}
        area.update({"comparisonEligible": current_complete and code != CITY, "metrics": metrics, "quality": quality,
                     "monthlyCoverage": {"currentComplete": current_complete, "previousComplete": previous_complete,
                                         "missingForceMonths": {k: v for k, v in missing.items() if v}}})
        areas.append(area)
    generated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    coverage = {"start": current_months[0] + "-01", "end": month_end(current_months[-1]),
                "label": dt.date.fromisoformat(current_months[0] + "-01").strftime("%b %Y") + " – " + dt.date.fromisoformat(current_months[-1] + "-01").strftime("%b %Y"),
                "frequency": "monthly", "sourcePublishedAt": record["publishedAt"]}
    population_source = next((s for s in official["sources"] if "population" in (s["id"] + " " + s["title"]).lower()), None)
    sources = [
        {"id": "police-uk-monthly", "title": "Police.uk monthly street-data archive", "url": record["url"], "publishedAt": record["publishedAt"]},
        {"id": "police-uk-changelog", "title": "Police.uk changelog and missing submissions", "url": CHANGELOG},
        {"id": "police-uk-methodology", "title": "Police.uk data definitions and limitations", "url": ABOUT},
    ]
    if population_source:
        sources.append(population_source)
    status_note = "Monthly provisional Police.uk records. Broad categories differ from the official quarterly series. Areas with missing submissions are excluded from the latest comparison; missing data never becomes zero."
    data = {"schemaVersion": 1, "generatedAt": generated, "scope": "England and Wales", "unit": "offences per 1,000 residents",
            "baselineId": NATION, "datasetLabel": "Monthly provisional", "datasetId": "monthly", "statusNote": status_note,
            "coverage": coverage, "categories": CATEGORIES, "areas": areas, "sources": sources,
            "updatePolicy": {"checkFrequency": "monthly", "publicationFrequency": "monthly", "note": status_note},
            "notes": [status_note,
                      "Rates use the same ONS resident-population estimates and police-force geography as the official comparison. They are not a resident's probability of becoming a victim.",
                      "Each current value is a complete rolling 12-month total. Change compares it with the preceding 12 months. History shows rolling-year totals ending each month; individual monthly counts are included in the data export.",
                      "Violence and sexual offences are combined by Police.uk. Fraud and anti-social behaviour are excluded. ASB incidents must not be interpreted as criminal offences.",
                      "A police counting clarification from April 2025 treats shop theft involving violence or threats, including during escape, as business robbery. Robbery and shoplifting trends span this recording change.",
                      "Every CSV row is counted by its reporting force, including records with missing coordinates. British Transport Police and Northern Ireland are excluded. Regional totals sum constituent territorial forces.",
                      "A missing force-month CSV makes the corresponding rolling-year count unavailable for that force and every containing region or national total. Presence of a CSV does not guarantee perfect reporting: consult Police.uk's changelog.",
                      "Police.uk publishes snapshots which may not incorporate later crime cancellations and reclassifications unless the force refreshes its data. Compare trends within this source; do not splice it into the official quarterly time series."],
            "monthlyMetadata": {"latestObservationMonth": months[-1], "apiDate": api_date,
                                "changelogUrl": CHANGELOG, "changelogSha256": changelog_sha,
                                "completeForces": sum(a["type"] == "force" and a["monthlyCoverage"]["currentComplete"] for a in areas),
                                "missingForces": [a["id"] for a in areas if a["type"] == "force" and not a["monthlyCoverage"]["currentComplete"]]}}
    manifest = {"schemaVersion": 1, "generatedAt": generated, "coverage": coverage, "archive": record,
                "archiveSha256": parsed["archiveSha256"], "policeUkLatestApiDate": api_date,
                "changelog": {"url": CHANGELOG, "sha256": changelog_sha},
                "populationSource": population_source, "officialSnapshotGeneratedAt": official["generatedAt"],
                "licence": "Open Government Licence v3.0", "licenceUrl": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                "attribution": "Contains public sector information licensed under the Open Government Licence v3.0. Crime: Police.uk / Single Online Home National Digital Team. Population: Office for National Statistics.",
                "validation": {"monthsRequested": months, "territorialForcesExpected": 43, "parsedCsvFiles": len(parsed["entries"]),
                               "parsedRows": parsed["rows"], "asbRowsExcluded": parsed["excludedAsb"], "csvCrc32Verified": True},
                "entries": parsed["entries"]}
    validate_dataset(data)
    return data, manifest


def validate_dataset(data):
    if data.get("schemaVersion") != 1 or data.get("datasetId") != "monthly":
        raise ValueError("Unsupported monthly schema")
    if data["coverage"]["frequency"] != "monthly":
        raise ValueError("Wrong monthly frequency")
    start, end = dt.date.fromisoformat(data["coverage"]["start"]), dt.date.fromisoformat(data["coverage"]["end"])
    if (end - start).days not in (364, 365) or start.day != 1:
        raise ValueError("Monthly comparison is not a complete rolling year")
    areas = data["areas"]
    if len(areas) != 54 or collections.Counter(a["type"] for a in areas) != {"force": 43, "region": 10, "nation": 1}:
        raise ValueError("Monthly geographic coverage mismatch")
    if len({a["id"] for a in areas}) != 54 or {c["id"] for c in data["categories"]} != set(CATEGORY_IDS):
        raise ValueError("Monthly duplicate areas or category mismatch")
    by_id = {a["id"]: a for a in areas}
    for area in areas:
        complete = area["monthlyCoverage"]["currentComplete"]
        previous_complete = area["monthlyCoverage"]["previousComplete"]
        if area["comparisonEligible"] != (complete and area["id"] != CITY):
            raise ValueError("Incomplete force-month coverage remained comparable")
        if not isinstance(area["population"], int) or area["population"] <= 0:
            raise ValueError("Invalid monthly denominator")
        if set(area["metrics"]) != set(CATEGORY_IDS):
            raise ValueError("Incomplete monthly categories")
        for category, metric in area["metrics"].items():
            count, previous, rate = metric["count"], metric["previousCount"], metric["rate"]
            if (count is not None) != complete or (previous is not None) != previous_complete:
                raise ValueError("Partial rolling-year counts must be null")
            for value in (count, previous):
                if value is not None and (not isinstance(value, int) or value < 0):
                    raise ValueError("Invalid monthly crime count")
            expected_rate = None if count is None or area["id"] == CITY else round(count / area["population"] * 1000, 4)
            if rate != expected_rate:
                raise ValueError("Invalid monthly per-capita rate")
            expected_change = None if count is None or not previous else round((count / previous - 1) * 100, 2)
            if metric["changePercent"] != expected_change:
                raise ValueError("Invalid monthly change or comparison across missing months")
            if len(metric["history"]) != 13 or metric["history"][-1]["count"] != count or metric["history"][-1]["periodEnd"] != end.isoformat():
                raise ValueError("Monthly trend does not reconcile to current comparison")
            if len(metric["monthlyCounts"]) != 24:
                raise ValueError("Missing monthly observations")
        if complete and area["metrics"]["all-crime"]["count"] != sum(area["metrics"][c]["count"] for c in CATEGORY_IDS if c != "all-crime"):
            raise ValueError("Monthly categories do not reconcile to all-crime")
        if area["type"] != "force":
            members = [a for a in areas if a["type"] == "force" and (area["type"] == "nation" or a["regionId"] == area["id"])]
            if sum(a["population"] for a in members) != area["population"]:
                raise ValueError("Monthly population aggregation mismatch")
            if complete != all(a["monthlyCoverage"]["currentComplete"] for a in members):
                raise ValueError("Missing monthly force was omitted from aggregate")
            if complete:
                for category in CATEGORY_IDS:
                    if area["metrics"][category]["count"] != sum(a["metrics"][category]["count"] for a in members):
                        raise ValueError("Monthly regional offence count does not reconcile")
    json.dumps(data, allow_nan=False)


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".monthly-", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", "--check", dest="check", action="store_true")
    parser.add_argument("--force", action="store_true", help="Rebuild output even if source and population hashes are unchanged")
    args = parser.parse_args(argv)
    target, manifest_target = OUTPUT / "monthly.json", OUTPUT / "monthly-manifest.json"
    if args.check:
        validate_dataset(json.loads(target.read_text()))
        manifest = json.loads(manifest_target.read_text())
        if not re.fullmatch(r"[a-f0-9]{64}", manifest["archiveSha256"]):
            raise ValueError("Monthly provenance missing archive hash")
        print("Monthly snapshot valid: 43 forces, ten regional units, missing submissions suppressed.")
        return 0
    official_bytes = (OUTPUT / "crime.json").read_bytes()
    official = json.loads(official_bytes)
    api_date = json.loads(fetch_small(API))["date"]
    latest = api_date[:7]
    if not re.fullmatch(r"\d{4}-\d{2}", latest):
        raise ValueError("Invalid Police.uk latest observation date")
    record = discover_archive(latest)
    print(f"Checking Police.uk {latest} archive ({record['bytes']:,} bytes).", flush=True)
    archive_path, archive_sha = download_archive(record)
    changelog = fetch_small(CHANGELOG)
    changelog_sha = hashlib.sha256(changelog).hexdigest()
    official_sha = hashlib.sha256(official_bytes).hexdigest()
    if target.exists() and manifest_target.exists() and not args.force:
        old = json.loads(manifest_target.read_text())
        if old.get("archiveSha256") == archive_sha and old.get("officialSnapshotSha256") == official_sha and old.get("changelog", {}).get("sha256") == changelog_sha:
            validate_dataset(json.loads(target.read_text()))
            print("Monthly archive, population snapshot and changelog unchanged; snapshot preserved.")
            return 0
    print("Aggregating the latest 24 months of territorial-force street CSVs.", flush=True)
    parsed = parse_archive(archive_path, latest, archive_sha)
    data, manifest = build_dataset(official, parsed, record, api_date, changelog_sha)
    manifest["officialSnapshotSha256"] = official_sha
    if target.exists() and data["coverage"]["end"] < json.loads(target.read_text())["coverage"]["end"]:
        raise ValueError("Police.uk observation period rolled back; retaining newer monthly snapshot")
    # Validate and serialize both payloads before replacing either public file.
    json.dumps(data, allow_nan=False)
    json.dumps(manifest, allow_nan=False)
    atomic_json(manifest_target, manifest)
    atomic_json(target, data)
    complete = data["monthlyMetadata"]["completeForces"]
    print(f"Published monthly provisional: {data['coverage']['label']}; {complete}/43 forces have complete current rolling-year submissions.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Optional monthly refresh failed; existing monthly and official snapshots retained: {error}", file=sys.stderr)
        sys.exit(1)
