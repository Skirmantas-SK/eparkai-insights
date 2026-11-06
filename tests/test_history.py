"""Regression tests for overnight batches, gaps, revisions, and DST."""

from datetime import date, datetime, timedelta, timezone
import unittest

from test_production import day_samples, payload
from custom_components.eparkai_insights.history import build_statistics
from custom_components.eparkai_insights.production import TZ, parse_intervals, select_production


def recorded(rows):
    return [{**row, "start": row["start"].timestamp()} for row in rows]


class HistoryTests(unittest.TestCase):
    def hours(self, day=date(2026, 11, 4), cadence=60):
        return select_production(parse_intervals(payload(day_samples(day, cadence))), cadence,
                                 datetime(2026, 11, 6, 12, tzinfo=TZ))["hours"]

    def test_overnight_batch_is_backdated_to_each_source_hour(self):
        hours = self.hours()
        rows = build_statistics(hours, [])
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0]["start"], datetime(2026, 11, 3, 22, tzinfo=timezone.utc))
        self.assertEqual(rows[-1]["start"], datetime(2026, 11, 4, 21, tzinfo=timezone.utc))
        self.assertEqual([row["state"] for row in rows], [1] * 24)
        self.assertEqual(rows[-1]["sum"], 24)

    def test_reimport_and_restart_do_not_double_count(self):
        hours = self.hours()
        first = build_statistics(hours, [], previous_sum=123)
        self.assertEqual(build_statistics(hours, recorded(first)), first)
        self.assertEqual(first[-1]["sum"], 147)

    def test_correction_recomputes_later_recorded_hours(self):
        hours = self.hours()
        first = build_statistics(hours, [], previous_sum=10)
        correction = [{**hours[5], "energy": 4}]
        revised = build_statistics(correction, recorded(first)[5:])
        self.assertEqual(len(revised), 19)
        self.assertEqual(revised[0]["state"], 4)
        self.assertEqual(revised[-1]["state"], 1)
        self.assertEqual(revised[-1]["sum"], 37)
        self.assertEqual(build_statistics(correction, recorded(revised)), revised)

    def test_late_gap_fill_keeps_existing_later_energy(self):
        hours = self.hours()
        first = build_statistics([hours[0], hours[2]], [])
        revised = build_statistics([hours[1]], recorded(first)[1:])
        self.assertEqual([row["sum"] for row in revised], [2, 3])

    def test_missing_values_do_not_erase_known_history(self):
        hours = self.hours()
        first = build_statistics(hours, [])
        revised = build_statistics([hours[0], hours[-1]], recorded(first))
        self.assertEqual(first, revised)

    def test_zero_energy_is_retained(self):
        hours = self.hours()
        hours[-1] = {**hours[-1], "energy": 0}
        rows = build_statistics(hours, [])
        self.assertEqual(rows[-1]["state"], 0)
        self.assertEqual(rows[-1]["sum"], rows[-2]["sum"])

    def test_new_window_after_outage_continues_previous_sum(self):
        rows = build_statistics(self.hours(), [], previous_sum=42)
        self.assertEqual(rows[0]["sum"], 43)
        self.assertEqual(rows[-1]["sum"], 66)

    def test_subhourly_and_daylight_saving(self):
        for day, count in ((date(2026, 3, 29), 23), (date(2026, 10, 25), 25)):
            for cadence in (15, 30, 60):
                with self.subTest(day=day, cadence=cadence):
                    hours = self.hours(day, cadence)
                    rows = build_statistics(hours, [])
                    self.assertEqual(len(rows), count)
                    self.assertEqual(len({row["start"] for row in rows}), count)
                    self.assertEqual(rows[-1]["sum"], count * 60 // cadence)
                    for first, second in zip(rows, rows[1:]):
                        self.assertEqual(second["start"] - first["start"], timedelta(hours=1))

    def test_latest_complete_day_has_full_hourly_curve(self):
        selected = select_production(parse_intervals(payload(day_samples(date(2026, 11, 4)))),
                                     60, datetime(2026, 11, 6, tzinfo=TZ))
        self.assertEqual(len(selected["daily"]["hours"]), 24)
        self.assertEqual(sum(row["energy"] for row in selected["daily"]["hours"]), selected["daily"]["energy"])
