"""
filters/session.py — Trading session filter.

Determines whether an instrument is allowed to trade based on the current
UTC time and the instrument's assigned trading sessions.
"""

import logging
from datetime import datetime, timezone, time as dtime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


def _parse_time(time_str):
    """Parse "HH:MM" string to datetime.time object."""
    parts = time_str.split(":")
    return dtime(int(parts[0]), int(parts[1]))


def _is_time_in_session(current_time, session_start, session_end):
    """
    Check if current_time is within [session_start, session_end].

    Handles sessions that cross midnight (e.g., 22:00–06:00) —
    though not needed for current config, included for robustness.

    Args:
        current_time: datetime.time (UTC)
        session_start: datetime.time
        session_end: datetime.time

    Returns:
        True if within session.
    """
    if session_start <= session_end:
        # Normal session (e.g., 08:00–16:00)
        return session_start <= current_time <= session_end
    else:
        # Overnight session (e.g., 22:00–06:00)
        return current_time >= session_start or current_time <= session_end


def is_session_active(symbol, current_utc=None):
    """
    Check if the given instrument is in an active trading session.

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        current_utc: datetime in UTC (defaults to now)

    Returns:
        (active: bool, session_name: str or None, reason: str)
    """
    if current_utc is None:
        current_utc = datetime.now(timezone.utc)

    current_time = current_utc.time()

    # Get allowed sessions for this instrument
    allowed_sessions = config.INSTRUMENT_SESSIONS.get(symbol, [])

    if not allowed_sessions:
        return False, None, f"No sessions defined for {symbol}"

    for session_name in allowed_sessions:
        session_config = config.SESSIONS.get(session_name)
        if session_config is None:
            continue

        session_start = _parse_time(session_config["start"])
        session_end = _parse_time(session_config["end"])

        if _is_time_in_session(current_time, session_start, session_end):
            return True, session_name, f"Active in {session_name} session"

    # Not in any allowed session
    active_session_names = ", ".join(allowed_sessions)
    return (
        False,
        None,
        f"{symbol} only trades during: {active_session_names}. "
        f"Current UTC time: {current_time.strftime('%H:%M')}"
    )
