"""Build idempotent hourly energy statistics, independent of Home Assistant."""

from datetime import datetime, timezone
import math


def build_statistics(hours, existing, previous_sum=0.0):
    """Replace revised hours and recompute sums through the existing later tail.

Existing rows start at the earliest incoming timestamp. Their state is interval
energy, not a meter reading. Keep valid recorded hours absent from a new response.
"""
    if not hours:
        return []
    incoming = {datetime.fromisoformat(row["start"]).timestamp(): row["energy"] for row in hours}
    earliest = min(incoming)
    existing = sorted((row for row in existing if row["start"] >= earliest), key=lambda row: row["start"])
    values = {}
    for row in existing:
        if row.get("state") is None or row.get("sum") is None:
            raise ValueError("Recorded hourly energy is missing state or sum")
        if not math.isfinite(row["state"]) or row["state"] < 0 or not math.isfinite(row["sum"]):
            raise ValueError("Recorded hourly energy is invalid")
        values[row["start"]] = row["state"]
    # The first existing sum minus that hour's energy is the total before this
    # window. If the window is entirely new, continue from the last recorded sum.
    total = existing[0]["sum"] - existing[0]["state"] if existing else previous_sum
    values.update(incoming)
    result = []
    for timestamp, energy in sorted(values.items()):
        total = math.fsum((total, energy))
        result.append({"start": datetime.fromtimestamp(timestamp, timezone.utc),
                       "state": energy, "sum": total})
    return result
