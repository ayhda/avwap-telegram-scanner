"""Unit tests for Telegram HTML message and monospace table formatting."""

import unittest
from datetime import datetime, timezone

from scanner.anchored_vwap import AVWAPResult
from scanner.formatter import (
    build_telegram_html,
    format_distance,
    generate_monospace_table,
)
from scanner.state_engine import CoinScanResult, RetestSignal


class TestFormatter(unittest.TestCase):
    def test_format_distance(self):
        self.assertEqual(format_distance(3.3, 5), " +3.3")
        self.assertEqual(format_distance(-0.7, 5), " -0.7")
        self.assertEqual(format_distance(19.2, 5), "+19.2")
        self.assertEqual(format_distance(-15.6, 5), "-15.6")
        self.assertEqual(format_distance(120.4, 5), " +120")
        self.assertEqual(format_distance(-150.0, 5), " -150")
        self.assertEqual(format_distance(None, 5), "  N/A")

    def test_table_line_length_and_alignment(self):
        now = datetime.now(timezone.utc)

        def make_anchor(name: str, dist: float) -> AVWAPResult:
            return AVWAPResult(
                name, 100.0, 2.0, 102.0, 98.0, dist, 1.0, 10, now, None
            )

        items = [
            CoinScanResult(
                symbol="UNI",
                current_close=8.5,
                anchors={
                    "Y": make_anchor("Y", 3.3),
                    "Q": make_anchor("Q", -0.7),
                    "M": make_anchor("M", -0.7),
                    "pW": make_anchor("pW", 0.3),
                    "W": make_anchor("W", 1.8),
                },
                state="BULL",
            ),
            CoinScanResult(
                symbol="DOGE",
                current_close=0.15,
                anchors={
                    "Y": make_anchor("Y", 6.3),
                    "Q": make_anchor("Q", 0.6),
                    "M": make_anchor("M", 0.6),
                    "pW": make_anchor("pW", -0.1),
                    "W": make_anchor("W", 1.9),
                },
                state="BULL",
            ),
            CoinScanResult(
                symbol="POL",
                current_close=0.45,
                anchors={
                    "Y": make_anchor("Y", 19.0),
                    "Q": make_anchor("Q", 0.3),
                    "M": make_anchor("M", 0.3),
                    "pW": make_anchor("pW", 1.4),
                    "W": make_anchor("W", -0.1),
                },
                state="N-BULL",
            ),
        ]

        table = generate_monospace_table(items)
        lines = table.split("\n")

        self.assertEqual(len(lines), 4)  # Header + 3 rows
        header = lines[0]
        self.assertEqual(header, "SYM     Y     Q     M    pW     W  STATE")

        # Verify max length of every line is <= 42 characters (fits mobile screens without wrapping)
        for line in lines:
            self.assertLessEqual(
                len(line),
                42,
                f"Line '{line}' exceeds 42 characters: {len(line)}",
            )

    def test_build_telegram_html_sections(self):
        now = datetime.now(timezone.utc)
        items = [
            CoinScanResult(
                symbol="POL",
                current_close=0.45,
                anchors={},
                state="N-BULL",
                prev_state="BEAR",
                is_state_flip=True,
                green_retests=[
                    RetestSignal("W", -0.1, -0.05, "GREEN_PULLBACK", "Testing W (-0.1%🟢)"),
                    RetestSignal("M", 0.3, 0.1, "GREEN_PULLBACK", "Testing M (+0.3%🟢)"),
                ],
            ),
            CoinScanResult(
                symbol="UNI",
                current_close=8.5,
                anchors={},
                state="BULL",
                prev_state="BULL",
                is_state_flip=False,
                green_retests=[
                    RetestSignal("M", -0.7, -0.2, "GREEN_PULLBACK", "Testing M (-0.7%🟢)"),
                    RetestSignal("pW", 0.3, 0.1, "GREEN_PULLBACK", "Testing pW (+0.3%🟢)"),
                ],
            ),
        ]

        html = build_telegram_html(items, scan_time=now, exchange_source="Bitget")

        # Validate required HTML tags
        self.assertIn("<b>MULTI-TIMEFRAME AVWAP SCANNER</b>", html)
        self.assertIn("<pre>", html)
        self.assertIn("</pre>", html)
        self.assertIn("<b>STATE FLIPS & RETESTS</b>", html)
        self.assertIn("BEAR ➔ <b>N-BULL</b>", html)
        self.assertIn("Testing W (-0.1%🟢) | M (+0.3%🟢)", html)
        self.assertIn("Testing M (-0.7%🟢) | pW (+0.3%🟢)", html)


if __name__ == "__main__":
    unittest.main()
