# 📊 Serverless Multi-Timeframe Anchored VWAP (AVWAP) Telegram Scanner Bot

A 100% free, serverless **Multi-Timeframe Anchored VWAP (AVWAP)** scanner bot (inspired by `vyaps.xyz`) engineered to run entirely on **GitHub Actions** with **zero VPS or hosting costs**. 

The bot calculates 8 distinct Anchored VWAPs across multiple timeframe resolutions, detects market regime states (`BULL`, `N-BULL`, `BEAR`, `N-BEAR`, `CHOP`), identifies active Value Area retests (`🟢 Green Pullback Zone`) and short-term rejections (`🔴 Local Rejection Zone`), tracks **state flips** across consecutive runs, and formats ultra-clean monospace matrix tables for mobile Telegram screens.

---

## 🌟 Key Architecture & Features

- **100% Free & Serverless:** Runs on a GitHub Actions 30-minute cron schedule (`*/30 * * * *`) or manual trigger (`workflow_dispatch`). Zero servers to maintain.
- **Binance Geo-Block Bypass:** Binance US runners get HTTP 451 geo-blocked on GitHub Actions. This scanner uses the **Bitget USDT-M Futures Public REST API** with automatic, seamless fallback to the **Bybit V5 Public API** (no API keys required).
- **Lightweight Dependencies:** Uses only `requests`, `pandas`, and `numpy`. Installs in <10 seconds on GitHub Actions runners.
- **Deterministic State Persistence:** Stores previous scan states in `previous_states.json`, automatically committed back to the repository branch by GitHub Actions using `[skip ci]`.
- **Mobile-Friendly Telegram Formatting:**
  - Section 1: High-priority **Actionable Alerts** (State flips e.g. `N-BULL ➔ BULL` and active `🟢` / `🔴` Value Area retests).
  - Section 2: Fixed-width monospace table (`<pre>`) that never horizontally wraps on phone screens (<= 41 characters width).

---

## 📐 Quantitative Math & Anchor Specifications

All anchors calculate from **00:00:00 UTC** boundaries using appropriate candle resolutions:

| Anchor | Description | Candle Resolution | Boundary Definition |
| :---: | :--- | :---: | :--- |
| **`pY`** | Previous Year VWAP | `1D` | `Jan 1 (Year-1) 00:00 UTC` to `Jan 1 (Year) 00:00 UTC` |
| **`Y`** | Current Year VWAP | `1D` | `Jan 1 (Year) 00:00 UTC` to Current Candle |
| **`pQ`** | Previous Quarter VWAP | `1D` | `1st day of Q-1 00:00 UTC` to `1st day of Current Quarter` |
| **`Q`** | Current Quarter VWAP | `1D` | `1st day of Current Quarter 00:00 UTC` to Current Candle |
| **`pM`** | Previous Month VWAP | `4H` | `1st day of Month-1 00:00 UTC` to `1st day of Current Month` |
| **`M`** | Current Month VWAP | `4H` | `1st day of Current Month 00:00 UTC` to Current Candle |
| **`pW`** | Previous Week VWAP | `1H` | `Monday of Week-1 00:00 UTC` to `Monday of Current Week` |
| **`W`** | Current Week VWAP | `1H` | `Monday of Current Week 00:00 UTC` to Current Candle |

### Quantitative Formulas

1. **Typical Price ($TP_i$):**
   $$TP_i = \frac{\text{High}_i + \text{Low}_i + \text{Close}_i}{3}$$

2. **Anchored VWAP:**
   $$\text{VWAP} = \frac{\sum_{i=1}^{N} (TP_i \times V_i)}{\sum_{i=1}^{N} V_i}$$

3. **Volume-Weighted Standard Deviation ($\sigma$):**
   $$\sigma = \sqrt{\frac{\sum_{i=1}^{N} (V_i \times (TP_i - \text{VWAP})^2)}{\sum_{i=1}^{N} V_i}}$$

4. **Value Area Bands:**
   $$\text{VAH} = \text{VWAP} + 1\sigma, \quad \text{VAL} = \text{VWAP} - 1\sigma$$

5. **Percentage Distance ($D$):**
   $$D = \left(\frac{\text{Close}_{\text{current}} - \text{VWAP}}{\text{VWAP}}\right) \times 100$$

6. **Z-Score ($Z$):**
   $$Z = \frac{\text{Close}_{\text{current}} - \text{VWAP}}{\sigma}$$

---

## 🧭 Regime Classification & Signal Logic

### 1. Market State Matrix
- **`BULL`:** $M \ge -1.0\%$ **AND** $pW \ge -1.0\%$ **AND** $W \ge 0.0\%$
- **`N-BULL` (Bullish Pullback):** $M \ge 0.0\%$ **AND** $pW \ge 0.0\%$, but $-1.5\% \le W < 0.0\%$
- **`BEAR`:** $M \le 1.0\%$ **AND** $pW \le 1.0\%$ **AND** $W < 0.0\%$
- **`N-BEAR` (Bearish Relief Bounce):** $M < 0.0\%$ **AND** $pW < 0.0\%$, but $0.0\% \le W \le 1.5\%$
- **`CHOP`:** Mixed macro / micro conditions not satisfying the standard trends.

### 2. Retest & Value Area Flags
- **🟢 Green Pullback Zone:** Flagged on any anchor ($Y, Q, M, pW, W$) when the asset is in a bullish regime (`BULL` or `N-BULL`) and actively testing support at the VWAP or $+1\sigma$ VAH:
  $$-0.8\% \le D \le +1.0\% \quad \text{OR} \quad -0.2 \le Z \le +1.1$$
