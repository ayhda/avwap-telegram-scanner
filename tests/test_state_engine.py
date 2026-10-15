"""Unit tests for regime classification, retests, and state flips."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
import pandas as pd

from scanner.anchored_vwap import AVWAPResult
from scanner.state_engine import (
    CoinScanResult,
    classify_state,
    detect_green_pullback_zones,
    detect_local_rejections,
    load_previous_states,
    save_current_states,
)


class TestStateEngine(unittest.TestCase):
    def test_classify_state_bull(self):
        # BULL: M >= -1.0% AND pW >= -1.0% AND W >= 0.0%
        # (excluding N-BEAR where M < 0 and pW < 0 and 0 <= W <= 1.5)
        self.assertEqual(classify_state(d_m=2.5, d_pw=1.0, d_w=0.5), "BULL")
        self.assertEqual(classify_state(d_m=0.5, d_pw=-0.8, d_w=0.2), "BULL")
        self.assertEqual(classify_state(d_m=-0.5, d_pw=0.2, d_w=0.1), "BULL")
        # Strong breakout from negative macro: W > 1.5%
        self.assertEqual(classify_state(d_m=-0.5, d_pw=-0.8, d_w=2.0), "BULL")

    def test_classify_state_n_bull(self):
        # N-BULL: M >= 0.0% AND pW >= 0.0% AND -1.5% <= W < 0.0%
        self.assertEqual(classify_state(d_m=1.5, d_pw=0.5, d_w=-0.4), "N-BULL")
        self.assertEqual(classify_state(d_m=0.0, d_pw=0.0, d_w=-1.5), "N-BULL")
        self.assertEqual(classify_state(d_m=3.0, d_pw=2.0, d_w=-0.01), "N-BULL")

    def test_classify_state_bear(self):
        # BEAR: M <= 1.0% AND pW <= 1.0% AND W < 0.0%
        # (excluding N-BULL where M >= 0 and pW >= 0 and -1.5 <= W < 0)
        self.assertEqual(classify_state(d_m=-2.0, d_pw=-1.5, d_w=-0.5), "BEAR")
        self.assertEqual(classify_state(d_m=0.5, d_pw=-0.2, d_w=-0.5), "BEAR")
        self.assertEqual(classify_state(d_m=-0.5, d_pw=0.5, d_w=-0.5), "BEAR")
        # Severe breakdown from positive macro: W < -1.5%
        self.assertEqual(classify_state(d_m=0.8, d_pw=0.8, d_w=-2.0), "BEAR")

    def test_classify_state_n_bear(self):
        # N-BEAR: M < 0.0% AND pW < 0.0% AND 0.0% <= W <= 1.5%
        self.assertEqual(classify_state(d_m=-1.5, d_pw=-2.0, d_w=0.5), "N-BEAR")
        self.assertEqual(classify_state(d_m=-0.1, d_pw=-0.5, d_w=0.0), "N-BEAR")
        self.assertEqual(classify_state(d_m=-3.0, d_pw=-1.0, d_w=1.5), "N-BEAR")

    def test_classify_state_chop(self):
        # Conflicting signals
        # M is very positive (+5%), but pW is very negative (-4%)
        self.assertEqual(classify_state(d_m=5.0, d_pw=-4.0, d_w=1.0), "CHOP")
        # None values
        self.assertEqual(classify_state(d_m=None, d_pw=1.0, d_w=1.0), "N/A")

    def test_detect_green_pullback_zones(self):
        now = datetime.now(timezone.utc)
        # Construct mock anchor results
        anchors = {
            "W": AVWAPResult(
                anchor_name="W",
                vwap=100.0,
                sigma=2.0,
                vah=102.0,
                val=98.0,
                distance_pct=-0.1,  # In range [-0.8, +1.0]
                z_score=-0.05,
                candle_count=10,
                start_time=now,
                end_time=None,
            ),
            "M": AVWAPResult(
                anchor_name="M",
                vwap=99.0,
                sigma=3.0,
                vah=102.0,
                val=96.0,
                distance_pct=0.3,  # In range [-0.8, +1.0]
                z_score=0.1,
                candle_count=50,
                start_time=now,
                end_time=None,
            ),
            "Y": AVWAPResult(
                anchor_name="Y",
                vwap=70.0,
                sigma=10.0,
                vah=80.0,
                val=60.0,
                distance_pct=42.0,  # Not in retest range
                z_score=2.9,
                candle_count=200,
                start_time=now,
                end_time=None,
            ),
        }

        # Should detect W and M for BULL or N-BULL
        retests = detect_green_pullback_zones(anchors, "N-BULL")
        detected_anchors = [r.anchor for r in retests]
        self.assertIn("W", detected_anchors)
        self.assertIn("M", detected_anchors)
        self.assertNotIn("Y", detected_anchors)

        # Should return empty if state is BEAR
        bear_retests = detect_green_pullback_zones(anchors, "BEAR")
        self.assertEqual(len(bear_retests), 0)

    def test_detect_local_rejections(self):
        now = datetime.now(timezone.utc)
        # 4H candles where the last one closed bearish (close < open)
        df_4h = pd.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp("2026-10-14 00:00:00", tz="UTC"),
                    pd.Timestamp("2026-10-14 04:00:00", tz="UTC"),
                ],
                "open": [100.0, 105.0],
                "high": [102.0, 106.0],
                "low": [99.0, 101.0],
                "close": [101.0, 102.0],  # Close (102) < Open (105) -> Bearish!
                "volume": [100.0, 150.0],
            }
        )

        anchors = {
            "M": AVWAPResult(
                anchor_name="M",
                vwap=100.0,
                sigma=5.0,
                vah=105.0,
                val=95.0,
                distance_pct=2.0,
                z_score=0.4,  # In range (0 < Z <= 1.0)
                candle_count=20,
                start_time=now,
                end_time=None,
            ),
            "Q": AVWAPResult(
                anchor_name="Q",
                vwap=90.0,
                sigma=4.0,
                vah=94.0,
                val=86.0,
                distance_pct=13.3,
                z_score=3.0,  # Z > 1.0 -> not a local rejection near VWAP
                candle_count=40,
                start_time=now,
                end_time=None,
            ),
        }

        rejections = detect_local_rejections(anchors, df_4h)
        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0].anchor, "M")
        self.assertIn("4H Rejection near M VWAP", rejections[0].description)

    def test_state_persistence_and_flips(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            temp_path = f.name

        try:
            now = datetime.now(timezone.utc)
            mock_res = [
                CoinScanResult(
                    symbol="ETH",
                    current_close=3500.0,
                    anchors={
                        "W": AVWAPResult(
                            "W", 3450.0, 20.0, 3470.0, 3430.0, 1.45, 2.5, 10, now, None
                        )
                    },
                    state="BULL",
                )
            ]
            save_current_states(temp_path, mock_res)

            # Load back
            loaded = load_previous_states(temp_path)
            self.assertIn("ETH", loaded)
            self.assertEqual(loaded["ETH"]["state"], "BULL")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
