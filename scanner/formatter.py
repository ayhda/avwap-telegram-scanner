"""Telegram message HTML formatter with mobile-friendly monospace table."""

from datetime import datetime, timezone
from typing import List, Optional
import numpy as np

from scanner.state_engine import CoinScanResult


def format_distance(val: Optional[float], width: int = 5) -> str:
    """Formats percentage distance with sign and fixed width.

    E.g., +3.3, -0.7, +19.0, +120, N/A
    """
    if val is None or np.isnan(val):
        return f"{'N/A':>{width}}"

    # Large values (> 99.9% or < -99.9%) format with 0 decimal places to fit width
    if abs(val) >= 99.5:
        s = f"{val:+.0f}"
    else:
        s = f"{val:+.1f}"

    return f"{s:>{width}}"


def generate_monospace_table(results: List[CoinScanResult]) -> str:
    """Builds a compact monospace matrix suitable for phone screens.

    Header format:
    SYM     Y     Q     M    pW     W  STATE
    """
    header = "SYM     Y     Q     M    pW     W  STATE"
    rows = [header]

    for item in results:
        sym = f"{item.symbol:<4}"[:4]  # Max 4-5 chars
        d_y = item.anchors.get("Y", None)
        d_q = item.anchors.get("Q", None)
        d_m = item.anchors.get("M", None)
        d_pw = item.anchors.get("pW", None)
        d_w = item.anchors.get("W", None)

        s_y = format_distance(d_y.distance_pct if d_y else None, 5)
        s_q = format_distance(d_q.distance_pct if d_q else None, 5)
        s_m = format_distance(d_m.distance_pct if d_m else None, 5)
        s_pw = format_distance(d_pw.distance_pct if d_pw else None, 5)
        s_w = format_distance(d_w.distance_pct if d_w else None, 5)
        state_str = f"{item.state:<6}"

        row = f"{sym} {s_y} {s_q} {s_m} {s_pw} {s_w}  {state_str}"
        rows.append(row)

    return "\n".join(rows)


def build_telegram_html(
    results: List[CoinScanResult],
    scan_time: Optional[datetime] = None,
    exchange_source: str = "Bitget/Bybit",
) -> str:
    """Builds the complete Telegram message formatted with HTML parse mode."""
    t_utc = scan_time or datetime.now(timezone.utc)
    time_str = t_utc.strftime("%Y-%m-%d %H:%M UTC")

    # Group actionable alerts
    state_flips: List[str] = []
    active_retests: List[str] = []
    local_rejections: List[str] = []

    for item in results:
        # 1. State Flips
        if item.is_state_flip and item.prev_state:
            # Highlight flips to BULL / N-BULL or general flips
            flip_emoji = "🚀" if item.state in ("BULL", "N-BULL") else "🔄"
            state_flips.append(
                f"• {flip_emoji} <b>{item.symbol}</b>: {item.prev_state} ➔ <b>{item.state}</b>"
            )

        # 2. Active 🟢 Green Pullback Support Retests
        if item.green_retests:
            retest_strs = []
            for r in item.green_retests:
                sign = "+" if r.distance_pct >= 0 else ""
                retest_strs.append(f"{r.anchor} ({sign}{r.distance_pct:.1f}%🟢)")
            retest_line = " | ".join(retest_strs)
            active_retests.append(
                f"• <b>{item.symbol}</b> [{item.state}]: Testing {retest_line}"
            )

        # 3. 🔴 Local Rejections
        if item.local_rejections:
            rej_strs = [r.description for r in item.local_rejections]
            rej_line = " | ".join(rej_strs)
            local_rejections.append(
                f"• <b>{item.symbol}</b> [{item.state}]: {rej_line}"
            )

    # Section 1: Actionable Alerts
    alerts_parts: List[str] = []

    if state_flips:
        alerts_parts.append("<b>🔄 STATE FLIPS:</b>\n" + "\n".join(state_flips))

    if active_retests:
        alerts_parts.append(
            "<b>🟢 VALUE AREA RETESTS (Support):</b>\n" + "\n".join(active_retests)
        )

    if local_rejections:
        alerts_parts.append(
            "<b>🔴 LOCAL REJECTIONS (4H Bearish):</b>\n" + "\n".join(local_rejections)
        )

    if not alerts_parts:
        actionable_section = (
            "🚨 <b>STATE FLIPS & RETESTS</b>\n"
            "<i>No active state flips or support retests this cycle.</i>"
        )
    else:
        actionable_section = "🚨 <b>STATE FLIPS & RETESTS</b>\n\n" + "\n\n".join(
            alerts_parts
        )

    # Section 2: Monospace Matrix
    matrix_table = generate_monospace_table(results)

    # Assemble full message
    msg = (
        f"📊 <b>MULTI-TIMEFRAME AVWAP SCANNER</b>\n"
        f"📅 <code>{time_str}</code> | <i>{exchange_source}</i>\n\n"
        f"{actionable_section}\n\n"
        f"📈 <b>DISTANCE TO VWAP MATRIX (%)</b>\n"
        f"<pre>{matrix_table}</pre>\n"
        f"<i>Anchors: Y=Year, Q=Quarter, M=Month, pW=PrevWeek, W=Week</i>"
    )

    return msg
