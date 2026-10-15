"""Unit tests for candle parsing from Bitget and Bybit responses."""

import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from scanner.data_fetcher import DataFetcher


class TestDataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = DataFetcher(preferred_exchange="bitget")

    @patch("requests.Session.get")
    def test_bitget_parsing(self, mock_get):
        # Mock Bitget response format:
        # [timestamp, open, high, low, close, baseVolume, quoteVolume]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "00000",
            "msg": "success",
            "data": [
                [
                    "1699990000000",
                    "35000.0",
                    "35200.0",
                    "34900.0",
                    "35100.0",
                    "100.5",
                    "3500000.0",
                ],
                [
                    "1699993600000",
                    "35100.0",
                    "35400.0",
                    "35050.0",
                    "35300.0",
                    "150.0",
                    "5200000.0",
                ],
            ],
        }
        mock_get.return_value = mock_response

        df = self.fetcher._fetch_bitget_candles("BTCUSDT", "1H")
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        self.assertIn("timestamp", df.columns)
        self.assertIn("close", df.columns)
        self.assertEqual(df["close"].iloc[-1], 35300.0)
        self.assertEqual(df["volume"].iloc[-1], 150.0)

    @patch("requests.Session.get")
    def test_bybit_parsing(self, mock_get):
        # Mock Bybit response format (reverse chronological order):
        # [timestamp, open, high, low, close, volume, turnover]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "linear",
                "symbol": "BTCUSDT",
                "list": [
                    # Newest first
                    [
                        "1699993600000",
                        "35100.0",
                        "35400.0",
                        "35050.0",
                        "35300.0",
                        "150.0",
                        "5200000.0",
                    ],
                    # Older
                    [
                        "1699990000000",
                        "35000.0",
                        "35200.0",
                        "34900.0",
                        "35100.0",
                        "100.5",
                        "3500000.0",
                    ],
                ],
            },
        }
        mock_get.return_value = mock_response

        df = self.fetcher._fetch_bybit_candles("BTCUSDT", "1H")
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        # Should be sorted ascending by timestamp
        self.assertLess(df["timestamp"].iloc[0], df["timestamp"].iloc[1])
        self.assertEqual(df["close"].iloc[-1], 35300.0)


if __name__ == "__main__":
    unittest.main()
