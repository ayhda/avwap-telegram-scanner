"""Unit tests for quantitative Anchored VWAP and Value Area calculations."""

import math
import unittest
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from scanner.anchored_vwap import (
    compute_avwap_metrics,
    get_anchor_windows,
)


class TestAnchoredVWAP(unittest.TestCase):
    def setUp(self):
        # Create a sample DataFrame with 3 candles
        # Candle 1: H=110, L=90, C=100 -> TP = 100, V = 10 -> TP*V = 1000
        # Candle 2: H=120, L=100, C=110 -> TP = 110, V = 20 -> TP*V = 2200
        # Candle 3: H=130, L=110, C=120 -> TP = 120, V = 10 -> TP*V = 1200
        # Total V = 40. Total TP*V = 4400. VWAP = 4400 / 40 = 110.0
        # Variance: [10*(100-110)^2 + 20*(110-110)^2 + 10*(120-110)^2] / 40
        #          = [10*100 + 0 + 10*100] / 40 = 2000 / 40 = 50.0
        # Sigma: sqrt(50.0) ~= 7.0710678
        self.timestamps = [
            pd.Timestamp("2026-10-10 00:00:00", tz="UTC"),
            pd.Timestamp("2026-10-11 00:00:00", tz="UTC"),
            pd.Timestamp("2026-10-12 00:00:00", tz="UTC"),
        ]
        self.df = pd.DataFrame(
            {
                "timestamp": self.timestamps,
                "high": [110.0, 120.0, 130.0],
                "low": [90.0, 100.0, 110.0],
                "close": [100.0, 110.0, 120.0],
                "volume": [10.0, 20.0, 10.0],
            }
        )

    def test_avwap_math_exact(self):
        start_t = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
        current_close = 124.1421356  # close - vwap = 14.1421356 = 2 * sigma
        res = compute_avwap_metrics(
            self.df, start_t, None, current_close, "TEST"
        )

        self.assertIsNotNone(res.vwap)
        self.assertAlmostEqual(res.vwap, 110.0, places=4)

        expected_sigma = math.sqrt(50.0)
        self.assertAlmostEqual(res.sigma, expected_sigma, places=4)
        self.assertAlmostEqual(res.vah, 110.0 + expected_sigma, places=4)
        self.assertAlmostEqual(res.val, 110.0 - expected_sigma, places=4)

        # Distance %: ((124.1421356 - 110) / 110) * 100 = (14.1421356 / 110) * 100 = 12.856%
        expected_dist = ((current_close - 110.0) / 110.0) * 100.0
        self.assertAlmostEqual(res.distance_pct, expected_dist, places=3)

        # Z-score: (124.1421356 - 110) / sigma = 14.1421356 / 7.0710678 = 2.0
        self.assertAlmostEqual(res.z_score, 2.0, places=3)
        self.assertEqual(res.candle_count, 3)

    def test_anchor_windows_utc_boundaries(self):
        # Test reference time: Wednesday Oct 14, 2026 15:30 UTC
        ref = datetime(2026, 10, 14, 15, 30, tzinfo=timezone.utc)
        windows = get_anchor_windows(ref)

        # 1. Yearly
        self.assertEqual(
            windows["Y"], (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), None)
        )
        self.assertEqual(
            windows["pY"],
            (
                datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            ),
        )

        # 2. Quarterly (Oct is Q4)
        self.assertEqual(
            windows["Q"],
            (datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc), None),
        )
        self.assertEqual(
            windows["pQ"],
            (
                datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
            ),
        )

        # 3. Monthly (Oct)
        self.assertEqual(
            windows["M"],
            (datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc), None),
        )
        self.assertEqual(
            windows["pM"],
            (
                datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
            ),
        )

        # 4. Weekly (Monday was Oct 12, 2026)
        self.assertEqual(
            windows["W"],
            (datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc), None),
        )
        self.assertEqual(
            windows["pW"],
            (
                datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc),
            ),
        )

    def test_q1_rollover_boundaries(self):
        # In January (Q1), pQ should be Q4 of previous year
        ref = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        windows = get_anchor_windows(ref)
        self.assertEqual(
            windows["pQ"],
            (
                datetime(2025, 10, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            ),
        )
        self.assertEqual(
            windows["pM"],
            (
                datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
            ),
        )

    def test_empty_dataframe_handled(self):
        empty_df = pd.DataFrame(
            columns=["timestamp", "high", "low", "close", "volume"]
        )
        start_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        res = compute_avwap_metrics(empty_df, start_t, None, 100.0, "EMPTY")
        self.assertIsNone(res.vwap)
        self.assertEqual(res.candle_count, 0)


if __name__ == "__main__":
    unittest.main()
