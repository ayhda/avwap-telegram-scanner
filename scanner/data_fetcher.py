"""Data fetcher for Bitget and Bybit public REST APIs with auto-fallback."""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import pandas as pd
import requests

from scanner.config import (
    BACKOFF_FACTOR,
    BITGET_BASE_URL,
    BITGET_CANDLES_ENDPOINT,
    BITGET_GRANULARITY_MAP,
    BITGET_PRODUCT_TYPE,
    BYBIT_BASE_URL,
    BYBIT_CATEGORY,
    BYBIT_INTERVAL_MAP,
    BYBIT_KLINE_ENDPOINT,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    SYMBOL_ALIASES,
)
from scanner.mock_data import get_mock_market_data

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches futures candlestick data from Bitget or Bybit without API keys."""

    def __init__(self, preferred_exchange: str = "bitget", use_mock: bool = False):
        self.preferred_exchange = preferred_exchange.lower()
        self.use_mock = use_mock or os.getenv("MOCK_DATA", "false").lower() in ("true", "1", "yes")
        self.verify_ssl = os.getenv("VERIFY_SSL", "true").lower() not in ("false", "0", "no")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "AVWAP-Scanner-Bot/1.0 (GitHubActions; Serverless; Python)",
                "Accept": "application/json",
            }
        )

    def _fetch_bitget_candles(
        self,
        symbol: str,
        granularity: str,
        limit: int = 1000,
    ) -> Optional[pd.DataFrame]:
        """Fetches candles from Bitget V2 Futures API.

        GET /api/v2/mix/market/candles
        Candle row: [timestamp, open, high, low, close, baseVolume, quoteVolume]
        """
        url = f"{BITGET_BASE_URL}{BITGET_CANDLES_ENDPOINT}"
        bitget_granularity = BITGET_GRANULARITY_MAP.get(granularity, granularity)

        params = {
            "symbol": symbol,
            "productType": BITGET_PRODUCT_TYPE,
            "granularity": bitget_granularity,
            "limit": str(limit),
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    verify=self.verify_ssl,
                )
                if resp.status_code != 200:
                    logger.warning(
                        f"Bitget HTTP {resp.status_code} for {symbol} ({granularity})"
                    )
                    time.sleep(BACKOFF_FACTOR * attempt)
                    continue

                data = resp.json()
                if data.get("code") != "00000" or not data.get("data"):
                    logger.warning(
                        f"Bitget non-success code {data.get('code')} for {symbol}: {data.get('msg')}"
                    )
                    return None

                raw_list = data["data"]
                if not raw_list:
                    return None

                # Parse into DataFrame
                # Bitget fields: [timestamp, open, high, low, close, baseVolume, quoteVolume]
                df = pd.DataFrame(
                    raw_list,
                    columns=[
                        "timestamp",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "quote_volume",
                    ],
                )
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"].astype(float), unit="ms", utc=True
                )
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)

                df.sort_values(by="timestamp", inplace=True)
                df.reset_index(drop=True, inplace=True)
                return df

            except Exception as e:
                logger.warning(
                    f"Bitget error for {symbol} ({granularity}) attempt {attempt}: {e}"
                )
                time.sleep(BACKOFF_FACTOR * attempt)

        return None

    def _fetch_bybit_candles(
        self,
        symbol: str,
        granularity: str,
        limit: int = 1000,
    ) -> Optional[pd.DataFrame]:
        """Fetches candles from Bybit V5 Linear Futures API.

        GET /v5/market/kline
        Candle row: [timestamp, open, high, low, close, volume, turnover]
        """
        url = f"{BYBIT_BASE_URL}{BYBIT_KLINE_ENDPOINT}"
        bybit_interval = BYBIT_INTERVAL_MAP.get(granularity, granularity)

        params = {
            "category": BYBIT_CATEGORY,
            "symbol": symbol,
            "interval": bybit_interval,
            "limit": limit,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    verify=self.verify_ssl,
                )
                if resp.status_code != 200:
                    logger.warning(
                        f"Bybit HTTP {resp.status_code} for {symbol} ({granularity})"
                    )
                    time.sleep(BACKOFF_FACTOR * attempt)
                    continue

                data = resp.json()
                if data.get("retCode") != 0 or not data.get("result"):
                    logger.warning(
                        f"Bybit non-zero retCode {data.get('retCode')} for {symbol}: {data.get('retMsg')}"
                    )
                    return None

                raw_list = data["result"].get("list", [])
                if not raw_list:
                    return None

                # Bybit fields: [timestamp, open, high, low, close, volume, turnover]
                # Note: Bybit returns reverse-chronological order (newest first)
                df = pd.DataFrame(
                    raw_list,
                    columns=[
                        "timestamp",
                        "open",
                        "high",
                        "low",
                        "close",
                        "volume",
                        "turnover",
                    ],
                )
                df["timestamp"] = pd.to_datetime(
                    df["timestamp"].astype(float), unit="ms", utc=True
                )
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)

                # Sort ascending
                df.sort_values(by="timestamp", inplace=True)
                df.reset_index(drop=True, inplace=True)
                return df

            except Exception as e:
                logger.warning(
                    f"Bybit error for {symbol} ({granularity}) attempt {attempt}: {e}"
                )
                time.sleep(BACKOFF_FACTOR * attempt)

        return None

    def fetch_candles_for_symbol(
        self,
        base_symbol: str,
        granularity: str,
    ) -> Tuple[Optional[pd.DataFrame], str]:
        """Fetches candles for a symbol, trying preferred exchange first with fallback

        to secondary exchange and trying all known symbol aliases.

        Returns (DataFrame or None, source_info_string).
        """
        candidate_symbols = SYMBOL_ALIASES.get(base_symbol, [f"{base_symbol}USDT"])

        # Determine exchange order
        if self.preferred_exchange == "bybit":
            exchanges = ["bybit", "bitget"]
        else:
            exchanges = ["bitget", "bybit"]

        for exchange in exchanges:
            for symbol in candidate_symbols:
                if exchange == "bitget":
                    df = self._fetch_bitget_candles(symbol, granularity)
                else:
                    df = self._fetch_bybit_candles(symbol, granularity)

                if df is not None and not df.empty:
                    return df, f"{exchange.capitalize()}:{symbol}"

        return None, "None"

    def fetch_all_timeframes(
        self,
        base_symbol: str,
        ref_time: Optional[datetime] = None,
    ) -> Tuple[
        Optional[pd.DataFrame],
        Optional[pd.DataFrame],
        Optional[pd.DataFrame],
        str,
    ]:
        """Fetches 1D, 4H, and 1H candles for a base symbol.

        Returns (df_1d, df_4h, df_1h, source_summary).
        """
        if self.use_mock:
            now_t = ref_time or datetime.now(timezone.utc)
            d1, d4, d1h = get_mock_market_data(base_symbol, now_t)
            return d1, d4, d1h, "MockSim"

        df_1d, src_1d = self.fetch_candles_for_symbol(base_symbol, "1D")
        df_4h, src_4h = self.fetch_candles_for_symbol(base_symbol, "4H")
        df_1h, src_1h = self.fetch_candles_for_symbol(base_symbol, "1H")

        source_info = (
            src_1h
            if src_1h != "None"
            else (src_4h if src_4h != "None" else src_1d)
        )
        return df_1d, df_4h, df_1h, source_info
