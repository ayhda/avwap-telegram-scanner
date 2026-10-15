"""State classification engine, retest detection, and state-flip tracking."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from scanner.anchored_vwap import AVWAPResult
from scanner.config import (
    GREEN_RETEST_D_MAX,
    GREEN_RETEST_D_MIN,
    GREEN_RETEST_Z_MAX,
    GREEN_RETEST_Z_MIN,
    LOCAL_REJECTION_Z_MAX,
    LOCAL_REJECTION_Z_MIN,
)


@dataclass
class RetestSignal:
    """Represents a support test or value area flag on a specific timeframe."""
    anchor: str
    distance_pct: float
    z_score: float
    signal_type: str  # 'GREEN_PULLBACK' or 'LOCAL_REJECTION'
    description: str


@dataclass
class CoinScanResult:
    """Consolidated quantitative results, state, and signals for one coin."""
    symbol: str
    current_close: float
    anchors: Dict[str, AVWAPResult]
    state: str
    prev_state: Optional[str] = None
    is_state_flip: bool = False
    green_retests: List[RetestSignal] = field(default_factory=list)
    local_rejections: List[RetestSignal] = field(default_factory=list)


def classify_state(
    d_m: Optional[float],
    d_pw: Optional[float],
    d_w: Optional[float],
) -> str:
    """Classifies market regime into BULL, N-BULL, BEAR, N-BEAR, or CHOP.

    Formulas:
    - BULL: M >= -1.0% AND pW >= -1.0% AND W >= 0.0%
    - N-BULL (Bullish Pullback): M >= 0.0% AND pW >= 0.0%, but -1.5% <= W < 0.0%
    - BEAR: M <= 1.0% AND pW <= 1.0% AND W < 0.0%
    - N-BEAR (Bearish Relief Bounce): M < 0.0% AND pW < 0.0%, but 0.0% <= W <= 1.5%
    """
    if d_m is None or d_pw is None or d_w is None:
        return "N/A"

    # Evaluate pullback / bounce conditions first to avoid overlap with broad regimes
    # N-BULL: Macro positive, but short-term week pulled back mildly
    if d_m >= 0.0 and d_pw >= 0.0 and (-1.5 <= d_w < 0.0):
        return "N-BULL"

    # N-BEAR: Macro negative, but short-term week bounced mildly
    if d_m < 0.0 and d_pw < 0.0 and (0.0 <= d_w <= 1.5):
        return "N-BEAR"

    # Standard BULL: Macro firm and short-term week positive
    if d_m >= -1.0 and d_pw >= -1.0 and d_w >= 0.0:
        return "BULL"

    # Standard BEAR: Macro weak and short-term week negative
    if d_m <= 1.0 and d_pw <= 1.0 and d_w < 0.0:
        return "BEAR"

    return "CHOP"


def detect_green_pullback_zones(
    anchors: Dict[str, AVWAPResult],
    state: str,
) -> List[RetestSignal]:
    """Detects 🟢 Green Pullback Zone:

    Flag any timeframe (Y, Q, M, pW, W) where price is in an active bullish trend
    (state in BULL or N-BULL) and testing support right at VWAP or +1 sigma VAH:
    (-0.8% <= D <= +1.0% OR -0.2 <= Z <= +1.1).
    """
    retests: List[RetestSignal] = []

    # Active bullish trend required
    if state not in ("BULL", "N-BULL"):
        return retests

    check_anchors = ["W", "pW", "M", "Q", "Y"]
    for name in check_anchors:
        res = anchors.get(name)
        if not res or res.distance_pct is None or res.z_score is None:
            continue

        d = res.distance_pct
        z = res.z_score

        is_d_in_range = GREEN_RETEST_D_MIN <= d <= GREEN_RETEST_D_MAX
        is_z_in_range = GREEN_RETEST_Z_MIN <= z <= GREEN_RETEST_Z_MAX

        if is_d_in_range or is_z_in_range:
            sign = "+" if d >= 0 else ""
            desc = f"Testing {name} ({sign}{d:.1f}%🟢)"
            retests.append(
                RetestSignal(
                    anchor=name,
                    distance_pct=d,
                    z_score=z,
                    signal_type="GREEN_PULLBACK",
                    description=desc,
                )
            )

    return retests


def detect_local_rejections(
    anchors: Dict[str, AVWAPResult],
    candles_4h: pd.DataFrame,
) -> List[RetestSignal]:
    """Detects 🔴 Local Rejection Zone:

    Flag when price is positive on M or Q (0 < Z <= 1.0)
    but the last 4H candle closed bearish (Close < Open).
    """
    rejections: List[RetestSignal] = []

    if candles_4h.empty or len(candles_4h) < 1:
        return rejections

    last_candle = candles_4h.iloc[-1]
    is_4h_bearish = float(last_candle["close"]) < float(last_candle["open"])

    if not is_4h_bearish:
        return rejections

    for name in ["M", "Q"]:
        res = anchors.get(name)
        if not res or res.z_score is None:
            continue

        z = res.z_score
        if LOCAL_REJECTION_Z_MIN < z <= LOCAL_REJECTION_Z_MAX:
            desc = f"4H Rejection near {name} VWAP (Z={z:+.1f}🔴)"
            rejections.append(
                RetestSignal(
                    anchor=name,
                    distance_pct=res.distance_pct or 0.0,
                    z_score=z,
                    signal_type="LOCAL_REJECTION",
                    description=desc,
                )
            )

    return rejections


def load_previous_states(file_path: str) -> Dict[str, Any]:
    """Loads previously saved states from disk."""
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"Warning: Failed to load previous states from {file_path}: {e}")
        return {}


def save_current_states(
    file_path: str,
    results: List[CoinScanResult],
) -> None:
    """Persists current state map to JSON for future state-flip comparisons."""
    out: Dict[str, Any] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    for item in results:
        out[item.symbol] = {
            "state": item.state,
            "close": item.current_close,
            "d_w": item.anchors["W"].distance_pct if "W" in item.anchors else None,
            "d_pw": item.anchors["pW"].distance_pct if "pW" in item.anchors else None,
            "d_m": item.anchors["M"].distance_pct if "M" in item.anchors else None,
            "updated_at": now_iso,
        }

    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    except Exception as e:
        print(f"Error saving states to {file_path}: {e}")
