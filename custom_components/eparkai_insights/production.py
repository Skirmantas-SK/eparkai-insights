"""Parse provider intervals and select complete Lithuanian days and hours.

Independent of Home Assistant so the data rules can be tested in isolation.
Labels are interpreted as interval starts, as specified in EPARKAI_INTEGRATION.md.
"""

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Vilnius")
UTC = timezone.utc
MONTHS = (
    "Sausio", "Vasario", "Kovo", "Balandžio", "Gegužės", "Birželio",
    "Liepos", "Rugpjūčio", "Rugsėjo", "Spalio", "Lapkričio", "Gruodžio",
)


class ParseError(ValueError):
    """The provider response is not a supported generation series."""


def parse_intervals(payload):
    """Return local naive labels and energy, preserving invalid values as None."""
    if not isinstance(payload, list):
        raise ParseError("Expected Drupal command array")
    series = []
    for command in payload:
        if not isinstance(command, dict) or command.get("command") != "settings":
            continue
        settings = command.get("settings")
        if isinstance(settings, dict):
            candidate = settings.get("product_generation_form")
            # Drupal may also emit form settings without chart data. Count only
            # actual series, matching the supplied reference implementation.
            if isinstance(candidate, dict) and "labels" in candidate and "data" in candidate:
                series.append(candidate)
    if not series:
        raise ParseError("No generation series in the portal response")
    if len(series) != 1:
        raise ParseError("Multiple generation series in the portal response")
    labels, values = series[0].get("labels"), series[0].get("data")
    if not isinstance(labels, list) or not isinstance(values, list) or len(labels) != len(values):
        raise ParseError("Invalid labels/data arrays")
    result = []
    for label, value in zip(labels, values):
        try:
            raw = " ".join(label) if isinstance(label, list) else label
            year, month, day, clock = raw.split()
            month_number = MONTHS.index(month.replace("Rugsėo", "Rugsėjo")) + 1
            stamp = datetime.strptime(f"{year}-{month_number}-{day} {clock}", "%Y-%m-%d %H:%M")
        except (ValueError, TypeError, AttributeError) as err:
            raise ParseError("Invalid generation timestamp") from err
        energy = None
        if not isinstance(value, bool) and isinstance(value, (int, float, str)):
            try:
                number = float(value)
                if math.isfinite(number) and number >= 0:
                    energy = number
            except (ValueError, OverflowError):
                pass
        result.append((stamp, energy, raw))
    return result


def expected_intervals(day, cadence):
    """Walk UTC to retain both autumn hours and skip the absent spring hour."""
    start = datetime.combine(day, time(), TZ).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(), TZ).astimezone(UTC)
    result = []
    while start < end:
        result.append(start.astimezone(TZ))
        start += timedelta(minutes=cadence)
    return result


def select_production(intervals, cadence, now):
    """Select newest complete past day and independently newest completed hour."""
    if cadence not in (15, 30, 60):
        raise ValueError("Unsupported interval cadence")
    now = now.astimezone(TZ)
    days = defaultdict(list)
    for stamp, energy, raw in intervals:
        days[stamp.date()].append((stamp, energy, raw))
    daily = hourly = None
    for day in sorted(days, reverse=True):
        if day > now.date():
            continue
        expected = expected_intervals(day, cadence)
        expected_counts = Counter(stamp.replace(tzinfo=None) for stamp in expected)
        observed = defaultdict(list)
        for stamp, value, raw in days[day]:
            observed[stamp].append((value, raw))
        observed_counts = Counter({stamp: len(values) for stamp, values in observed.items()})
        # A repeated DST label is usable only if both occurrences are supplied.
        # Provider order assigns the first to summer time and the second to winter time.
        occurrences = Counter()
        hours = defaultdict(list)
        valid = []
        for stamp in expected:
            naive = stamp.replace(tzinfo=None)
            index = occurrences[naive]
            occurrences[naive] += 1
            sample = None
            if observed_counts[naive] == expected_counts[naive]:
                sample = observed[naive][index]
            hour_start = stamp.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            hours[hour_start].append((stamp, sample))
            valid.append(sample is not None and sample[0] is not None)
        if daily is None and day < now.date() and observed_counts == expected_counts and all(valid):
            daily = {
                "energy": math.fsum(value for _, value, _ in days[day]),
                "date": day.isoformat(),
                "interval_count": len(expected),
                "last_interval": expected[-1].isoformat(),
            }
        if hourly is None:
            for start, samples in sorted(hours.items(), reverse=True):
                if start + timedelta(hours=1) > now.astimezone(UTC):
                    continue
                # Reject off-cadence extras in this local clock hour, too.
                local = start.astimezone(TZ)
                if any(s.hour == local.hour and s not in expected_counts for s in observed):
                    continue
                if len(samples) != 60 // cadence or any(s is None or s[0] is None for _, s in samples):
                    continue
                hourly = {
                    "energy": math.fsum(s[0] for _, s in samples),
                    "start": local.isoformat(),
                    "end": (start + timedelta(hours=1)).astimezone(TZ).isoformat(),
                    "source_labels": [s[1] for _, s in samples],
                    "interval_count": len(samples),
                }
                break
    return {"daily": daily, "hourly": hourly}
