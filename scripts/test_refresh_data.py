"""Offline integrity tests for a public comparison built from mutable statistics."""

import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("refresh_data.py")
SPEC = importlib.util.spec_from_file_location("refresh_data", SCRIPT)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


class SourceTransformTests(unittest.TestCase):
    def test_financial_quarter_changes_calendar_year(self):
        self.assertEqual(refresh.quarter_end("2025/26", 1), dt.date(2025, 6, 30))
        self.assertEqual(refresh.quarter_end("2025/26", 4), dt.date(2026, 3, 31))

    def test_fraud_does_not_enter_geographical_crime_totals(self):
        self.assertEqual(refresh.categories_for_offence("Fraud offences", "Fraud: Action Fraud"), [])
        self.assertEqual(refresh.categories_for_offence("Theft offences", "Shoplifting"), ["all-crime", "shoplifting"])

    def test_burglary_history_handles_offence_reclassification(self):
        for subgroup in ("Domestic burglary", "Non-domestic burglary", "Residential burglary", "Non-residential burglary"):
            self.assertEqual(refresh.categories_for_offence("Theft offences", subgroup), ["all-crime", "burglary"])

    def test_unknown_population_or_stale_denominator_fails(self):
        with self.assertRaisesRegex(ValueError, "No actual"):
            refresh.population_for("E23000099", 2025, {}, {})
        with self.assertRaisesRegex(ValueError, "out of date"):
            refresh.population_for("E23000001", 2025, {"E23000001": {2020: 10}}, {})


class PublishedIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((refresh.OUTPUT / "crime.json").read_text())

    def test_actual_snapshot_has_complete_coverage_and_reconciles(self):
        refresh.validate_dataset(self.data)

    def test_missing_force_is_not_treated_as_zero(self):
        bad = copy.deepcopy(self.data)
        bad["areas"] = [a for a in bad["areas"] if a["id"] != "E23000005"]
        with self.assertRaises(ValueError):
            refresh.validate_dataset(bad)

    def test_incorrect_denominator_cannot_publish(self):
        bad = copy.deepcopy(self.data)
        area = next(a for a in bad["areas"] if a["id"] == "E23000005")
        area["population"] *= 2
        with self.assertRaisesRegex(ValueError, "population-normalised"):
            refresh.validate_dataset(bad)

    def test_city_of_london_cannot_enter_rate_rankings(self):
        bad = copy.deepcopy(self.data)
        city = next(a for a in bad["areas"] if a["id"] == refresh.CITY)
        city["comparisonEligible"] = True
        with self.assertRaisesRegex(ValueError, "City of London"):
            refresh.validate_dataset(bad)

    def test_history_endpoint_must_match_latest_count(self):
        bad = copy.deepcopy(self.data)
        bad["areas"][0]["metrics"]["all-crime"]["history"][-1]["count"] += 1
        with self.assertRaisesRegex(ValueError, "Trend endpoint"):
            refresh.validate_dataset(bad)

    def test_failed_fetch_preserves_both_public_snapshots(self):
        before = {filename: (refresh.OUTPUT / filename).read_bytes()
                  for filename in ("crime.json", "source-manifest.json")}
        with patch.object(refresh, "discover_sources", side_effect=RuntimeError("source unavailable")):
            with self.assertRaisesRegex(RuntimeError, "source unavailable"):
                refresh.main([])
        for filename, content in before.items():
            self.assertEqual((refresh.OUTPUT / filename).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
