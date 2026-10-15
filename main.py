"""Main orchestrator for the Multi-Timeframe AVWAP Scanner Bot."""

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import List

from scanner.anchored_vwap import calculate_all_anchors
from scanner.config import WATCHLIST, config
from scanner.data_fetcher import DataFetcher
from scanner.formatter import build_telegram_html
from scanner.state_engine import (
    CoinScanResult,
    classify_state,
    detect_green_pullback_zones,
    detect_local_rejections,
    load_previous_states,
    save_current_states,
)
from scanner.telegram_bot import send_telegram_message

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AVWAP_Scanner")


def run_scanner(
    dry_run: bool = False,
    exchange: str = "bitget",
    state_file: str = "previous_states.json",
    mock: bool = False,
) -> List[CoinScanResult]:
    """Executes a full scanning cycle across all symbols in the watchlist."""
    logger.info("=" * 60)
    logger.info("Starting Multi-Timeframe AVWAP Scanner Bot Cycle")
    logger.info(
        f"Watchlist: {WATCHLIST} | Preferred Exchange: {exchange} | Dry Run: {dry_run} | Mock: {mock}"
    )
    logger.info("=" * 60)

    # 1. Load previous states for flip detection
    prev_states = load_previous_states(state_file)
    logger.info(
        f"Loaded {len(prev_states)} existing symbol states from {state_file}"
    )

    fetcher = DataFetcher(preferred_exchange=exchange, use_mock=mock)
    results: List[CoinScanResult] = []
    used_sources = set()

    # 2. Iterate through each symbol in the watchlist
    for sym in WATCHLIST:
        logger.info(f"Processing symbol: {sym}...")
        try:
            df_1d, df_4h, df_1h, src = fetcher.fetch_all_timeframes(sym)
            if src != "None":
                used_sources.add(src.split(":")[0])

            if df_1d is None or df_1h is None or df_4h is None:
                logger.warning(
                    f"Insufficient candle data fetched for {sym}. Skipping."
                )
                continue

            # Calculate 8 AVWAP anchors
            anchors = calculate_all_anchors(df_1d, df_4h, df_1h)

            # Determine latest price
            current_close = float(df_1h["close"].iloc[-1])

            # Extract distances for M, pW, W
            d_m = anchors["M"].distance_pct if "M" in anchors else None
            d_pw = anchors["pW"].distance_pct if "pW" in anchors else None
            d_w = anchors["W"].distance_pct if "W" in anchors else None

            # State classification
            state = classify_state(d_m, d_pw, d_w)

            # Check state flips
            prev_entry = prev_states.get(sym, {})
            prev_state_name = prev_entry.get("state") if prev_entry else None
            is_flip = (
                prev_state_name is not None
                and prev_state_name != state
                and state != "N/A"
            )

            # Detect retests & rejections
            green_retests = detect_green_pullback_zones(anchors, state)
            local_rejections = detect_local_rejections(anchors, df_4h)

            coin_res = CoinScanResult(
                symbol=sym,
                current_close=current_close,
                anchors=anchors,
                state=state,
                prev_state=prev_state_name,
                is_state_flip=is_flip,
                green_retests=green_retests,
                local_rejections=local_rejections,
            )
            results.append(coin_res)

            logger.info(
                f"  -> {sym}: Price={current_close:.4f} | State={state} (prev: {prev_state_name}) | "
                f"Flip={is_flip} | Retests={len(green_retests)} | Rejections={len(local_rejections)}"
            )

        except Exception as e:
            logger.error(
                f"Error processing symbol {sym}: {e}", exc_info=True
            )

    if not results:
        logger.error(
            "No scan results generated. Exiting without sending notifications."
        )
        return []

    # 3. Build formatted Telegram HTML
    exchange_summary = "/".join(sorted(used_sources)) if used_sources else exchange.capitalize()
    now_utc = datetime.now(timezone.utc)
    html_message = build_telegram_html(
        results, scan_time=now_utc, exchange_source=exchange_summary
    )

    # 4. Dispatch Telegram Notification
    bot_token = config.telegram_bot_token
    chat_id = config.telegram_chat_id
    send_telegram_message(
        bot_token=bot_token,
        chat_id=chat_id,
        html_text=html_message,
        dry_run=dry_run,
    )

    # 5. Persist updated states
    save_current_states(state_file, results)
    logger.info(f"Updated states successfully saved to {state_file}")
    logger.info("AVWAP Scanner cycle completed.")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Timeframe Anchored VWAP (AVWAP) Telegram Scanner"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=config.dry_run,
        help="Print Telegram message to console without sending API request",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        default=config.preferred_exchange,
        help="Preferred exchange ('bitget' or 'bybit')",
    )
    parser.add_argument(
        "--state-file",
        type=str,
        default=config.state_file_path,
        help="Path to previous states JSON file",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use realistic synthetic market data for offline verification and dry runs",
    )
    args = parser.parse_args()

    run_scanner(
        dry_run=args.dry_run,
        exchange=args.exchange,
        state_file=args.state_file,
        mock=args.mock,
    )


if __name__ == "__main__":
    main()
