"""Fetch macro-event blackout dates for hftbacktest experiments."""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
from typing import Any, Dict, Iterable, List, Set
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen


FXMD_CALENDAR_URL = "https://fxmacrodata.com/api/v1/calendar/{currency}"
FXMD_HOST = "fxmacrodata.com"


def normalize_currency(currency: str) -> str:
    """Return a normalized ISO currency code for the FXMacroData API path."""
    currency_code = currency.strip().upper()
    if len(currency_code) != 3 or not currency_code.isalpha():
        raise ValueError("currency must be a three-letter ISO currency code")
    return currency_code


def fetch_release_events(
    currency: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Fetch FXMacroData release-calendar events for a currency and date range."""
    params = urlencode({"start_date": start_date, "end_date": end_date})
    url = f"{FXMD_CALENDAR_URL.format(currency=normalize_currency(currency))}?{params}"
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != FXMD_HOST:
        raise ValueError("release calendar URL must use the FXMacroData HTTPS host")

    request = Request(url, headers={"User-Agent": "hftbacktest-fxmacrodata-example"})
    with urlopen(request, timeout=20) as response:  # nosec B310
        payload = json.load(response)

    return payload.get("data", [])


def build_blackout_dates(
    events: Iterable[Dict[str, Any]],
    min_market_tier: int = 1,
    window_days: int = 0,
) -> Set[str]:
    """Build a set of UTC calendar dates around confirmed macro events."""
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
    """Convert a nanosecond timestamp to a UTC calendar date string."""
    timestamp_seconds = timestamp_ns / 1_000_000_000
    return datetime.fromtimestamp(timestamp_seconds, timezone.utc).date().isoformat()


def can_quote(timestamp_ns: int, blackout_dates: Set[str]) -> bool:
    """Return whether a timestamp falls outside the macro-event blackout dates."""
    return timestamp_ns_to_date(timestamp_ns) not in blackout_dates