- **🔴 Local Rejection Zone:** Flagged when price is positive on $M$ or $Q$ ($0 < Z \le 1.0$), but the most recent 4H candle closed bearish ($\text{Close} < \text{Open}$).

---

## 📱 Telegram Alert Format Example

```html
📊 <b>MULTI-TIMEFRAME AVWAP SCANNER</b>
📅 <code>2026-10-16 01:00 UTC</code> | <i>Bitget</i>

🚨 <b>STATE FLIPS & RETESTS</b>

<b>🔄 STATE FLIPS:</b>
• 🚀 <b>POL</b>: BEAR ➔ <b>N-BULL</b>
• 🔄 <b>ETH</b>: BULL ➔ <b>N-BULL</b>

<b>🟢 VALUE AREA RETESTS (Support):</b>
• <b>POL</b> [N-BULL]: Testing W (-0.1%🟢) | M (+0.3%🟢)
• <b>UNI</b> [BULL]: Testing M (-0.7%🟢) & pW (+0.3%🟢)

📈 <b>DISTANCE TO VWAP MATRIX (%)</b>
<pre>
SYM     Y     Q     M    pW     W  STATE
UNI  +3.3  -0.7  -0.7  +0.3  +1.8  BULL  
DOGE +6.3  +0.6  +0.6  -0.1  +1.9  BULL  
POL   +19  +0.3  +0.3  +1.4  -0.1  N-BULL
BTC  +177  +291 -45.3  -5.1  -4.6  BEAR  
ETH  +114 +57.5 -21.7  -9.1  -1.0  BEAR  
SOL  -18.1 -29.0 +43.4  +0.0  +1.7  BULL  
</pre>
<i>Anchors: Y=Year, Q=Quarter, M=Month, pW=PrevWeek, W=Week</i>
```

---

## 🚀 Setup & Deployment Guide

### Step 1: Create a Telegram Bot & Get Chat ID
1. Open Telegram and search for [@BotFather](https://t.me/botfather).
2. Send `/newbot`, follow prompts, and copy your **HTTP API Token** (e.g. `7890123456:AAG...`).
3. Create a Telegram channel or group, add your bot as an administrator.
4. Obtain your `TELEGRAM_CHAT_ID`:
   - For groups/channels: forward a message to [@userinfobot](https://t.me/userinfobot) or use `-100xxxxxxxxxx`.
   - For direct personal alerts: send a message to your bot and visit `https://api.telegram.org/bot<TOKEN>/getUpdates`.

### Step 2: Push to GitHub & Configure Secrets
1. Push this repository to your GitHub account:
   ```bash
   git init
   git add .
   git commit -m "feat: initial AVWAP telegram scanner"
   git branch -M main
   git remote add origin https://github.com/<your-username>/avwap-telegram-scanner.git
   git push -u origin main
   ```
2. Navigate to your repository on GitHub:
   - Go to **Settings** ➔ **Secrets and variables** ➔ **Actions**.
   - Click **New repository secret** and add:
     - `TELEGRAM_BOT_TOKEN`: Your BotFather token.
     - `TELEGRAM_CHAT_ID`: Your target chat/channel ID.

### Step 3: Enable Workflow Write Permissions
For GitHub Actions to automatically commit and push state updates (`previous_states.json`):
1. In your repository, go to **Settings** ➔ **Actions** ➔ **General**.
2. Scroll down to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

### Step 4: Run Your First Scan
1. In GitHub, go to the **Actions** tab.
2. Select **AVWAP Telegram Scanner Bot** in the left sidebar.
3. Click **Run workflow** ➔ **Run workflow**.
4. Check your Telegram chat—your first matrix alert will arrive in ~20 seconds!

---

## 💻 Local Development & Testing

```bash
# Clone and enter directory
cd avwap-telegram-scanner

# Install lightweight dependencies
pip install -r requirements.txt

# Run full test suite
python -m unittest discover -s tests -v

# Run dry-run scan with realistic mock data (no credentials or network needed)
python main.py --dry-run --mock

# Run dry-run scan against live Bitget API
python main.py --dry-run --exchange bitget

# Run against Bybit API
python main.py --dry-run --exchange bybit
```

---

## 📦 Project Structure

```text
avwap-telegram-scanner/
├── .github/
│   └── workflows/
│       └── scanner.yml          # GitHub Actions 30m cron + state persistence
├── scanner/
│   ├── __init__.py
│   ├── config.py                # Watchlist, symbols, endpoints, thresholds
│   ├── data_fetcher.py          # Bitget & Bybit public REST client with fallback
│   ├── anchored_vwap.py         # Quantitative AVWAP, StdDev, Value Area math
│   ├── state_engine.py          # Regime classifier, retest flags, state flips
│   ├── formatter.py             # Mobile-friendly HTML table builder
│   ├── telegram_bot.py          # Telegram Bot API client
│   └── mock_data.py             # Synthetic generator for local verification
├── tests/
│   ├── test_anchored_vwap.py    # AVWAP math & UTC boundary unit tests
│   ├── test_state_engine.py     # State regimes, retest flags, persistence tests
│   ├── test_formatter.py        # Table formatting & width verification tests
│   └── test_data_fetcher.py     # Exchange parsing tests
├── main.py                      # Main entry point & scanner orchestrator
├── previous_states.json         # State cache for flip tracking across runs
├── requirements.txt             # Lightweight Python dependencies
├── env.example                  # Sample environment variables
└── README.md                    # Documentation & setup guide
```

---

## 🛡️ License
MIT License. Free to use, modify, and distribute.
