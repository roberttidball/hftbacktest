"""Fetch macro-event blackout dates for hftbacktest experiments.

High-frequency strategies often behave differently around scheduled macro
releases. This helper pulls the FXMacroData public release calendar and creates
a set of tier-one USD dates that can be used to segment replay results or pause
new quoting during event windows.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from typing import Any, Dict, Iterable, List, Set
from urllib.parse import urlencode
from urllib.request import urlopen


FXMD_CALENDAR_URL = "https://fxmacrodata.com/api/v1/calendar/{currency}"


def fetch_release_events(
    currency: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    params = urlencode({"start_date": start_date, "end_date": end_date})
    url = f"{FXMD_CALENDAR_URL.format(currency=currency.upper())}?{params}"

    with urlopen(url, timeout=20) as response:
        payload = json.load(response)

    return payload.get("data", [])


def build_blackout_dates(
    events: Iterable[Dict[str, Any]],
    min_market_tier: int = 1,
    window_days: int = 0,
) -> Set[str]:
    blackout_dates: Set[str] = set()

    for event in events:
        if not event.get("release_date_confirmed"):
            continue

        market_tier = event.get("market_tier")
        if market_tier is None or int(market_tier) > min_market_tier:
            continue

        announcement_ts = event.get("announcement_datetime")
        if announcement_ts is None:
            continue

        event_date = datetime.fromtimestamp(
            int(announcement_ts),
            tz=timezone.utc,
        ).date()
        for offset in range(-window_days, window_days + 1):
            blackout_dates.add((event_date + timedelta(days=offset)).isoformat())

    return blackout_dates


def timestamp_ns_to_date(timestamp_ns: int) -> str:
    timestamp_seconds = timestamp_ns / 1_000_000_000
    return datetime.fromtimestamp(timestamp_seconds, timezone.utc).date().isoformat()


def can_quote(timestamp_ns: int, blackout_dates: Set[str]) -> bool:
    return timestamp_ns_to_date(timestamp_ns) not in blackout_dates


# Example:
#
# events = fetch_release_events("USD", "2026-07-01", "2026-07-31")
# blackout_dates = build_blackout_dates(events, min_market_tier=1, window_days=0)
# if not can_quote(hbt.current_timestamp, blackout_dates):
#     continue
