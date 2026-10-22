"""Coverage safety tests for the optional Police.uk monthly pipeline."""
import copy
import csv
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("refresh_monthly", Path(__file__).with_name("refresh_monthly.py"))
monthly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monthly)


def fixture():
    months = [monthly.month_offset("2026-08", i) for i in range(-23, 1)]
    force_areas = []
    region_codes = ["E1200000" + str(i) for i in range(1, 10)] + ["W92000004"]
    for i, code in enumerate(monthly.FORCES.values()):
        region = "W92000004" if code.startswith("W") else region_codes[i % 9]
        force_areas.append({"id": code, "code": code, "name": code, "type": "force", "regionId": region,
                            "population": 1000, "populationYear": 2025})
    regions = [{"id": code, "code": code, "name": code, "type": "region", "regionId": None,
                "population": sum(a["population"] for a in force_areas if a["regionId"] == code), "populationYear": 2025}
               for code in region_codes]
    nation = {"id": monthly.NATION, "code": monthly.NATION, "name": "England and Wales", "type": "nation", "regionId": None,
              "population": 43000, "populationYear": 2025}
    official = {"areas": force_areas + regions + [nation], "generatedAt": "2026-10-22T00:00:00Z", "sources": []}
    counts = {code: {m: {cat: (1 if cat in ("all-crime", "burglary") else 0) for cat in monthly.CATEGORY_IDS} for m in months}
              for code in monthly.FORCES.values()}
    parsed = {"months": months, "counts": counts, "archiveSha256": "a" * 64, "entries": [], "rows": 1032, "excludedAsb": 0}
    record = {"url": "https://policeuk-data.s3.amazonaws.com/archive/2026-08.zip", "publishedAt": "2026-09-30"}
    return official, parsed, record


def build(official, parsed, record):
    return monthly.build_dataset(official, parsed, record, "2026-08-01", "b" * 64)[0]


class MissingSubmissionTests(unittest.TestCase):
    def test_complete_rolling_year_sums_months_and_regions(self):
        data = build(*fixture())
        force = next(a for a in data["areas"] if a["type"] == "force" and a["id"] != monthly.CITY)
        metric = force["metrics"]["burglary"]
        self.assertEqual(metric["count"], 12)
        self.assertEqual(metric["rate"], 12)
        self.assertEqual(metric["previousCount"], 12)
        self.assertEqual(metric["changePercent"], 0)
        self.assertEqual(len(metric["history"]), 13)
        self.assertEqual(len(metric["monthlyCounts"]), 24)
        national = next(a for a in data["areas"] if a["type"] == "nation")
        self.assertEqual(national["metrics"]["burglary"]["count"], 43 * 12)

    def test_missing_current_month_suppresses_force_region_and_nation(self):
        official, parsed, record = fixture()
        missing_code = "E23000005"
        del parsed["counts"][missing_code]["2026-08"]
        data = build(official, parsed, record)
        by_id = {a["id"]: a for a in data["areas"]}
        force = by_id[missing_code]
        for code in (missing_code, force["regionId"], monthly.NATION):
            self.assertFalse(by_id[code]["comparisonEligible"])
            self.assertIsNone(by_id[code]["metrics"]["all-crime"]["count"])
            self.assertIsNone(by_id[code]["metrics"]["burglary"]["rate"])
            self.assertIsNone(by_id[code]["metrics"]["burglary"]["changePercent"])
        self.assertEqual(force["metrics"]["burglary"]["previousCount"], 12)
        self.assertEqual(force["monthlyCoverage"]["missingForceMonths"], {missing_code: ["2026-08"]})
        self.assertTrue(by_id["E23000002"]["comparisonEligible"])

    def test_missing_previous_year_withholds_change_but_current_is_comparable(self):
        official, parsed, record = fixture()
        code = "E23000005"
        del parsed["counts"][code]["2024-09"]
        data = build(official, parsed, record)
        force = next(a for a in data["areas"] if a["id"] == code)
        self.assertTrue(force["comparisonEligible"])
        self.assertEqual(force["metrics"]["burglary"]["count"], 12)
        self.assertIsNone(force["metrics"]["burglary"]["previousCount"])
        self.assertIsNone(force["metrics"]["burglary"]["changePercent"])
        self.assertIsNone(force["metrics"]["burglary"]["history"][0]["count"])
        self.assertEqual(force["metrics"]["burglary"]["history"][-1]["count"], 12)

    def test_validator_rejects_partial_count_presented_as_zero(self):
        official, parsed, record = fixture()
        del parsed["counts"]["E23000005"]["2026-08"]
        data = build(official, parsed, record)
        force = next(a for a in data["areas"] if a["id"] == "E23000005")
        force["metrics"]["burglary"]["count"] = 0
        with self.assertRaisesRegex(ValueError, "Partial rolling-year"):
            monthly.validate_dataset(data)


class CsvSafetyTests(unittest.TestCase):
    def parse_rows(self, crime_types, reported="Cumbria Constabulary", observation="2026-08"):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / "source.zip"
            csv_text = io.StringIO(newline="")
            writer = csv.writer(csv_text)
            writer.writerow(["Month", "Reported by", "Crime type"])
            for crime in crime_types:
                writer.writerow([observation, reported, crime])
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("2026-08/2026-08-cumbria-street.csv", csv_text.getvalue())
                # These categories would fail parsing if NI or BTP were included.
                archive.writestr("2026-08/2026-08-northern-ireland-street.csv", "irrelevant")
                archive.writestr("2026-08/2026-08-btp-street.csv", "irrelevant")
            with patch.object(monthly, "CACHE", directory):
                return monthly.parse_archive(path, "2026-08", "a" * 64)

    def test_asb_excluded_and_btp_northern_ireland_not_counted(self):
        parsed = self.parse_rows(["Burglary", "Anti-social behaviour", "Anti-social behaviour"])
        values = parsed["counts"]["E23000002"]["2026-08"]
        self.assertEqual(values["all-crime"], 1)
        self.assertEqual(values["burglary"], 1)
        self.assertEqual(parsed["excludedAsb"], 2)
        self.assertEqual(len(parsed["entries"]), 1)

    def test_unknown_category_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown Police.uk crime category"):
            self.parse_rows(["New category requiring review"])

    def test_wrong_reported_force_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "reporting force"):
            self.parse_rows(["Burglary"], reported="Metropolitan Police Service")

    def test_wrong_observation_month_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "observation month"):
            self.parse_rows(["Burglary"], observation="2026-07")

    def test_header_only_csv_is_missing_not_zero(self):
        with self.assertRaisesRegex(ValueError, "no usable current"):
            self.parse_rows([])


if __name__ == "__main__":
    unittest.main()
