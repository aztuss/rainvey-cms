"""
broker/capital_api.py — Capital.com REST API wrapper.

Handles authentication, session management, price data retrieval,
position management, and order placement with retry logic.
"""

import time
import logging
import requests
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


class CapitalAPI:
    """Wrapper for Capital.com REST API v1."""

    def __init__(self):
        self.base_url = config.BASE_URLS[config.ENVIRONMENT]
        self.api_key = config.API_KEY
        self.identifier = config.API_IDENTIFIER
        self.password = config.API_PASSWORD
        self.cst = None             # Client Session Token
        self.security_token = None  # X-SECURITY-TOKEN
        self.session_created_at = None
        self.session = requests.Session()

    # -------------------------------------------------------------------------
    #  Authentication
    # -------------------------------------------------------------------------
    def create_session(self):
        """Authenticate with Capital.com and obtain session tokens."""
        url = f"{self.base_url}/api/v1/session"
        headers = {
            "X-CAP-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "identifier": self.identifier,
            "password": self.password,
        }

        resp = self._request("POST", url, headers=headers, json=payload,
                              skip_auth=True)
        if resp is None:
            logger.error("Failed to create Capital.com session.")
            return False

        self.cst = resp.headers.get("CST")
        self.security_token = resp.headers.get("X-SECURITY-TOKEN")
        self.session_created_at = datetime.now(timezone.utc)
        logger.info("Capital.com session created successfully.")
        return True

    def _ensure_session(self):
        """Refresh session if tokens are missing or expired (>9 min)."""
        if self.cst is None or self.security_token is None:
            return self.create_session()

        elapsed = (datetime.now(timezone.utc) - self.session_created_at).total_seconds()
        if elapsed > 540:  # Refresh before 10-min timeout
            logger.info("Session nearing expiry, refreshing...")
            return self.create_session()
        return True

    def _auth_headers(self):
        """Return authentication headers for API requests."""
        return {
            "X-CAP-API-KEY": self.api_key,
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token,
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------------------------
    #  Core HTTP request with retry logic
    # -------------------------------------------------------------------------
    def _request(self, method, url, headers=None, json=None, params=None,
                 skip_auth=False):
        """
        Execute an HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Full URL
            headers: Optional headers dict (if None, uses auth headers)
            json: JSON body
            params: Query parameters
            skip_auth: If True, don't add auth headers (used for login)

        Returns:
            requests.Response on success, None on failure.
        """
        if headers is None and not skip_auth:
            self._ensure_session()
            headers = self._auth_headers()

        for attempt in range(1, config.API_MAX_RETRIES + 1):
            try:
                resp = self.session.request(
                    method, url,
                    headers=headers,
                    json=json,
                    params=params,
                    timeout=config.API_TIMEOUT,
                )
                if resp.status_code in (200, 201):
                    return resp

                # Rate limited
                if resp.status_code == 429:
                    wait = config.API_RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                # Unauthorized — refresh session and retry
                if resp.status_code == 401 and not skip_auth:
                    logger.warning("Session expired, re-authenticating...")
                    self.create_session()
                    headers = self._auth_headers()
                    continue

                logger.error(
                    f"API error {resp.status_code}: {resp.text} "
                    f"[{method} {url}] (attempt {attempt})"
                )
                if attempt < config.API_MAX_RETRIES:
                    time.sleep(config.API_RETRY_DELAY * attempt)

            except requests.exceptions.RequestException as e:
                logger.error(f"Request exception: {e} (attempt {attempt})")
                if attempt < config.API_MAX_RETRIES:
                    time.sleep(config.API_RETRY_DELAY * attempt)

        logger.error(f"All {config.API_MAX_RETRIES} retries exhausted for {method} {url}")
        return None

    # -------------------------------------------------------------------------
    #  Price Data
    # -------------------------------------------------------------------------
    def get_prices(self, epic, resolution="HOUR", max_bars=300):
        """
        Fetch OHLCV candles for an instrument.

        Args:
            epic: Instrument epic/symbol (e.g., "EURUSD")
            resolution: Candle resolution — "HOUR" (H1), "HOUR_4" (H4), "DAY", etc.
            max_bars: Number of candles to fetch (max ~1000 per request)

        Returns:
            List of candle dicts or empty list on failure.
        """
        url = f"{self.base_url}/api/v1/prices/{epic}"
        params = {
            "resolution": resolution,
            "max": max_bars,
        }
        resp = self._request("GET", url, params=params)
        if resp is None:
            return []

        data = resp.json()
        return data.get("prices", [])

    def get_prices_range(self, epic, resolution, from_date, to_date):
        """
        Fetch OHLCV candles for a date range (for backtesting).

        Args:
            epic: Instrument epic
            resolution: Candle resolution
            from_date: Start date string "YYYY-MM-DDTHH:MM:SS"
            to_date: End date string "YYYY-MM-DDTHH:MM:SS"

        Returns:
            List of candle dicts.
        """
        url = f"{self.base_url}/api/v1/prices/{epic}"
        params = {
            "resolution": resolution,
            "from": from_date,
            "to": to_date,
            "max": 1000,
        }
        resp = self._request("GET", url, params=params)
        if resp is None:
            return []

        data = resp.json()
        return data.get("prices", [])

    # -------------------------------------------------------------------------
    #  Positions
    # -------------------------------------------------------------------------
    def get_open_positions(self):
        """
        Get all currently open positions.

        Returns:
            List of position dicts or empty list.
        """
        url = f"{self.base_url}/api/v1/positions"
        resp = self._request("GET", url)
        if resp is None:
            return []

        data = resp.json()
        return data.get("positions", [])

    def place_order(self, epic, direction, size, stop_level=None,
                    profit_level=None):
        """
        Place a market order (open a position).

        Args:
            epic: Instrument epic
            direction: "BUY" or "SELL"
            size: Position size (in the instrument's unit)
            stop_level: Absolute stop-loss price
            profit_level: Absolute take-profit price

        Returns:
            Deal reference string or None on failure.
        """
        url = f"{self.base_url}/api/v1/positions"
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size,
        }
        if stop_level is not None:
            payload["stopLevel"] = stop_level
        if profit_level is not None:
            payload["profitLevel"] = profit_level

        resp = self._request("POST", url, json=payload)
        if resp is None:
            return None

        data = resp.json()
        deal_ref = data.get("dealReference")
        logger.info(
            f"Order placed: {direction} {size} {epic} | "
            f"SL={stop_level} TP={profit_level} | ref={deal_ref}"
        )
        return deal_ref

    def close_position(self, deal_id):
        """
        Close an open position by deal ID.

        Args:
            deal_id: The position's deal ID.

        Returns:
            True on success, False on failure.
        """
        url = f"{self.base_url}/api/v1/positions/{deal_id}"
        resp = self._request("DELETE", url)
        if resp is None:
            return False

        logger.info(f"Position closed: deal_id={deal_id}")
        return True

    def update_position(self, deal_id, stop_level=None, profit_level=None):
        """
        Update stop-loss and/or take-profit on an existing position.

        Args:
            deal_id: The position's deal ID.
            stop_level: New absolute stop-loss price (or None to keep).
            profit_level: New absolute take-profit price (or None to keep).

        Returns:
            True on success, False on failure.
        """
        url = f"{self.base_url}/api/v1/positions/{deal_id}"
        payload = {}
        if stop_level is not None:
            payload["stopLevel"] = stop_level
        if profit_level is not None:
            payload["profitLevel"] = profit_level

        resp = self._request("PUT", url, json=payload)
        if resp is None:
            return False

        logger.info(
            f"Position updated: deal_id={deal_id} | "
            f"SL={stop_level} TP={profit_level}"
        )
        return True

    def get_deal_confirmation(self, deal_reference):
        """
        Get deal confirmation details after placing an order.

        Args:
            deal_reference: The deal reference from place_order().

        Returns:
            Dict with deal details or None.
        """
        url = f"{self.base_url}/api/v1/confirms/{deal_reference}"
        resp = self._request("GET", url)
        if resp is None:
            return None
        return resp.json()

    # -------------------------------------------------------------------------
    #  Account Info
    # -------------------------------------------------------------------------
    def get_account_info(self):
        """Get account balance and details."""
        url = f"{self.base_url}/api/v1/accounts"
        resp = self._request("GET", url)
        if resp is None:
            return None
        return resp.json()

    def get_market_info(self, epic):
        """Get market details for a specific instrument."""
        url = f"{self.base_url}/api/v1/markets/{epic}"
        resp = self._request("GET", url)
        if resp is None:
            return None
        return resp.json()
