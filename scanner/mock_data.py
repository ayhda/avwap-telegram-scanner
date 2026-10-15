"""Mock candlestick data generator for local testing and offline verification."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
import numpy as np
import pandas as pd


def generate_mock_candles(
    base_price: float,
    start_time: datetime,
    end_time: datetime,
    freq_hours: int,
    volatility: float = 0.015,
    trend: float = 0.0005,
) -> pd.DataFrame:
    """Generates synthetic OHLCV candles between start_time and end_time."""
    current_time = start_time
    times = []
    while current_time <= end_time:
        times.append(current_time)
        current_time += timedelta(hours=freq_hours)

    n = len(times)
    if n == 0:
        return pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

    # Random walk with drift
    np.random.seed(int(base_price * 100) % 10000 + n)
    returns = np.random.normal(trend, volatility, n)
    price_factors = np.cumprod(1 + returns)
    closes = base_price * price_factors

    opens = np.roll(closes, 1)
    opens[0] = base_price

    highs = np.maximum(opens, closes) * (1 + np.abs(np.random.normal(0, volatility * 0.5, n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(np.random.normal(0, volatility * 0.5, n)))
    volumes = np.abs(np.random.normal(1000.0, 300.0, n)) * (base_price / 100.0)

    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(times, utc=True),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )
    return df


def get_mock_market_data(
    symbol: str,
    ref_time: datetime,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generates realistic 1D, 4H, and 1H data for a given symbol."""
    base_prices: Dict[str, float] = {
        "BTC": 64500.0,
        "ETH": 3420.0,
        "SOL": 158.0,
        "UNI": 8.40,
        "DOGE": 0.142,
        "LINK": 12.10,
        "ETHFI": 2.15,
        "PEPE": 0.0000105,
        "POL": 0.385,
        "SUI": 2.18,
        "AAVE": 162.0,
    }
    price = base_prices.get(symbol, 100.0)

    # 1D candles: past 2 years (covers pY, Y, pQ, Q)
    start_1d = datetime(ref_time.year - 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    df_1d = generate_mock_candles(price * 0.7, start_1d, ref_time, 24, volatility=0.02, trend=0.0008)

    # 4H candles: past 3 months (covers pM, M)
    start_4h = ref_time - timedelta(days=90)
    df_4h = generate_mock_candles(price * 0.9, start_4h, ref_time, 4, volatility=0.012, trend=0.0004)

    # 1H candles: past 30 days (covers pW, W)
    start_1h = ref_time - timedelta(days=30)
    df_1h = generate_mock_candles(price * 0.95, start_1h, ref_time, 1, volatility=0.008, trend=0.0002)

    return df_1d, df_4h, df_1h
