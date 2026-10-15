"""Configuration settings and constants for the AVWAP Telegram Scanner."""

import os
from dataclasses import dataclass
from typing import Dict, List


# Watchlist as specified in the prompt
WATCHLIST: List[str] = [
    "BTC",
    "ETH",
    "SOL",
    "UNI",
    "DOGE",
    "LINK",
    "ETHFI",
    "PEPE",
    "POL",
    "SUI",
    "AAVE",
]

# Exchange symbol resolution candidates (Primary -> Fallbacks)
# Bitget and Bybit might name tokens slightly differently (e.g. PEPE vs 1000PEPE, POL vs MATIC)
SYMBOL_ALIASES: Dict[str, List[str]] = {
    "BTC": ["BTCUSDT"],
    "ETH": ["ETHUSDT"],
    "SOL": ["SOLUSDT"],
    "UNI": ["UNIUSDT"],
    "DOGE": ["DOGEUSDT"],
    "LINK": ["LINKUSDT"],
    "ETHFI": ["ETHFIUSDT"],
    "PEPE": ["1000PEPEUSDT", "PEPEUSDT"],
    "POL": ["POLUSDT", "MATICUSDT"],
    "SUI": ["SUIUSDT"],
    "AAVE": ["AAVEUSDT"],
}

# Public REST Endpoints (Neither requires API keys; both bypass Binance US blocks on GitHub Actions)
BITGET_BASE_URL: str = "https://api.bitget.com"
BITGET_CANDLES_ENDPOINT: str = "/api/v2/mix/market/candles"
BITGET_PRODUCT_TYPE: str = "usdt-futures"

BYBIT_BASE_URL: str = "https://api.bybit.com"
BYBIT_KLINE_ENDPOINT: str = "/v5/market/kline"
BYBIT_CATEGORY: str = "linear"

# HTTP Client Settings
REQUEST_TIMEOUT_SECONDS: int = 12
MAX_RETRIES: int = 3
BACKOFF_FACTOR: float = 1.5

# Timeframe mapping for candle fetching
# 1D: for pY, Y, pQ, Q
# 4H: for pM, M
# 1H: for pW, W
BITGET_GRANULARITY_MAP = {
    "1D": "1D",
    "4H": "4H",
    "1H": "1H",
}

BYBIT_INTERVAL_MAP = {
    "1D": "D",
    "4H": "240",
    "1H": "60",
}

# State Classification Criteria
# BULL: M >= -1.0% AND pW >= -1.0% AND W >= 0.0%
# N-BULL: M >= 0.0% AND pW >= 0.0% AND -1.5% <= W < 0.0%
# BEAR: M <= 1.0% AND pW <= 1.0% AND W < 0.0%
# N-BEAR: M < 0.0% AND pW < 0.0% AND 0.0% <= W <= 1.5%

# Retest / Value Area Criteria
# Green Pullback Zone: Active bullish trend & (-0.8% <= D <= +1.0% OR -0.2 <= Z <= +1.1)
GREEN_RETEST_D_MIN: float = -0.8
GREEN_RETEST_D_MAX: float = 1.0
GREEN_RETEST_Z_MIN: float = -0.2
GREEN_RETEST_Z_MAX: float = 1.1

# Local Rejection Zone: Price positive on M or Q (0 < Z <= 1.0) but last 4H candle closed bearish (Close < Open)
LOCAL_REJECTION_Z_MIN: float = 0.0
LOCAL_REJECTION_Z_MAX: float = 1.0

# Environment / App Settings
@dataclass
class AppConfig:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    state_file_path: str = os.getenv("STATE_FILE_PATH", "previous_states.json")
    dry_run: bool = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
    preferred_exchange: str = os.getenv("PREFERRED_EXCHANGE", "bitget").lower()


config = AppConfig()
