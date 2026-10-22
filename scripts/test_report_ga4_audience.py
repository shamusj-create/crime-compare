"""Synthetic offline fixtures for the crime.compare reporting helper.

Fixture audience numbers are invented test inputs, never measured site figures."""

from __future__ import annotations

import csv
import copy
import importlib.util
import io
import json
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).with_name("report_ga4_audience.py")
SPEC = importlib.util.spec_from_file_location("crime_report_ga4_audience", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=ZoneInfo("Europe/London"))


class CrimeGa4ReportTests(unittest.TestCase):
    """Reporting arithmetic, query provenance, processing time and privacy scope."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.bundle = self.make_bundle()

    def response(self, name, rows):
        dimensions, metrics = module.REPORT_SPECS[name]
        return {
            "dimensionHeaders": [{"name": value} for value in dimensions],
            "metricHeaders": [{"name": value, "type": "TYPE_INTEGER"} for value in metrics],
            "rowCount": len(rows),
            "rows": [{"dimensionValues": [{"value": str(row[value])} for value in dimensions],
                      "metricValues": [{"value": str(row[value])} for value in metrics]} for row in rows],
            "metadata": {"timeZone": "Europe/London"},
        }

    def make_bundle(self, days=28):
        end = date(2026, 10, 19)
        start = end - timedelta(days=days - 1)
        reach = days * 5
        overview = {"screenPageViews": days * 100, "totalUsers": reach, "activeUsers": days * 4,
                    "newUsers": days * 2, "sessions": days * 15,
                    "engagedSessions": days * 7, "userEngagementDuration": days * 225}
        daily = [{"date": (start + timedelta(days=value)).strftime("%Y%m%d"),
                  "screenPageViews": 100, "totalUsers": 10, "activeUsers": 8,
                  "newUsers": 2, "sessions": 15, "engagedSessions": 7, "userEngagementDuration": 225}
                 for value in range(days)]
        def session_row(dimension, value):
            return {dimension: value, **{key: overview[key] for key in module.SESSION_METRICS}}
        rows = {
            "overview": [overview], "daily": daily,
            "countries": [session_row("country", "United Kingdom")],
            "devices": [session_row("deviceCategory", "mobile")],
            "channels": [session_row("sessionDefaultChannelGroup", "Organic Search")],
            "sources": [session_row("sessionSourceMedium", "google / organic")],
            "landing_pages": [session_row("landingPage", "/official/forces")],
            "pages": [{"pagePath": "/official/forces", "screenPageViews": days * 60, "totalUsers": reach},
                      {"pagePath": "/monthly/regions", "screenPageViews": days * 30, "totalUsers": reach},
                      {"pagePath": "/privacy", "screenPageViews": days * 10, "totalUsers": 10}],
            "content_groups": [{"contentGroup": name, "screenPageViews": days * views, "totalUsers": reach}
                               for name, views in (("Official comparison", 60), ("Monthly comparison", 30), ("Privacy", 10))],
            # These groups overlap, deliberately. They must never be used to
            # derive period total users or as two percentages adding to 100.
            "returning": [{"newVsReturning": "new", "totalUsers": days * 2},
                          {"newVsReturning": "returning", "totalUsers": days * 4}],
        }
        return {
            "schema_version": 2, "source": module.API_SOURCE, "property_id": "123456789",
            "property_timezone": "Europe/London", "hostname_filter": "crime.compare",
            "measurement_start": start.isoformat(), "report_start": start.isoformat(), "report_end": end.isoformat(),
            "exported_at": "2026-10-22T10:00:00+01:00",
            "reports": {name: {"requests": [module.make_api_request(name, start, end)],
                                "responses": [self.response(name, rows[name])]} for name in module.REPORT_SPECS},
        }

    def report(self):
        return module.build_api_report(self.bundle, now=NOW)

    def test_period_reach_is_not_sum_of_days_or_categories(self):
        report = self.report()
        self.assertEqual(report["status"], "standard")
        self.assertFalse(report["data_quality"]["flags"])
        self.assertEqual(report["sitewide"]["totalUsers"], 140)
        self.assertEqual(report["sitewide"]["average_daily_total_users"], 10)
        self.assertEqual(report["sitewide"]["average_daily_active_users"], 8)
        self.assertEqual(report["sitewide"]["returning_users"], 112)
        self.assertEqual(report["sitewide"]["engagement_rate_percent"], 46.67)
        self.assertEqual(report["sitewide"]["average_engagement_seconds_per_session"], 15)
        self.assertEqual(report["sections"]["Monthly comparison"]["share_of_site_views_percent"], 30)
        self.assertGreater(sum(row["totalUsers"] for row in report["breakdowns"]["pages"]), report["sitewide"]["totalUsers"])
        self.assertIn("certified count of humans", module.render_api_markdown(report))

    def test_provisional_first_period_is_not_extrapolated(self):
        self.bundle = self.make_bundle(7)
        report = self.report()
        self.assertEqual(report["status"], "provisional")
        self.assertEqual(report["complete_days"], 7)
        self.assertEqual(report["sitewide"]["screenPageViews"], 700)
        self.assertIn("no monthly extrapolation", module.render_api_markdown(report))

    def test_rejects_missing_reports_tampered_scope_and_incomplete_rows(self):
        del self.bundle["reports"]["devices"]
        with self.assertRaisesRegex(module.ReportError, "ten approved aggregate reports"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["reports"]["overview"]["requests"][0]["dimensionFilter"]["filter"]["stringFilter"]["value"] = "example.com"
        with self.assertRaisesRegex(module.ReportError, "different dates, host filter"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["reports"]["pages"]["responses"][0]["rowCount"] = 4
        with self.assertRaisesRegex(module.ReportError, "missing or truncated API rows"):
            self.report()

    def test_rejects_inconsistent_views_and_duplicate_rows(self):
        self.bundle["reports"]["daily"]["responses"][0]["rows"][0]["metricValues"][0]["value"] = "99"
        with self.assertRaisesRegex(module.ReportError, "daily page views do not reconcile"):
            self.report()
        self.bundle = self.make_bundle()
        response = self.bundle["reports"]["daily"]["responses"][0]
        response["rows"].append(response["rows"][0])
        response["rowCount"] += 1
        with self.assertRaisesRegex(module.ReportError, "duplicate dimension row"):
            self.report()

    def test_flags_sampling_thresholds_and_unknown_groups_without_hiding_them(self):
        metadata = self.bundle["reports"]["countries"]["responses"][0]["metadata"]
        metadata.update({"subjectToThresholding": True, "samplingMetadatas": [{"samplesReadCount": "10", "samplingSpaceSize": "100"}]})
        self.bundle["reports"]["content_groups"]["responses"][0]["rows"][0]["dimensionValues"][0]["value"] = "(not set)"
        report = self.report()
        self.assertEqual(report["status"], "quality_review_required")
        self.assertTrue(any("threshold" in value for value in report["data_quality"]["flags"]))
        self.assertTrue(any("sampling" in value for value in report["data_quality"]["flags"]))
        self.assertIn("Review source data", module.render_api_html(report))

    def test_rejects_crime_area_detail_and_query_strings(self):
        for path in ("/areas/E23000013", "/official/forces/robbery", "/official/forces?search=Name", "/foo", "/"):
            with self.subTest(path=path):
                self.bundle = self.make_bundle()
                self.bundle["reports"]["pages"]["responses"][0]["rows"][0]["dimensionValues"][0]["value"] = path
                with self.assertRaisesRegex(module.ReportError, "unexpected page path"):
                    self.report()

    def test_timestamps_settling_and_measurement_start(self):
        self.bundle["exported_at"] = "2026-10-21T10:00:00+01:00"
        with self.assertRaisesRegex(module.ReportError, "48-hour processing"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["exported_at"] = "2026-10-22T10:00:00"
        with self.assertRaisesRegex(module.ReportError, "include a timezone"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["measurement_start"] = "2026-10-22"
        with self.assertRaisesRegex(module.ReportError, "before the first complete measurement"):
            self.report()
        with self.assertRaisesRegex(module.ReportError, "no settled complete"):
            module.select_api_window(date(2026, 10, 23), now=NOW)
        start, end = module.select_api_window(date(2026, 9, 1), now=NOW)
        self.assertEqual(end, date(2026, 10, 19))
        self.assertEqual((end - start).days, 27)

    def test_processing_allowance_uses_elapsed_hours_across_spring_clock_change(self):
        spring_now = datetime(2026, 3, 30, 0, 30, tzinfo=ZoneInfo("Europe/London"))
        _, end = module.select_api_window(date(2026, 3, 1), now=spring_now)
        self.assertEqual(end, date(2026, 3, 26))

    def test_omitted_zero_activity_day_is_explicit_and_still_has_zero_in_average(self):
        response = self.bundle["reports"]["daily"]["responses"][0]
        removed = response["rows"].pop()
        response["rowCount"] -= 1
        for name in ("overview", "pages", "content_groups"):
            metric = self.bundle["reports"][name]["responses"][0]["rows"][0]["metricValues"][0]
            metric["value"] = str(int(metric["value"]) - 100)
        report = self.report()
        self.assertEqual(report["data_quality"]["days_with_no_api_row"], ["2026-10-19"])
        self.assertEqual(report["daily"][-1]["screenPageViews"], 0)
        self.assertFalse(report["daily"][-1]["api_returned_row"])
        self.assertEqual(report["sitewide"]["average_daily_views"], 96.43)

    def test_report_pack_is_private_html_escaped_csv_safe_and_not_overwritten(self):
        report = self.report()
        report["breakdowns"]["sources"][0]["label"] = "=SUM(1,2)<script>"
        out = self.folder / "report"
        module.write_report_pack(report, self.bundle, out)
        self.assertIn("&lt;script&gt;", (out / "audience-report.html").read_text())
        self.assertNotIn("<script>", (out / "audience-report.html").read_text())
        self.assertIn("'=SUM", (out / "sources.csv").read_text())
        self.assertEqual((out.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((out / "source-bundle.json").stat().st_mode & 0o777), 0o600)
        self.assertEqual(len(list(out.glob("*.csv"))), 9)
        self.assertEqual(hashlib.sha256((out / "source-bundle.json").read_bytes()).hexdigest(), report["bundle_sha256"])
        self.assertIn("Private draft", (out / "audience-report.html").read_text())
        self.assertNotIn("<script", (out / "audience-report.html").read_text())
        with self.assertRaisesRegex(module.ReportError, "already exists"):
            module.write_report_pack(report, self.bundle, out)
        with self.assertRaisesRegex(module.ReportError, "outside the repository"):
            module.write_report_pack(report, self.bundle, SCRIPT.parents[1] / "public" / "example-report")

    def test_manual_ui_exports_roundtrip_without_api_credentials(self):
        manifest = {key: value for key, value in self.bundle.items() if key != "reports"}
        manifest["manual_quality_review"] = {"sampling": False, "thresholding": False, "other_row": False,
                                             "row_limit": False, "scope_and_filters_checked": True}
        manifest_path = self.folder / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        for name, (dimensions, metrics) in module.REPORT_SPECS.items():
            with (self.folder / f"{name}.csv").open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(dimensions + metrics)
                response = self.bundle["reports"][name]["responses"][0]
                for row in response["rows"]:
                    values = [value["value"] for value in row["dimensionValues"]]
                    if name == "daily":
                        values[0] = f"{values[0][:4]}-{values[0][4:6]}-{values[0][6:]}"
                    writer.writerow(values + [value["value"] for value in row["metricValues"]])
        imported = module.import_csv_bundle(self.folder, manifest_path, now=NOW)
        report = module.build_api_report(imported, now=NOW)
        self.assertEqual(report["source"], module.MANUAL_SOURCE)
        self.assertEqual(report["sitewide"]["totalUsers"], 140)
        self.assertEqual(len(imported["source_files_sha256"]), 11)
        manifest["manual_quality_review"]["row_limit"] = True
        manifest_path.write_text(json.dumps(manifest))
        report = module.build_api_report(module.import_csv_bundle(self.folder, manifest_path, now=NOW), now=NOW)
        self.assertEqual(report["status"], "quality_review_required")

    def test_fetch_saves_exact_queries_and_paginates_without_saving_token(self):
        fixture = self.bundle
        calls = []
        def transport(property_id, request, token):
            self.assertEqual(property_id, "123456789")
            self.assertEqual(token, "")
            name = next(name for name, (dimensions, _) in module.REPORT_SPECS.items()
                        if [value["name"] for value in request["dimensions"]] == list(dimensions))
            response = copy.deepcopy(fixture["reports"][name]["responses"][0])
            start = int(request["offset"])
            response["rows"] = response["rows"][start:start + 10]
            calls.append(name)
            return response
        with patch.object(module, "API_LIMIT", 10):
            bundle = module.fetch_bundle("123456789", date.fromisoformat(fixture["measurement_start"]), now=NOW, post=transport)
            self.assertEqual(calls.count("daily"), 3)
            report = module.build_api_report(bundle, now=NOW)
        self.assertEqual(report["sitewide"]["totalUsers"], 140)
        self.assertNotIn("token", json.dumps(bundle).lower())

    def test_api_failure_does_not_echo_token_or_error_body(self):
        error = module.HTTPError("https://analyticsdata.googleapis.com", 403, "Forbidden", {}, io.BytesIO(b"private-credential-detail"))
        with patch.object(module, "urlopen", side_effect=error):
            with self.assertRaises(module.ReportError) as caught:
                module._api_post("123456789", {}, "fake-secret-token")
        self.assertIn("Viewer access", str(caught.exception))
        self.assertNotIn("private-credential-detail", str(caught.exception))
        self.assertNotIn("fake-secret-token", str(caught.exception))

    def test_existing_authentication_is_required_without_exposing_gcloud_errors(self):
        with patch.dict(module.os.environ, {}, clear=True):
            with self.assertRaisesRegex(module.ReportError, "existing local gcloud"):
                module._oauth_token(token_env="GA4_ACCESS_TOKEN", use_adc=False)
            result = module.subprocess.CompletedProcess([], 1, stdout="", stderr="secret credential error")
            with patch.object(module.subprocess, "run", return_value=result):
                with self.assertRaises(module.ReportError) as caught:
                    module._oauth_token(token_env="GA4_ACCESS_TOKEN", use_adc=True)
            self.assertNotIn("secret credential", str(caught.exception))

    def test_malformed_metric_shape_and_nonfinite_duration_are_rejected(self):
        self.bundle["reports"]["devices"]["responses"][0]["rows"][0]["metricValues"] = None
        with self.assertRaisesRegex(module.ReportError, "malformed dimension or metric"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["reports"]["overview"]["responses"][0]["rows"][0]["metricValues"][-1]["value"] = "nan"
        with self.assertRaisesRegex(module.ReportError, "finite non-negative"):
            self.report()

    def test_measurement_contract_is_exactly_the_seven_approved_virtual_paths(self):
        self.assertEqual(module.HOST, "crime.compare")
        self.assertEqual(module.DEFAULT_PROPERTY_ID, "560206660")
        self.assertEqual(module.SAFE_PATHS, {
            "/official/regions", "/official/forces", "/monthly/regions", "/monthly/forces", "/method", "/sources", "/privacy",
        })
        for path in module.SAFE_PATHS:
            self.assertEqual(module.classify_path(path), module.PATH_GROUPS[path])
        for path in ("/", "/monthly/forces?crime=robbery", "/official/regions#search", "/area/E23000013", "/Cleveland", "/compare/robbery"):
            with self.subTest(path=path):
                with self.assertRaises(module.ReportError):
                    module.classify_path(path)

    def test_country_is_separate_from_the_visited_crime_site_section(self):
        report = self.report()
        self.assertEqual(report["sections"]["Monthly comparison"]["share_of_site_views_percent"], 30)
        self.assertEqual(report["breakdowns"]["countries"][0]["label"], "United Kingdom")
        self.assertEqual(report["breakdowns"]["countries"][0]["session_share_percent"], 100)
        self.assertFalse(any("Cleveland" in str(row) for row in report["breakdowns"]["pages"]))

    def test_read_only_queries_do_not_request_sensitive_dimensions(self):
        dimensions = {dimension for spec in module.REPORT_SPECS.values() for dimension in spec[0]}
        self.assertEqual(dimensions, {
            "date", "country", "deviceCategory", "sessionDefaultChannelGroup", "sessionSourceMedium",
            "landingPage", "pagePath", "contentGroup", "newVsReturning",
        })
        request = module.make_api_request("pages", date(2026, 10, 1), date(2026, 10, 19))
        self.assertEqual(request["dimensionFilter"]["filter"]["stringFilter"]["value"], "crime.compare")
        self.assertNotIn("userId", json.dumps(request))

    def test_unexpected_credentials_or_reader_level_reports_are_not_archived(self):
        self.bundle["access_token"] = "synthetic-test-secret"
        with self.assertRaisesRegex(module.ReportError, "unexpected fields"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["reports"]["individual_events"] = {"rows": []}
        with self.assertRaisesRegex(module.ReportError, "ten approved aggregate reports"):
            self.report()

    def test_wrong_host_or_timezone_cannot_be_reported_as_crime_compare(self):
        self.bundle["hostname_filter"] = "politicians.compare"
        with self.assertRaisesRegex(module.ReportError, "hostname"):
            self.report()
        self.bundle = self.make_bundle()
        self.bundle["property_timezone"] = "UTC"
        with self.assertRaisesRegex(module.ReportError, "timezone"):
            self.report()

    def test_launch_report_dates_follow_48_elapsed_hours(self):
        first_day = date(2026, 10, 23)
        for moment, latest in (
            (datetime(2026, 10, 26, 0, 0, tzinfo=ZoneInfo("Europe/London")), date(2026, 10, 23)),
            (datetime(2026, 10, 28, 0, 0, tzinfo=ZoneInfo("Europe/London")), date(2026, 10, 25)),
            (datetime(2026, 11, 22, 0, 0, tzinfo=ZoneInfo("Europe/London")), date(2026, 11, 19)),
        ):
            with self.subTest(moment=moment):
                start, end = module.select_api_window(first_day, now=moment)
                self.assertEqual(start, first_day)
                self.assertEqual(end, latest)

    def test_new_output_under_another_git_checkout_is_rejected(self):
        other = self.folder / "another-checkout"
        other.mkdir(); (other / ".git").mkdir()
        with self.assertRaisesRegex(module.ReportError, "every Git checkout"):
            module.write_report_pack(self.report(), self.bundle, other / "private-report")

    def test_csv_formula_protection_also_covers_leading_whitespace(self):
        report = self.report()
        report["breakdowns"]["sources"][0]["label"] = "  =HYPERLINK(\"https://example.invalid\")"
        out = self.folder / "spreadsheet-safe-report"
        module.write_report_pack(report, self.bundle, out)
        with (out / "sources.csv").open(newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertTrue(row["label"].startswith("'  ="))


if __name__ == "__main__":
    unittest.main()
