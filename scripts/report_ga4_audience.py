#!/usr/bin/env python3
"""Create private advertiser reports from GA4 exports or read-only Data API queries.

API access is opt-in (--fetch). It uses an existing local OAuth credential, never
creates credentials or changes Google settings, and saves no authentication data.
Adapted from the reviewed reporting helper used by the politicians.compare sister project.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time as clock_time
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


HOST = "crime.compare"
DEFAULT_PROPERTY_ID = "560206660"
ZONE = ZoneInfo("Europe/London")
DAYS = 28
API_SOURCE = "Google Analytics 4 Data API"
MANUAL_SOURCE = "Google Analytics 4 manually exported CSV reports"
SETTLE_HOURS = 48
API_LIMIT = 10_000
MAX_API_ROWS = 100_000
OVERVIEW_METRICS = (
    "screenPageViews", "totalUsers", "activeUsers", "newUsers", "sessions",
    "engagedSessions", "userEngagementDuration",
)
SESSION_METRICS = ("totalUsers", "sessions", "engagedSessions", "userEngagementDuration")
REPORT_SPECS = {
    "overview": ((), OVERVIEW_METRICS),
    "daily": (("date",), OVERVIEW_METRICS),
    "countries": (("country",), SESSION_METRICS),
    "devices": (("deviceCategory",), SESSION_METRICS),
    "channels": (("sessionDefaultChannelGroup",), SESSION_METRICS),
    "sources": (("sessionSourceMedium",), SESSION_METRICS),
    "landing_pages": (("landingPage",), SESSION_METRICS),
    "pages": (("pagePath",), ("screenPageViews", "totalUsers")),
    "content_groups": (("contentGroup",), ("screenPageViews", "totalUsers")),
    "returning": (("newVsReturning",), ("totalUsers",)),
}
# This is the consent controller's complete measurement contract, not a list of
# application URLs. No crime type, area code/name, query, selection or search is
# permitted. The physical '/' entry is measured as '/official/forces'.
PATH_GROUPS = {
    "/official/regions": "Official comparison",
    "/official/forces": "Official comparison",
    "/monthly/regions": "Monthly comparison",
    "/monthly/forces": "Monthly comparison",
    "/method": "Method", "/sources": "Sources", "/privacy": "Privacy",
}
SAFE_PATHS = frozenset(PATH_GROUPS)
CONTENT_GROUPS = tuple(dict.fromkeys(PATH_GROUPS.values()))
SECTION_NAMES = (*CONTENT_GROUPS, "Unclassified")


class ReportError(ValueError):
    """The aggregate inputs do not support a complete, reconciled report."""


def classify_path(path: str) -> str:
    """Match the deliberately coarse, mutually exclusive measurement contract."""
    path = _safe_api_path(path, context="section mapping")
    return "Unclassified" if path == "(not set)" else PATH_GROUPS[path]



def _normalise_column(value: str) -> str:
    return re.sub(r"[\s_-]", "", value.strip().lower())


def _csv_rows(path: Path, expected: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            raw = list(enumerate(csv.reader(handle), start=1))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ReportError(f"cannot read {path}: {exc}") from exc
    # GA4 exports can prepend comment metadata. It is not used as evidence: the
    # accompanying manifest records property, host, timezone and export time.
    while raw and (not raw[0][1] or raw[0][1][0].lstrip().startswith("#")):
        raw.pop(0)
    if not raw:
        raise ReportError(f"{path}: CSV is empty")
    header = tuple(_normalise_column(value) for value in raw.pop(0)[1])
    if header != expected:
        raise ReportError(f"{path}: expected columns {', '.join(expected)}; got {', '.join(header)}")
    result: list[tuple[int, dict[str, str]]] = []
    for line, values in raw:
        if len(values) != len(header) or not any(value.strip() for value in values):
            raise ReportError(f"{path}:{line}: malformed or empty row")
        result.append((line, dict(zip(header, (value.strip() for value in values)))))
    return result


def _day(value: str, *, context: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ReportError(f"{context}: date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ReportError(f"{context}: invalid date {value}") from exc


def _mean(values: list[int]) -> float:
    return round(statistics.mean(values), 2)


def source_bundle_text(bundle: dict[str, object]) -> str:
    """The exact private source-file bytes bound by the report's SHA-256."""
    return json.dumps(bundle, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _aware_timestamp(value: object, *, context: str) -> datetime:
    if not isinstance(value, str):
        raise ReportError(f"{context}: expected a timezone-aware ISO timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReportError(f"{context}: invalid timestamp") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ReportError(f"{context}: timestamp must include a timezone")
    return stamp


def select_api_window(
    measurement_start: date, *, start: date | None = None, end: date | None = None,
    now: datetime | None = None,
) -> tuple[date, date]:
    """Choose 28 settled days, or an explicitly provisional shorter first period."""
    current = now.astimezone(ZONE) if now is not None else datetime.now(ZONE)
    latest = current.date() - timedelta(days=2)
    while current.astimezone(timezone.utc) - datetime.combine(
        latest + timedelta(days=1), time.min, tzinfo=ZONE,
    ).astimezone(timezone.utc) < timedelta(hours=SETTLE_HOURS):
        latest -= timedelta(days=1)
    end = end or latest
    start = start or max(measurement_start, end - timedelta(days=DAYS - 1))
    if start < measurement_start:
        raise ReportError("report starts before the first complete measurement day")
    if end > latest:
        raise ReportError("report end must have finished at least 48 hours ago in Europe/London")
    if end < start:
        raise ReportError("no settled complete measured days yet; wait until 48 hours after the first complete measurement day")
    if (end - start).days >= DAYS:
        raise ReportError("select at most 28 days; use separate period queries for separate reports")
    return start, end


def make_api_request(name: str, start: date, end: date, *, offset: int = 0) -> dict[str, object]:
    dimensions, metrics = REPORT_SPECS[name]
    return {
        "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
        "dimensions": [{"name": value} for value in dimensions],
        "metrics": [{"name": value} for value in metrics],
        "dimensionFilter": {"filter": {"fieldName": "hostName", "stringFilter": {
            "matchType": "EXACT", "value": HOST, "caseSensitive": True,
        }}},
        "keepEmptyRows": True, "returnPropertyQuota": True,
        "limit": str(API_LIMIT), "offset": str(offset),
        "orderBys": ([{"dimension": {"dimensionName": value}} for value in dimensions]
                     if dimensions else []),
    }


def _oauth_token(*, token_env: str, use_adc: bool) -> str:
    token = os.environ.get(token_env, "").strip()
    if not token and use_adc:
        try:
            result = subprocess.run(
                ["gcloud", "auth", "application-default", "print-access-token"],
                check=False, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReportError("could not use local gcloud credentials; authenticate with the analytics.readonly scope first") from exc
        if result.returncode:
            # gcloud stderr can contain local identity/credential details. Do not
            # echo it into a report, log, terminal, or an exception.
            raise ReportError("local Google credentials are unavailable or expired; renew read-only user authentication")
        token = result.stdout.strip()
    if not token or any(char.isspace() for char in token):
        raise ReportError(f"set a valid OAuth access token in {token_env}, or use --use-adc with existing local gcloud credentials")
    return token


def _api_post(property_id: str, request: dict[str, object], token: str) -> dict[str, object]:
    endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    quota_project = os.environ.get("GA4_QUOTA_PROJECT", "").strip()
    if quota_project:
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", quota_project):
            raise ReportError("GA4_QUOTA_PROJECT must be a Google Cloud project ID")
        headers["x-goog-user-project"] = quota_project
    for attempt in range(2):
        try:
            with urlopen(Request(endpoint, data=json.dumps(request).encode(), headers=headers, method="POST"), timeout=20) as response:
                raw = response.read(20_000_001)
                if len(raw) > 20_000_000:
                    raise ReportError("GA4 response exceeds the private aggregate report size limit")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ReportError("GA4 returned an invalid JSON report")
                return result
        except HTTPError as exc:
            exc.close()
            if attempt == 0 and exc.code in {429, 500, 502, 503, 504}:
                clock_time.sleep(1)
                continue
            advice = {
                400: "a requested report is incompatible or its API configuration is invalid",
                401: "the OAuth token is expired or invalid",
                403: "the user needs property Viewer access, analytics.readonly scope, and an enabled Data API project",
                429: "the read-only API quota is temporarily exhausted",
            }.get(exc.code, "Google could not serve the aggregate report")
            raise ReportError(f"GA4 API HTTP {exc.code}: {advice}; no report was published") from exc
        except (URLError, TimeoutError) as exc:
            if attempt == 0:
                clock_time.sleep(1)
                continue
            raise ReportError("GA4 API connection failed after one retry; no report was published") from exc
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ReportError("GA4 returned an unreadable JSON response") from exc
    raise ReportError("GA4 query did not complete")


def fetch_bundle(
    property_id: str, measurement_start: date, *, start: date | None = None, end: date | None = None,
    token_env: str = "GA4_ACCESS_TOKEN", use_adc: bool = False, now: datetime | None = None,
    post=None,
) -> dict[str, object]:
    if not re.fullmatch(r"[1-9]\d*", property_id):
        raise ReportError("property ID must be a numeric GA4 property ID")
    start, end = select_api_window(measurement_start, start=start, end=end, now=now)
    # An injected transport is for deterministic unit tests, not an alternate
    # source of data in the command-line workflow.
    token = _oauth_token(token_env=token_env, use_adc=use_adc) if post is None else ""
    post = post or _api_post
    reports = {}
    for name in REPORT_SPECS:
        requests, responses, offset = [], [], 0
        while True:
            request = make_api_request(name, start, end, offset=offset)
            response = post(property_id, request, token)
            requests.append(request)
            responses.append(response)
            count = _api_count(response.get("rowCount", 0), context=f"{name} rowCount")
            rows = response.get("rows", [])
            if not isinstance(rows, list):
                raise ReportError(f"{name}: GA4 rows must be a list")
            offset += len(rows)
            if offset >= count:
                break
            if not rows or offset >= MAX_API_ROWS:
                raise ReportError(f"{name}: row limit or incomplete pagination; report not saved")
        reports[name] = {"requests": requests, "responses": responses}
    current = now.astimezone(ZONE) if now is not None else datetime.now(ZONE)
    bundle = {
        "schema_version": 2, "source": API_SOURCE, "property_id": property_id,
        "property_timezone": "Europe/London", "hostname_filter": HOST,
        "measurement_start": measurement_start.isoformat(),
        "report_start": start.isoformat(), "report_end": end.isoformat(),
        "exported_at": current.isoformat(), "reports": reports,
    }
    # Validate all responses, dates, scope and coarse paths before the caller
    # saves the bundle. A fetch alone must not create an invalid audience claim.
    build_api_report(bundle, now=current)
    return bundle


def _api_count(value: object, *, context: str) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"(?:0|[1-9]\d*)", str(value)):
        raise ReportError(f"{context}: expected a non-negative integer")
    return int(str(value))


def _api_metric(value: object, *, metric: str, context: str) -> int | float:
    if metric != "userEngagementDuration":
        return _api_count(value, context=context)
    try:
        result = float(str(value))
    except ValueError as exc:
        raise ReportError(f"{context}: expected non-negative seconds") from exc
    if not math.isfinite(result) or result < 0:
        raise ReportError(f"{context}: expected finite non-negative seconds")
    return result


def _quality_flags(metadata: dict[str, object], *, name: str) -> list[str]:
    if metadata.get("timeZone") != "Europe/London":
        raise ReportError(f"{name}: GA4 response timezone must be Europe/London")
    flags = []
    for field, explanation in {
        "dataLossFromOtherRow": "some rows were combined into an '(other)' bucket",
        "subjectToThresholding": "privacy thresholds may withhold rows",
        "samplingMetadatas": "Google reports sampling in this query",
        "dataTruncationReasons": "Google reports truncated data",
    }.items():
        if metadata.get(field):
            flags.append(f"{name}: {explanation}")
    restriction = metadata.get("schemaRestrictionResponse", {})
    if restriction and (not isinstance(restriction, dict) or restriction.get("activeMetricRestrictions")):
        flags.append(f"{name}: access restrictions may affect metrics")
    if metadata.get("emptyReason"):
        flags.append(f"{name}: Google returned an empty-report reason")
    return flags


def _report_rows(
    bundle: dict[str, object], name: str, start: date, end: date,
) -> tuple[list[dict[str, object]], list[str]]:
    reports = bundle.get("reports")
    if not isinstance(reports, dict) or name not in reports or not isinstance(reports[name], dict):
        raise ReportError(f"bundle: missing required {name} report")
    item = reports[name]
    requests, responses = item.get("requests"), item.get("responses")
    if not isinstance(requests, list) or not isinstance(responses, list) or not requests or len(requests) != len(responses):
        raise ReportError(f"{name}: request/response pages are missing or inconsistent")
    dimensions, metrics = REPORT_SPECS[name]
    result, flags, seen = [], [], set()
    expected_count, offset = None, 0
    for request, response in zip(requests, responses):
        if request != make_api_request(name, start, end, offset=offset):
            raise ReportError(f"{name}: saved query has different dates, host filter, dimensions, metrics or pagination")
        if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
            raise ReportError(f"{name}: missing GA4 response metadata")
        flags.extend(_quality_flags(response["metadata"], name=name))
        dheaders = response.get("dimensionHeaders", [])
        mheaders = response.get("metricHeaders", [])
        if (not isinstance(dheaders, list) or not isinstance(mheaders, list)
                or not all(isinstance(header, dict) for header in dheaders + mheaders)
                or [header.get("name") for header in dheaders if isinstance(header, dict)] != list(dimensions)
                or [header.get("name") for header in mheaders if isinstance(header, dict)] != list(metrics)):
            raise ReportError(f"{name}: response headers do not match the requested schema")
        count = _api_count(response.get("rowCount", 0), context=f"{name} rowCount")
        if count > MAX_API_ROWS:
            raise ReportError(f"{name}: response exceeds the aggregate row limit")
        if expected_count is not None and count != expected_count:
            raise ReportError(f"{name}: row count changed during pagination; fetch a fresh bundle")
        expected_count = count
        raw_rows = response.get("rows", [])
        if not isinstance(raw_rows, list):
            raise ReportError(f"{name}: response rows must be a list")
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise ReportError(f"{name}: invalid response row")
            dvalues, mvalues = raw.get("dimensionValues", []), raw.get("metricValues", [])
            if (not isinstance(dvalues, list) or not isinstance(mvalues, list)
                    or len(dvalues) != len(dimensions) or len(mvalues) != len(metrics)):
                raise ReportError(f"{name}: malformed dimension or metric row")
            key = tuple(value.get("value") for value in dvalues if isinstance(value, dict))
            if len(key) != len(dimensions) or any(not isinstance(value, str) for value in key):
                raise ReportError(f"{name}: malformed dimension value")
            if key in seen:
                raise ReportError(f"{name}: duplicate dimension row; pagination cannot be reconciled")
            seen.add(key)
            if any(value == "(other)" for value in key):
                flags.append(f"{name}: an '(other)' bucket is present")
            row = dict(zip(dimensions, key))
            for metric, raw_value in zip(metrics, mvalues):
                if not isinstance(raw_value, dict):
                    raise ReportError(f"{name}: malformed metric value")
                row[metric] = _api_metric(raw_value.get("value"), metric=metric, context=f"{name} {metric}")
            result.append(row)
        offset += len(raw_rows)
    if offset != expected_count:
        raise ReportError(f"{name}: missing or truncated API rows ({offset} received, {expected_count} declared)")
    return result, flags


def _safe_api_path(path: object, *, context: str) -> str:
    if path == "(not set)":
        return "(not set)"
    if not isinstance(path, str) or path.rstrip("/") not in {value.rstrip("/") for value in SAFE_PATHS}:
        raise ReportError(f"{context}: unexpected page path; check coarse-path measurement before exporting a report")
    return path.rstrip("/") or "/"


def _ratio(numerator: int | float, denominator: int | float, *, percent: bool = False) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * (100 if percent else 1), 2)


def build_api_report(bundle: dict[str, object], *, now: datetime | None = None) -> dict[str, object]:
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 2 or bundle.get("source") not in {API_SOURCE, MANUAL_SOURCE}:
        raise ReportError("expected a version-2 GA4 Data API aggregate bundle")
    allowed_fields = {"schema_version", "source", "property_id", "property_timezone", "hostname_filter",
                      "measurement_start", "report_start", "report_end", "exported_at", "reports",
                      "source_files_sha256", "manual_quality_review"}
    if set(bundle) - allowed_fields:
        raise ReportError("source bundle contains unexpected fields; never include credentials or reader-level data")
    if not isinstance(bundle.get("reports"), dict) or set(bundle["reports"]) != set(REPORT_SPECS):
        raise ReportError("source bundle must contain only the ten approved aggregate reports")
    property_id = bundle.get("property_id")
    if not isinstance(property_id, str) or not re.fullmatch(r"[1-9]\d*", property_id):
        raise ReportError("bundle: property_id must be a numeric string")
    if bundle.get("property_timezone") != "Europe/London" or bundle.get("hostname_filter") != HOST:
        raise ReportError("bundle: reporting timezone or hostname is incorrect")
    measurement_start = _day(str(bundle.get("measurement_start", "")), context="measurement_start")
    start = _day(str(bundle.get("report_start", "")), context="report_start")
    end = _day(str(bundle.get("report_end", "")), context="report_end")
    current = now.astimezone(ZONE) if now is not None else datetime.now(ZONE)
    select_api_window(measurement_start, start=start, end=end, now=current)
    exported_at = _aware_timestamp(bundle.get("exported_at"), context="exported_at")
    if exported_at > current + timedelta(minutes=5):
        raise ReportError("bundle: export timestamp is in the future")
    settled_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=ZONE).astimezone(timezone.utc) + timedelta(hours=SETTLE_HOURS)
    if exported_at < settled_at:
        raise ReportError("bundle: export predates the 48-hour processing allowance")
    data, flags = {}, []
    for name in REPORT_SPECS:
        data[name], findings = _report_rows(bundle, name, start, end)
        flags.extend(findings)
    if bundle["source"] == MANUAL_SOURCE:
        review = bundle.get("manual_quality_review")
        if not isinstance(review, dict) or set(review) != {"sampling", "thresholding", "other_row", "row_limit", "scope_and_filters_checked"}:
            raise ReportError("manual CSV bundle: explicit source data-quality review is required")
        if not all(isinstance(value, bool) for value in review.values()):
            raise ReportError("manual CSV bundle: quality-review values must be true or false")
        if not review["scope_and_filters_checked"]:
            flags.append("Manual source exports: dates, hostname, measurement scope and internal traffic need review")
        for key in ("sampling", "thresholding", "other_row", "row_limit"):
            if review[key]:
                flags.append(f"Manual source exports: reviewer reported {key.replace('_', ' ')}")
    if len(data["overview"]) > 1:
        raise ReportError("overview: expected one undimensioned period total")
    overview = data["overview"][0] if data["overview"] else {key: 0 for key in OVERVIEW_METRICS}
    if not overview["totalUsers"]:
        flags.append("No users were recorded in this period; measurement and collection coverage need checking before an advertiser claim")
    expected_days = [start + timedelta(days=value) for value in range((end - start).days + 1)]
    by_day = {}
    for row in data["daily"]:
        stamp = row["date"]
        if not re.fullmatch(r"\d{8}", stamp):
            raise ReportError("daily: GA4 date must be YYYYMMDD")
        day = _day(f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}", context="daily")
        if day not in expected_days:
            raise ReportError("daily: date outside the selected window")
        by_day[day] = row
    missing_days = [day.isoformat() for day in expected_days if day not in by_day]
    daily = [{"date": day.isoformat(), **{metric: by_day.get(day, {}).get(metric, 0) for metric in OVERVIEW_METRICS},
              "api_returned_row": day in by_day} for day in expected_days]
    if sum(row["screenPageViews"] for row in daily) != overview["screenPageViews"]:
        raise ReportError("daily page views do not reconcile to the undimensioned period total")
    # Users are deduplicated by Google within the requested period, so they are
    # never obtained by adding daily or country/page rows together.
    daily_users = [row["totalUsers"] for row in daily]
    if daily_users and not max(daily_users) <= overview["totalUsers"] <= sum(daily_users):
        flags.append("Daily and period users differ beyond expected deduplication bounds; check GA4 estimation and data quality")
    if overview["activeUsers"] > overview["totalUsers"] or overview["newUsers"] > overview["totalUsers"]:
        flags.append("A user metric exceeds period total users; review GA4 processing and estimation")
    if overview["engagedSessions"] > overview["sessions"]:
        raise ReportError("engaged sessions exceed total sessions")
    for name, dimension in (("pages", "pagePath"), ("landing_pages", "landingPage")):
        for row in data[name]:
            row[dimension] = _safe_api_path(row[dimension], context=name)
    if any(row[dimension] == "(not set)" for name, dimension in (("pages", "pagePath"), ("landing_pages", "landingPage")) for row in data[name]):
        flags.append("Page context is unclassified; verify consent-controller collection before external use")
    if sum(row["screenPageViews"] for row in data["pages"]) != overview["screenPageViews"]:
        raise ReportError("popular-page views do not reconcile to the undimensioned period total")
    if sum(row["screenPageViews"] for row in data["content_groups"]) != overview["screenPageViews"]:
        raise ReportError("content-group views do not reconcile to the undimensioned period total")
    sections = {name: {"total_views": 0} for name in SECTION_NAMES}
    for row in data["pages"]:
        section = classify_path(row["pagePath"]) if row["pagePath"] != "(not set)" else "Unclassified"
        sections[section]["total_views"] += row["screenPageViews"]
    for item in sections.values():
        item["share_of_site_views_percent"] = _ratio(item["total_views"], overview["screenPageViews"], percent=True)
        item["average_daily_views"] = _ratio(item["total_views"], len(expected_days))
    for row in data["content_groups"]:
        if row["contentGroup"] not in CONTENT_GROUPS:
            flags.append("content_groups: a content group is missing or outside the five approved coarse groups; page paths determine section shares")
    group_views = {row["contentGroup"]: row["screenPageViews"] for row in data["content_groups"]}
    if any(group_views.get(name, 0) != item["total_views"] for name, item in sections.items()):
        flags.append("content_groups: approved group values differ from coarse page-path section totals; check the collection mapping")
    if any(row["newVsReturning"] not in {"new", "returning", "(not set)"} for row in data["returning"]):
        flags.append("new/returning: an unknown user category was returned")
    if any(row["newVsReturning"] == "(not set)" for row in data["returning"]):
        flags.append("new/returning: an unclassified user bucket is present; returning users cover the known returning category only")
    returning = next((row["totalUsers"] for row in data["returning"] if row["newVsReturning"] == "returning"), 0)
    for name in ("countries", "devices", "channels", "sources", "landing_pages"):
        dimension = REPORT_SPECS[name][0][0]
        for row in data[name]:
            row["label"] = row.pop(dimension)
            row["session_share_percent"] = _ratio(row["sessions"], overview["sessions"], percent=True)
            row["engagement_rate_percent"] = _ratio(row["engagedSessions"], row["sessions"], percent=True)
        data[name].sort(key=lambda row: (-row["sessions"], row["label"]))
        if sum(row["sessions"] for row in data[name]) != overview["sessions"]:
            flags.append(f"{name}: session rows differ from the period total; review source coverage, scope and GA4 estimation")
        # Geographic/device and acquisition rows can carry unknown values. They
        # are retained visibly, rather than discarded to inflate audience share.
    data["pages"].sort(key=lambda row: (-row["screenPageViews"], row["pagePath"]))
    complete_days = len(expected_days)
    provisional = complete_days < DAYS
    return {
        "publication_status": "private_draft_pending_review",
        "schema_version": 2, "status": "quality_review_required" if flags else ("provisional" if provisional else "standard"),
        "site": HOST, "source": bundle["source"], "property_id": property_id,
        "property_timezone": "Europe/London", "measurement_start": measurement_start.isoformat(),
        "period_start": start.isoformat(), "period_end": end.isoformat(), "complete_days": complete_days,
        "provisional": provisional, "processing_allowance_hours": SETTLE_HOURS,
        "exported_at": bundle["exported_at"], "generated_at": current.isoformat(),
        "source_url": f"https://analytics.google.com/analytics/web/#/p{property_id}/reports/intelligenthome",
        "bundle_sha256": hashlib.sha256(source_bundle_text(bundle).encode()).hexdigest(),
        "sitewide": {
            **overview, "returning_users": returning,
            "average_daily_views": _mean([row["screenPageViews"] for row in daily]),
            "median_daily_views": statistics.median(row["screenPageViews"] for row in daily),
            "average_daily_total_users": _mean(daily_users), "median_daily_total_users": statistics.median(daily_users),
            "average_daily_active_users": _mean([row["activeUsers"] for row in daily]),
            "median_daily_active_users": statistics.median(row["activeUsers"] for row in daily),
            "engagement_rate_percent": _ratio(overview["engagedSessions"], overview["sessions"], percent=True),
            "average_engagement_seconds_per_session": _ratio(overview["userEngagementDuration"], overview["sessions"]),
            "views_per_session": _ratio(overview["screenPageViews"], overview["sessions"]),
            "sessions_per_total_user": _ratio(overview["sessions"], overview["totalUsers"]),
        },
        "daily": daily, "sections": sections,
        "breakdowns": {name: data[name] for name in ("countries", "devices", "channels", "sources", "landing_pages", "pages")},
        "data_quality": {"flags": sorted(set(flags)), "days_with_no_api_row": missing_days,
                         "all_required_reports_present": True, "view_totals_reconciled": True},
        "limitations": [
            "GA4 user counts describe measured browser/device identities under Google's reporting identity and estimation; they are not a certified count of individual humans.",
            "Google excludes known bots and spiders. Unknown bots, internal visits and test activity may remain; confirm internal-traffic exclusions before sharing.",
            "Only consenting browsers are measured. Standalone area, crime-category, methodology and sources pages do not load analytics, so reports do not cover all public pages. Declined consent, blockers and implementation gaps also reduce coverage; no uplift for unmeasured readers is applied.",
            "Total users are queried once for the entire period. Daily averages, countries and pages must not be added together to estimate period reach.",
            "New and returning user groups can overlap when a first-time visitor returns within the period; they are not complementary percentages.",
            "Section shares describe page views of broad official/monthly comparison and reference sections. Visitor countries are shown separately and do not identify which crime areas a visitor studied, their residence or personal circumstances.",
            "Days omitted by the complete GA4 API response count as zero recorded activity. This cannot establish whether collection was functioning on those days.",
            "Engagement is GA4 foreground time; an engaged session meets Google's duration, key-event or multiple-page criteria. It is not time looking at an advertisement.",
            "Page views are contextual audience evidence. Paid ad impressions, viewability, clicks, reach and campaign performance require the actual placement to be measured after an advertiser is booked.",
            "No crime-type selections, crime-area views, searches, filters, profile selections, precise visitor location, demographics, inferred interests or reader-level records are requested or included.",
        ],
    }


