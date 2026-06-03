"""
filters/news.py — ForexFactory economic calendar news filter.

Fetches high-impact news events and determines whether trades
should be blocked or lot sizes reduced based on upcoming events.
"""

import os
import logging
import time as _time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

import requests

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)

# Cache for the news calendar (refreshed once per day)
_cached_events = []
_cache_timestamp = None
CACHE_TTL_HOURS = 12

# ForexFactory calendar URLs (primary + fallback)
FF_CALENDAR_URLS = [
    "https://www.forexfactory.com/ff_calendar_thisweek.xml",
    "https://nfs.faireconomy.media/ff_calendar_thisweek.xml",
]


class NewsEvent:
    """Represents a single economic calendar event."""

    def __init__(self, title, currency, impact, event_time):
        self.title = title
        self.currency = currency.upper() if currency else ""
        self.impact = impact.lower() if impact else "low"
        self.event_time = event_time  # datetime (UTC)

    def __repr__(self):
        return (
            f"NewsEvent({self.title}, {self.currency}, "
            f"{self.impact}, {self.event_time})"
        )


def _fetch_calendar():
    """
    Fetch the ForexFactory economic calendar XML.

    Tries multiple URLs with fallback.

    Returns:
        List of NewsEvent objects, or empty list on failure.
    """
    for url in FF_CALENDAR_URLS:
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/xml, text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return _parse_xml(resp.text)
            elif resp.status_code == 403:
                logger.warning(
                    f"News calendar HTTP 403 (Forbidden) from {url} — "
                    f"assuming no high-impact news, trading allowed"
                )
                # Don't try other URLs, just allow trading
                return []
            else:
                logger.warning(
                    f"News calendar HTTP {resp.status_code} from {url}"
                )
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch news calendar from {url}: {e}")

    logger.warning("All news calendar sources failed. Allowing trading (no news filter).")
    return []


def _parse_xml(xml_text):
    """
    Parse the ForexFactory XML calendar into NewsEvent objects.

    Expected XML structure:
    <weeklyevents>
      <event>
        <title>Non-Farm Payrolls</title>
        <country>USD</country>
        <date>06-01-2026</date>
        <time>8:30am</time>
        <impact>High</impact>
        ...
      </event>
    </weeklyevents>

    Returns:
        List of NewsEvent objects.
    """
    events = []
    try:
        root = ElementTree.fromstring(xml_text)
        for event_el in root.findall(".//event"):
            title = _get_text(event_el, "title")
            currency = _get_text(event_el, "country")
            impact = _get_text(event_el, "impact")
            date_str = _get_text(event_el, "date")
            time_str = _get_text(event_el, "time")

            event_time = _parse_event_datetime(date_str, time_str)
            if event_time is None:
                continue

            events.append(NewsEvent(title, currency, impact, event_time))

    except ElementTree.ParseError as e:
        logger.error(f"Failed to parse news calendar XML: {e}")

    logger.info(f"Parsed {len(events)} news events from calendar")
    return events


def _get_text(element, tag):
    """Safely get text content of a child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def _parse_event_datetime(date_str, time_str):
    """
    Parse date + time strings from ForexFactory format.

    Args:
        date_str: e.g., "06-01-2026" or "Jun 1"
        time_str: e.g., "8:30am", "Tentative", "All Day"

    Returns:
        datetime (UTC) or None if unparseable.
    """
    if not date_str:
        return None

    # Skip tentative/all-day events
    if not time_str or time_str.lower() in ("tentative", "all day", ""):
        return None

    try:
        # Try MM-DD-YYYY format
        for fmt in ("%m-%d-%Y %I:%M%p", "%m-%d-%Y %I:%M %p"):
            try:
                dt = datetime.strptime(
                    f"{date_str} {time_str.upper()}",
                    fmt
                )
                # ForexFactory times are Eastern Time (ET).
                # Convert to UTC: ET = UTC-4 (EDT) or UTC-5 (EST)
                # Use -4 as approximation during most of the year
                dt = dt.replace(tzinfo=timezone(timedelta(hours=-4)))
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue

        # Try "Mon DD" format with current year
        for fmt in ("%b %d %I:%M%p", "%b %d %I:%M %p"):
            try:
                dt = datetime.strptime(
                    f"{date_str} {time_str.upper()}",
                    fmt
                )
                dt = dt.replace(year=datetime.now().year)
                dt = dt.replace(tzinfo=timezone(timedelta(hours=-4)))
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue

    except Exception as e:
        logger.debug(f"Could not parse event datetime: {date_str} {time_str}: {e}")

    return None


def _get_events():
    """
    Get the cached events list, refreshing if stale.

    Returns:
        List of NewsEvent objects.
    """
    global _cached_events, _cache_timestamp

    now = datetime.now(timezone.utc)

    if _cache_timestamp is not None:
        age_hours = (now - _cache_timestamp).total_seconds() / 3600
        if age_hours < CACHE_TTL_HOURS:
            return _cached_events

    logger.info("Refreshing news calendar cache...")
    _cached_events = _fetch_calendar()
    _cache_timestamp = now
    return _cached_events


def should_block_trade(symbol, current_utc=None):
    """
    Check if a trade should be blocked or lot size reduced due to news.

    Logic:
        🔴 High impact within ±30min → BLOCK all trades for affected currency
        🟠 Medium impact within ±30min → REDUCE lot by 50%
        🟡 Low impact → Trade normally

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        current_utc: Current UTC datetime (defaults to now)

    Returns:
        (blocked: bool, reason: str, lot_multiplier: float)
        lot_multiplier: 1.0 = normal, 0.5 = reduced, 0.0 = blocked
    """
    if current_utc is None:
        current_utc = datetime.now(timezone.utc)

    events = _get_events()
    if not events:
        return False, "No news data available", 1.0

    window = timedelta(minutes=config.NEWS_WINDOW_MINUTES)

    # Find which currencies affect this symbol
    affected_currencies = set()
    for currency, instruments in config.CURRENCY_INSTRUMENT_MAP.items():
        if symbol in instruments:
            affected_currencies.add(currency)

    # Check each event
    for event in events:
        if event.currency not in affected_currencies:
            continue

        if event.event_time is None:
            continue

        time_diff = abs((event.event_time - current_utc).total_seconds())
        within_window = time_diff <= window.total_seconds()

        if not within_window:
            continue

        # High impact → block
        if event.impact in ("high", "red"):
            reason = (
                f"🔴 HIGH IMPACT NEWS: {event.title} ({event.currency}) "
                f"at {event.event_time.strftime('%H:%M UTC')} — "
                f"trade blocked for {symbol}"
            )
            logger.warning(reason)
            return True, reason, 0.0

        # Medium impact → reduce lot
        if event.impact in ("medium", "orange"):
            reason = (
                f"🟠 MEDIUM IMPACT NEWS: {event.title} ({event.currency}) "
                f"at {event.event_time.strftime('%H:%M UTC')} — "
                f"lot reduced 50% for {symbol}"
            )
            logger.info(reason)
            return False, reason, 0.5

    return False, "No impactful news within window", 1.0
