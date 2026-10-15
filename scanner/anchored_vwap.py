"""Quantitative Anchored VWAP (AVWAP) and Value Area Band Calculations."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class AVWAPResult:
    """Stores quantitative metrics for a specific timeframe anchor."""
    anchor_name: str
    vwap: Optional[float]
    sigma: Optional[float]
    vah: Optional[float]  # VWAP + 1*sigma
    val: Optional[float]  # VWAP - 1*sigma
    distance_pct: Optional[float]  # ((current_close - vwap) / vwap) * 100
    z_score: Optional[float]  # (current_close - vwap) / sigma
    candle_count: int
    start_time: datetime
    end_time: Optional[datetime]


def get_anchor_windows(
    ref_time: Optional[datetime] = None,
) -> Dict[str, Tuple[datetime, Optional[datetime]]]:
    """Computes exact UTC anchor boundaries for 8 key AVWAP timeframes.

    Returns mapping of anchor_name -> (start_time, end_time).
    If end_time is None, the anchor extends through current time.
    """
    now = ref_time or datetime.now(timezone.utc)
    # Ensure timezone awareness
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    year = now.year
    month = now.month

    # 1. Yearly Anchors (Y, pY)
    start_y = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    start_py = datetime(year - 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_py = start_y

    # 2. Quarterly Anchors (Q, pQ)
    q_month = 1 + 3 * ((month - 1) // 3)
    start_q = datetime(year, q_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if q_month == 1:
        start_pq = datetime(year - 1, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        start_pq = datetime(year, q_month - 3, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_pq = start_q

    # 3. Monthly Anchors (M, pM)
    start_m = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if month == 1:
        start_pm = datetime(year - 1, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        start_pm = datetime(year, month - 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_pm = start_m

    # 4. Weekly Anchors (W, pW) - anchored at Monday 00:00:00 UTC
    start_w = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_pw = start_w - timedelta(days=7)
    end_pw = start_w

    return {
        "pY": (start_py, end_py),
        "Y": (start_y, None),
        "pQ": (start_pq, end_pq),
        "Q": (start_q, None),
        "pM": (start_pm, end_pm),
        "M": (start_m, None),
        "pW": (start_pw, end_pw),
        "W": (start_w, None),
    }


def compute_avwap_metrics(
    df: pd.DataFrame,
    start_time: datetime,
    end_time: Optional[datetime],
    current_close: float,
    anchor_name: str,
) -> AVWAPResult:
    """Calculates Typical Price, Anchored VWAP, Volume-Weighted StdDev,

    Value Area (+/- 1 sigma), Distance %, and Z-score for a given window.
    """
    if df.empty or current_close <= 0:
        return AVWAPResult(
            anchor_name=anchor_name,
            vwap=None,
            sigma=None,
            vah=None,
            val=None,
            distance_pct=None,
            z_score=None,
            candle_count=0,
            start_time=start_time,
            end_time=end_time,
        )

    # Slice by timestamp
    mask = df["timestamp"] >= start_time
    if end_time is not None:
        mask = mask & (df["timestamp"] < end_time)

    sub_df = df.loc[mask]
    n_candles = len(sub_df)

    if n_candles == 0:
        return AVWAPResult(
            anchor_name=anchor_name,
            vwap=None,
            sigma=None,
            vah=None,
            val=None,
            distance_pct=None,
            z_score=None,
            candle_count=0,
            start_time=start_time,
            end_time=end_time,
        )

    # Typical Price: TP = (High + Low + Close) / 3
    tp = (sub_df["high"] + sub_df["low"] + sub_df["close"]) / 3.0
    v = sub_df["volume"].fillna(0.0).values
    tp_vals = tp.values

    total_volume = float(np.sum(v))

    if total_volume <= 0:
        # Fallback to simple mean if volume is somehow 0
        vwap = float(np.mean(tp_vals))
        sigma = float(np.std(tp_vals))
    else:
        # Anchored VWAP: sum(TP * V) / sum(V)
        vwap = float(np.sum(tp_vals * v) / total_volume)

        # Volume-Weighted StdDev (sigma): sqrt( sum(V * (TP - VWAP)^2) / sum(V) )
        variance = float(np.sum(v * np.square(tp_vals - vwap)) / total_volume)
        sigma = float(np.sqrt(max(0.0, variance)))

    vah = vwap + sigma
    val = vwap - sigma

    # Percentage Distance: ((Close - VWAP) / VWAP) * 100
    distance_pct = float(((current_close - vwap) / vwap) * 100.0) if vwap > 0 else 0.0

    # Z-Score: (Close - VWAP) / sigma
    z_score = float((current_close - vwap) / sigma) if sigma > 1e-12 else 0.0

    return AVWAPResult(
        anchor_name=anchor_name,
        vwap=vwap,
        sigma=sigma,
        vah=vah,
        val=val,
        distance_pct=distance_pct,
        z_score=z_score,
        candle_count=n_candles,
        start_time=start_time,
        end_time=end_time,
    )


def calculate_all_anchors(
    candles_1d: pd.DataFrame,
    candles_4h: pd.DataFrame,
    candles_1h: pd.DataFrame,
    ref_time: Optional[datetime] = None,
) -> Dict[str, AVWAPResult]:
    """Calculates all 8 Anchored VWAP metrics using the designated candle timeframes.

    Timeframe mapping:
    - pY, Y: 1D candles
    - pQ, Q: 1D candles
    - pM, M: 4H candles
    - pW, W: 1H candles
    """
    windows = get_anchor_windows(ref_time)

    # Determine latest close across available data (preferring highest resolution 1H)
    current_close = 0.0
    for df in [candles_1h, candles_4h, candles_1d]:
        if not df.empty and "close" in df.columns:
            current_close = float(df["close"].iloc[-1])
            break

    results: Dict[str, AVWAPResult] = {}

    # pY, Y, pQ, Q -> 1D
    for name in ["pY", "Y", "pQ", "Q"]:
        start_t, end_t = windows[name]
        results[name] = compute_avwap_metrics(
            candles_1d, start_t, end_t, current_close, name
        )

    # pM, M -> 4H
    for name in ["pM", "M"]:
        start_t, end_t = windows[name]
        results[name] = compute_avwap_metrics(
            candles_4h, start_t, end_t, current_close, name
        )

    # pW, W -> 1H
    for name in ["pW", "W"]:
        start_t, end_t = windows[name]
        results[name] = compute_avwap_metrics(
            candles_1h, start_t, end_t, current_close, name
        )

    return results