def import_csv_bundle(folder: Path, manifest_path: Path, *, now: datetime | None = None) -> dict[str, object]:
    """Import manually checked, normalized GA4 UI exports, without an API token."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"cannot read manual report manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ReportError("manual manifest must be an object")
    start = _day(str(manifest.get("report_start", "")), context="report_start")
    end = _day(str(manifest.get("report_end", "")), context="report_end")
    bundle = {**manifest, "schema_version": 2, "source": MANUAL_SOURCE, "reports": {},
              "source_files_sha256": {"manifest.json": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}}
    for name, (dimensions, metrics) in REPORT_SPECS.items():
        path = folder / f"{name}.csv"
        columns = dimensions + metrics
        rows = _csv_rows(path, tuple(_normalise_column(value) for value in columns))
        api_rows = []
        for line, row in rows:
            dimensions_values = [row[_normalise_column(value)] for value in dimensions]
            if name == "daily":
                day = _day(dimensions_values[0], context=f"{path}:{line}")
                dimensions_values[0] = day.strftime("%Y%m%d")
            api_rows.append({
                "dimensionValues": [{"value": value} for value in dimensions_values],
                "metricValues": [{"value": row[_normalise_column(value)]} for value in metrics],
            })
        # This is a canonical table envelope, explicitly labelled manual CSV.
        # It does not assert that the saved query was sent through Google's API.
        request = make_api_request(name, start, end)
        response = {"dimensionHeaders": [{"name": value} for value in dimensions],
                    "metricHeaders": [{"name": value} for value in metrics],
                    "rows": api_rows, "rowCount": len(api_rows), "metadata": {"timeZone": "Europe/London"}}
        bundle["reports"][name] = {"requests": [request], "responses": [response]}
        bundle["source_files_sha256"][f"{name}.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
    build_api_report(bundle, now=now)
    return bundle


def _display(value: object, *, percent: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}" + ("%" if percent else "")
    if isinstance(value, float):
        return f"{value:,.2f}" + ("%" if percent else "")
    return str(value)


def render_api_markdown(report: dict[str, object]) -> str:
    totals = report["sitewide"]
    lines = [
        "# crime.compare · Audience report", "", "**Private draft — review source coverage before sharing.**", "",
        f"Period: **{report['period_start']} – {report['period_end']}** · {report['complete_days']} complete Europe/London days",
        f"Source: {report['source']} · property {report['property_id']} · extracted {report['exported_at']}",
        f"First complete measurement day: {report['measurement_start']} · data processing allowance: {SETTLE_HOURS} hours", "",
    ]
    if report["provisional"]:
        lines.extend(["**Provisional launch period:** fewer than 28 complete measured days. Figures cover only the dates above; no monthly extrapolation is applied.", ""])
    if report["data_quality"]["flags"]:
        lines.extend(["**Data quality review required before external use:**", ""])
        lines.extend(f"- {value}" for value in report["data_quality"]["flags"])
        lines.append("")
    lines.extend(["| Audience measure | Recorded value |", "| --- | ---: |"])
    for label, key, percent in (
        ("Page views", "screenPageViews", False), ("Average daily page views", "average_daily_views", False),
        ("Median daily page views", "median_daily_views", False), ("Total users over the entire period (GA4)", "totalUsers", False),
        ("Average daily users (GA4)", "average_daily_total_users", False),
        ("Median daily users (GA4)", "median_daily_total_users", False),
        ("Active users over the entire period (GA4)", "activeUsers", False),
        ("Average daily active users (GA4)", "average_daily_active_users", False),
        ("New users (GA4)", "newUsers", False), ("Returning users (GA4)", "returning_users", False),
        ("Sessions", "sessions", False), ("Engaged sessions", "engagedSessions", False),
        ("Engagement rate", "engagement_rate_percent", True),
        ("Average engagement seconds per session", "average_engagement_seconds_per_session", False),
        ("Page views per session", "views_per_session", False),
    ):
        lines.append(f"| {label} | {_display(totals[key], percent=percent)} |")
    lines.extend(["", "## Broad site sections", "", "| Section | Page views | Share of page views |", "| --- | ---: | ---: |"])
    for label, item in report["sections"].items():
        lines.append(f"| {label} | {_display(item['total_views'])} | {_display(item['share_of_site_views_percent'], percent=True)} |")
    titles = {"countries": "Visitor countries", "devices": "Devices", "channels": "Acquisition channels",
              "sources": "Referral sources and media", "landing_pages": "Landing pages"}
    for name, title in titles.items():
        lines.extend(["", f"## {title}", "", "| Category | Sessions | Share of sessions | Users (overlapping) | Engagement rate |",
                      "| --- | ---: | ---: | ---: | ---: |"])
        for row in report["breakdowns"][name]:
            label = html.escape(str(row["label"]), quote=False).replace("|", "\\|").replace("\n", " ").replace("[", "\\[").replace("]", "\\]")
            lines.append(f"| {label} | {_display(row['sessions'])} | {_display(row['session_share_percent'], percent=True)} | {_display(row['totalUsers'])} | {_display(row['engagement_rate_percent'], percent=True)} |")
    lines.extend(["", "## Popular broad pages", "", "| Page group | Page views | Users (overlapping) |", "| --- | ---: | ---: |"])
    for row in report["breakdowns"]["pages"]:
        lines.append(f"| {row['pagePath']} | {_display(row['screenPageViews'])} | {_display(row['totalUsers'])} |")
    lines.extend(["", "## Method and limitations", "", "These are measured browser events, not a certified count of humans or advert impressions.", ""])
    lines.extend(f"- {value}" for value in report["limitations"])
    if report["data_quality"]["days_with_no_api_row"]:
        lines.extend(["", "Days with no returned activity row: " + ", ".join(report["data_quality"]["days_with_no_api_row"]) + "."])
    lines.extend(["", f"[Open the source property]({report['source_url']}) · generated {report['generated_at']}",
                  "", f"Private source-bundle SHA-256: `{report['bundle_sha256']}`", ""])
    return "\n".join(lines)


def render_api_html(report: dict[str, object]) -> str:
    """A self-contained, printable media-sales report; no trackers or assets."""
    esc = lambda value: html.escape(str(value), quote=True)
    totals = report["sitewide"]
    cards = "".join(f'<article class="card"><span>{esc(label)}</span><strong>{esc(_display(totals[key], percent=percent))}</strong></article>'
                    for label, key, percent in (
                        ("Page views", "screenPageViews", False), ("Period users · GA4", "totalUsers", False),
                        ("Average daily users", "average_daily_total_users", False), ("Sessions", "sessions", False),
                        ("Engagement rate", "engagement_rate_percent", True),
                        ("Engagement seconds / session", "average_engagement_seconds_per_session", False)))
    def table(headers, rows):
        return '<div class="table-wrap"><table><thead><tr>' + "".join(f"<th>{esc(value)}</th>" for value in headers) + '</tr></thead><tbody>' + "".join('<tr>' + "".join(f"<td>{esc(value)}</td>" for value in row) + '</tr>' for row in rows) + '</tbody></table></div>'
    sections = table(["Section", "Page views", "Share of views"], [
        [name, _display(item["total_views"]), _display(item["share_of_site_views_percent"], percent=True)] for name, item in report["sections"].items()])
    tables = ""
    for name, title in (("countries", "Visitor countries"), ("devices", "Devices"), ("channels", "Acquisition channels"),
                        ("sources", "Referral sources and media"), ("landing_pages", "Landing pages")):
        tables += f'<section><h2>{title}</h2>' + table(["Category", "Sessions", "Session share", "Users¹", "Engagement rate"], [
            [row["label"], _display(row["sessions"]), _display(row["session_share_percent"], percent=True),
             _display(row["totalUsers"]), _display(row["engagement_rate_percent"], percent=True)] for row in report["breakdowns"][name]]) + '</section>'
    pages = table(["Page group", "Views", "Users¹"], [
        [row["pagePath"], _display(row["screenPageViews"]), _display(row["totalUsers"])] for row in report["breakdowns"]["pages"]])
    user_details = table(["Audience measure", "Value"], [
        [label, _display(totals[key])] for label, key in (
            ("Average daily page views", "average_daily_views"), ("Median daily page views", "median_daily_views"),
            ("Median daily users", "median_daily_total_users"), ("Active users over the period", "activeUsers"),
            ("Average daily active users", "average_daily_active_users"), ("New users²", "newUsers"),
            ("Returning users²", "returning_users"), ("Page views per session", "views_per_session"))])
    warnings = ''.join(f'<li>{esc(value)}</li>' for value in report["data_quality"]["flags"])
    quality = f'<aside class="notice"><strong>Review source data before external use</strong><ul>{warnings}</ul></aside>' if warnings else ''
    provisional = '<aside class="notice"><strong>Provisional launch period</strong><p>Fewer than 28 complete measured days are available. This report covers only the dates shown; no monthly extrapolation is applied.</p></aside>' if report["provisional"] else ''
    max_views = max((row["screenPageViews"] for row in report["daily"]), default=0) or 1
    bars = ''.join(f'<div class="bar-column" title="{esc(row["date"])}: {esc(_display(row["screenPageViews"]))} page views"><i style="height:{max(1, round(row["screenPageViews"] / max_views * 100))}%"></i></div>' for row in report["daily"])
    limitations = ''.join(f'<li>{esc(value)}</li>' for value in report["limitations"])
    no_rows = ', '.join(report["data_quality"]["days_with_no_api_row"])
    no_rows = f'<p>Days without a returned activity row: {esc(no_rows)}.</p>' if no_rows else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>crime.compare · Audience report</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eff2f3;color:#152d3a;font:15px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:1100px;margin:40px auto;padding:44px;background:#fff;border:1px solid #d8e1e4;border-radius:8px}}header{{border-top:5px solid #bd9655;padding-top:24px}}.brand{{letter-spacing:.13em;font-size:12px;font-weight:750;text-transform:uppercase;color:#526c79}}h1{{font:400 45px/1.1 Georgia,serif;letter-spacing:-.02em;margin:16px 0}}h2{{font:400 27px/1.25 Georgia,serif;margin:34px 0 16px}}p{{margin:10px 0}}.subtle,footer{{color:#617580;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:28px 0}}.card{{padding:20px;border:1px solid #dce4e7;border-radius:5px;background:#f8fafb}}.card span{{font-size:12px;color:#536c79}}.card strong{{display:block;font:400 32px/1.2 Georgia,serif;margin-top:8px}}.notice{{padding:18px 22px;background:#faf5e9;border-left:3px solid #bd9655;margin:20px 0}}.notice p{{margin-bottom:0}}.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th{{text-align:right;background:#edf2f4;font-size:11px;letter-spacing:.04em;text-transform:uppercase}}td,th{{padding:11px 12px;border-bottom:1px solid #dce4e7}}td{{text-align:right;font-variant-numeric:tabular-nums}}th:first-child,td:first-child{{text-align:left}}section{{break-inside:avoid}}.chart{{display:flex;align-items:flex-end;gap:5px;height:120px;border-bottom:1px solid #dce4e7;padding-top:5px}}.bar-column{{height:100%;flex:1;display:flex;align-items:flex-end}}.bar-column i{{display:block;background:#315d70;width:100%;min-height:1px;border-radius:2px 2px 0 0}}.axis{{display:flex;justify-content:space-between;font-size:11px;color:#617580;margin-top:8px}}.method li{{margin-bottom:8px}}a{{color:#315d70}}footer{{margin-top:30px;padding-top:20px;border-top:1px solid #dce4e7;overflow-wrap:anywhere}}@media(max-width:700px){{main{{margin:0;padding:24px;border:0;border-radius:0}}h1{{font-size:36px}}.grid{{grid-template-columns:repeat(2,1fr)}}.card{{padding:14px}}.card strong{{font-size:27px}}}}@media print{{body{{background:#fff}}main{{margin:0;padding:0;border:0;max-width:none}}.notice,.card,th{{print-color-adjust:exact}}a{{color:inherit}}.grid{{break-inside:avoid}}footer{{font-size:10px}}}}
</style></head><body><main><header><div class="brand">crime.compare · publisher audience</div><h1>Audience report</h1><p class="subtle">Private draft · review source coverage before sharing</p><p>{esc(report['period_start'])} – {esc(report['period_end'])} · {report['complete_days']} complete days · Europe/London</p><p class="subtle">Google Analytics 4 · First complete measurement day {esc(report['measurement_start'])} · {SETTLE_HOURS}-hour processing allowance</p></header>{provisional}{quality}<div class="grid">{cards}</div><section><h2>Daily page views</h2><div class="chart" role="img" aria-label="Daily page views. Full daily values are supplied in the accompanying CSV.">{bars}</div><div class="axis"><span>{esc(report['period_start'])}</span><span>{esc(report['period_end'])}</span></div></section><section><h2>Audience detail</h2>{user_details}<p class="subtle">¹ A user may appear in several categories. Period reach comes from one period query. ² New and returning groups can overlap.</p></section><section><h2>Broad site sections</h2>{sections}<p class="subtle">Share of page views by broad site section. These do not identify crime-type or area interests; visitor country is shown separately below.</p></section>{tables}<section><h2>Popular broad pages</h2>{pages}</section><section class="method"><h2>Method and limitations</h2><p>These are measured browser events, not a certified count of humans or advert impressions.</p><ul>{limitations}</ul>{no_rows}</section><footer><p>Source: {esc(report['source'])} · property {esc(report['property_id'])} · <a href="{esc(report['source_url'])}">View Google Analytics</a></p><p>Extracted {esc(report['exported_at'])} · Generated {esc(report['generated_at'])}</p><p>Source-bundle SHA-256: {esc(report['bundle_sha256'])}</p></footer></main></body></html>'''


def write_report_pack(report: dict[str, object], bundle: dict[str, object], output_dir: Path) -> None:
    """Create a new private folder so previous exports are never overwritten."""
    repository = Path(__file__).resolve().parents[1]
    resolved = output_dir.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ReportError("save advertiser reports outside the repository and public website folders")
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ReportError("save advertiser reports outside every Git checkout")
    if output_dir.exists():
        raise ReportError("output directory already exists; choose a new private report directory")
    output_dir.mkdir(mode=0o700, parents=True)
    outputs = {
        "source-bundle.json": source_bundle_text(bundle),
        "audience-report.json": json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        "audience-report.md": render_api_markdown(report),
        "audience-report.html": render_api_html(report),
    }
    tables = {"daily": report["daily"], **report["breakdowns"]}
    tables["summary"] = [{"metric": key, "value": value} for key, value in report["sitewide"].items()]
    tables["sections"] = [{"section": key, **value} for key, value in report["sections"].items()]
    for name, rows in tables.items():
        if not rows:
            continue
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        # Prevent cells beginning with spreadsheet formula tokens from being
        # executed when a recipient opens a source/medium label in Excel.
        writer.writerows({key: ("'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) else value)
                          for key, value in row.items()} for row in rows)
        outputs[f"{name}.csv"] = buffer.getvalue()
    for name, contents in outputs.items():
        path = output_dir / name
        path.write_text(contents, encoding="utf-8")
        path.chmod(0o600)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fetch", action="store_true", help="read aggregate reports from the Google Data API, using existing read-only authentication")
    modes.add_argument("--bundle", type=Path, help="rebuild offline from a saved version-2 aggregate source bundle")
    modes.add_argument("--csv-directory", type=Path, help="folder of normalized GA4 UI exports for the full report")
    parser.add_argument("--property-id", default=os.environ.get("CRIME_GA4_PROPERTY_ID", DEFAULT_PROPERTY_ID), help="crime.compare numeric GA4 property ID (560206660); alternatively set CRIME_GA4_PROPERTY_ID (not the G- measurement ID)")
    parser.add_argument("--measurement-start", type=date.fromisoformat, help="first complete verified production measurement day, YYYY-MM-DD")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--access-token-env", default="GA4_ACCESS_TOKEN", help="environment variable containing an existing OAuth token; never put a token in a command argument")
    parser.add_argument("--use-adc", action="store_true", help="use existing local gcloud Application Default Credentials")
    parser.add_argument("--output-dir", type=Path, required=True, help="new private folder outside Git checkouts for HTML, CSV, JSON and Markdown")
    parser.add_argument("--manifest", type=Path, help="required manual-source manifest for --csv-directory")
    args = parser.parse_args(argv)
    try:
        if args.fetch:
            if not args.property_id:
                raise ReportError("--fetch requires --property-id or CRIME_GA4_PROPERTY_ID for the dedicated crime.compare property")
            if args.measurement_start is None:
                raise ReportError("--fetch requires --measurement-start (the first complete measured production day)")
            bundle = fetch_bundle(args.property_id, args.measurement_start, start=args.start, end=args.end,
                                  token_env=args.access_token_env, use_adc=args.use_adc)
        elif args.csv_directory:
            if args.manifest is None:
                raise ReportError("--csv-directory requires --manifest with the manual source quality review")
            bundle = import_csv_bundle(args.csv_directory, args.manifest)
        else:
            bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        report = build_api_report(bundle)
        write_report_pack(report, bundle, args.output_dir)
    except (ReportError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"GA4 report rejected: {exc}", file=sys.stderr)
        return 2
    # Aggregate audience figures and source responses stay in the private pack.
    print(f"Private report pack created: {args.output_dir} ({report['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
