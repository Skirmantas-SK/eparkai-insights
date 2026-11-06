"""Offline regression tests: run with python -m unittest discover -s tests."""

from datetime import date, datetime
from pathlib import Path
import sys
import types
import unittest

# Load the provider package without importing Home Assistant's setup module.
ROOT = Path(__file__).resolve().parents[1]
if "custom_components.eparkai_insights" not in sys.modules:
    package = types.ModuleType("custom_components.eparkai_insights")
    package.__path__ = [str(ROOT / "custom_components" / "eparkai_insights")]
    sys.modules["custom_components.eparkai_insights"] = package

from custom_components.eparkai_insights.production import (
    MONTHS, ParseError, TZ, expected_intervals, parse_intervals, select_production,
)
from custom_components.eparkai_insights.client import AuthenticationError, EParkaiClient, Forms


def payload(samples):
    return [{"command": "settings", "settings": {"product_generation_form": {
        "labels": [[str(stamp.year), MONTHS[stamp.month - 1], str(stamp.day), stamp.strftime("%H:%M")] for stamp, _ in samples],
        "data": [value for _, value in samples],
    }}}]


def day_samples(day, cadence=60, energy=1):
    return [(stamp, energy) for stamp in expected_intervals(day, cadence)]


class ProductionTests(unittest.TestCase):
    def select(self, samples, cadence=60, now=None):
        return select_production(parse_intervals(payload(samples)), cadence, now or datetime(2026, 11, 6, 12, tzinfo=TZ))

    def test_latest_incomplete_day_falls_back_but_hour_is_independent(self):
        samples = day_samples(date(2026, 11, 4)) + day_samples(date(2026, 11, 5))[:3]
        selected = self.select(samples)
        self.assertEqual(selected["daily"]["date"], "2026-11-04")
        self.assertEqual(selected["daily"]["energy"], 24)
        self.assertEqual(selected["hourly"]["start"], "2026-11-05T02:00:00+02:00")

    def test_zero_is_valid_and_latest(self):
        samples = day_samples(date(2026, 11, 5), energy=0)
        selected = self.select(samples)
        self.assertEqual(selected["daily"]["energy"], 0)
        self.assertEqual(selected["hourly"]["energy"], 0)

    def test_invalid_values_never_become_zero(self):
        for value in (None, True, False, -1, "bad", float("nan"), float("inf"), {}, ""):
            with self.subTest(value=value):
                samples = day_samples(date(2026, 11, 5))
                samples[-1] = (samples[-1][0], value)
                selected = self.select(samples)
                self.assertIsNone(selected["daily"])
                self.assertEqual(selected["hourly"]["start"], "2026-11-05T22:00:00+02:00")

    def test_today_is_never_daily_and_unfinished_hour_is_not_selected(self):
        samples = day_samples(date(2026, 11, 6))
        selected = self.select(samples, now=datetime(2026, 11, 6, 12, 30, tzinfo=TZ))
        self.assertIsNone(selected["daily"])
        self.assertEqual(selected["hourly"]["start"], "2026-11-06T11:00:00+02:00")

    def test_subhourly_hour_sums_all_intervals(self):
        for cadence in (15, 30):
            with self.subTest(cadence=cadence):
                samples = day_samples(date(2026, 11, 5), cadence, 0.25)
                selected = self.select(samples, cadence)
                self.assertEqual(selected["hourly"]["energy"], 60 / cadence * 0.25)
                self.assertEqual(selected["daily"]["energy"], 1440 / cadence * 0.25)
                incomplete = self.select(samples[:-1], cadence)
                self.assertIsNone(incomplete["daily"])
                self.assertEqual(incomplete["hourly"]["start"], "2026-11-05T22:00:00+02:00")

    def test_duplicates_reject_day_and_affected_hour(self):
        samples = day_samples(date(2026, 11, 5))
        selected = self.select(samples + [samples[-1]])
        self.assertIsNone(selected["daily"])
        self.assertEqual(selected["hourly"]["start"], "2026-11-05T22:00:00+02:00")

    def test_off_cadence_samples_reject_day_and_hour(self):
        samples = day_samples(date(2026, 11, 5))
        samples.append((datetime(2026, 11, 5, 23, 15, tzinfo=TZ), 1))
        selected = self.select(samples)
        self.assertIsNone(selected["daily"])
        self.assertEqual(selected["hourly"]["start"], "2026-11-05T22:00:00+02:00")

    def test_daylight_saving_days_have_23_or_25_hours(self):
        for day, count in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            for cadence in (15, 30, 60):
                with self.subTest(day=day, cadence=cadence):
                    selected = self.select(day_samples(day, cadence), cadence)
                    self.assertEqual(selected["daily"]["interval_count"], count * 60 // cadence)
                    self.assertEqual(selected["daily"]["energy"], count * 60 // cadence)

    def test_repeated_hour_has_distinct_offsets_and_uses_latest_occurrence(self):
        samples = day_samples(date(2026, 10, 25))[:5]
        samples[-1] = (samples[-1][0], 2)
        selected = self.select(samples)
        self.assertEqual(selected["hourly"]["start"], "2026-10-25T03:00:00+02:00")
        self.assertEqual(selected["hourly"]["energy"], 2)
        # One ambiguous label cannot tell us which physical hour it belongs to.
        selected = self.select(samples[:-1])
        self.assertEqual(selected["hourly"]["start"], "2026-10-25T02:00:00+03:00")

    def test_year_boundary_and_unsorted_days(self):
        samples = day_samples(date(2025, 12, 31)) + day_samples(date(2025, 12, 30))
        selected = self.select(samples, now=datetime(2026, 1, 1, tzinfo=TZ))
        self.assertEqual(selected["daily"]["date"], "2025-12-31")

    def test_revisions_are_replacements(self):
        samples = day_samples(date(2026, 11, 5))
        self.assertEqual(self.select(samples)["daily"]["energy"], 24)
        samples[-1] = (samples[-1][0], 3)
        self.assertEqual(self.select(samples)["daily"]["energy"], 26)

    def test_schema_failures(self):
        for value in ({}, [], [None], payload([]) * 2, [{"command": "settings", "settings": {"product_generation_form": {"labels": [], "data": [1]}}}]):
            with self.subTest(value=value):
                with self.assertRaises(ParseError):
                    parse_intervals(value)

    def test_empty_valid_series(self):
        self.assertEqual(self.select([]), {"daily": None, "hourly": None})

    def test_non_chart_settings_do_not_make_valid_series_ambiguous(self):
        samples = day_samples(date(2026, 11, 5))
        response = payload(samples)
        for placeholder in (None, False, {}, {"form_id": "product_generation_form"}):
            response.append({"command": "settings", "settings": {"product_generation_form": placeholder}})
        self.assertEqual(len(parse_intervals(response)), 24)
        with self.assertRaisesRegex(ParseError, "Multiple generation series"):
            parse_intervals(response + payload(samples))

    def test_joined_label_and_month_typo(self):
        value = payload([(datetime(2026, 9, 1), "0.12")])
        value[0]["settings"]["product_generation_form"]["labels"] = ["2026 Rugsėo 01 00:00"]
        parsed = parse_intervals(value)
        self.assertEqual(parsed[0][0], datetime(2026, 9, 1))
        self.assertEqual(parsed[0][1], 0.12)


def form(form_id, token="fresh"):
    return f'<form><input name="form_id" value="{form_id}"><input name="form_token" value="{token}"></form>'


class Response:
    def __init__(self, text="", data=None, status=200):
        self.text, self.data, self.status_code = text, data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError("HTTP failure")

    def json(self):
        if self.data is None:
            raise ValueError("Invalid JSON")
        return self.data


class Session:
    def __init__(self, responses):
        self.responses, self.calls, self.headers = list(responses), [], {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


class ClientTests(unittest.TestCase):
    def client(self, responses):
        session = Session(responses)
        return EParkaiClient("test", "secret", "123", session), session

    def fetch(self, client, address="exact value"):
        return client.fetch("456", address, datetime(2026, 11, 6, tzinfo=TZ))

    def test_session_reuse_fresh_tokens_and_exact_address(self):
        client, session = self.client([Response(form("product_generation_form", "one")), Response(data=payload([])), Response(form("product_generation_form", "two")), Response(data=payload([]))])
        self.fetch(client)
        self.fetch(client, "another object")
        self.assertEqual(len(session.calls), 4)
        self.assertEqual(session.calls[1][2]["data"]["form_token"], "one")
        self.assertEqual(session.calls[3][2]["data"]["form_token"], "two")
        self.assertEqual(session.calls[3][2]["data"]["address"], "another object")
        self.assertFalse(session.calls[1][2]["allow_redirects"])
        self.assertEqual(session.calls[1][2]["timeout"], (10, 30))

    def test_full_login_retains_hidden_fields(self):
        client, session = self.client([Response(form("user_login_form")), Response(form("user_login_form", "login-token")), Response(form("product_generation_form")), Response(form("product_generation_form", "new-token")), Response(data=payload([]))])
        self.fetch(client)
        self.assertEqual(session.calls[2][2]["data"]["form_token"], "login-token")
        self.assertEqual(session.calls[2][2]["data"]["pass"], "secret")
        self.assertEqual(session.calls[-1][2]["data"]["form_token"], "new-token")

    def test_failed_login_is_not_repeated(self):
        client, session = self.client([Response(""), Response(form("user_login_form")), Response(form("user_login_form"))])
        for _ in range(2):
            with self.assertRaises(AuthenticationError):
                self.fetch(client)
        self.assertEqual(len(session.calls), 3)

    def test_ajax_redirect_or_login_page_is_auth_failure(self):
        for response in (Response(status=302), Response(form("user_login_form")), Response(status=403)):
            with self.subTest(status=response.status_code):
                client, _ = self.client([Response(form("product_generation_form")), response])
                with self.assertRaises(AuthenticationError):
                    self.fetch(client)

    def test_malformed_json(self):
        client, _ = self.client([Response(form("product_generation_form")), Response("not JSON")])
        with self.assertRaises(ParseError):
            self.fetch(client)

    def test_missing_login_form_never_posts_credentials(self):
        client, session = self.client([Response(""), Response(form("other_form"))])
        with self.assertRaises(AuthenticationError):
            self.fetch(client)
        self.assertTrue(all(call[0] == "GET" for call in session.calls))

    def test_blank_address_is_omitted(self):
        client, session = self.client([Response(form("product_generation_form")), Response(data=payload([]))])
        self.fetch(client, "")
        self.assertNotIn("address", session.calls[-1][2]["data"])

    def test_forms_do_not_mix_fields_between_forms(self):
        parsed = Forms(form("other", "wrong") + form("product_generation_form", "a&amp;b"))
        self.assertEqual(parsed.find("product_generation_form")["form_token"], "a&b")


if __name__ == "__main__":
    unittest.main()
