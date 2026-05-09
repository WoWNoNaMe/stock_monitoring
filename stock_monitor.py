import pandas as pd
import yfinance as yf
import requests
import json
import os
from datetime import datetime

# --- BEÁLLÍTÁSOK ---
import os
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

WATCHLIST = [
    # --- MEGA CAP AI / TECH ---
    "NVDA", "MSFT", "META", "GOOGL", "AMZN", "AAPL", "TSLA", "AVGO",

    # --- AI CHIPEK / FÉLVEZETŐK ---
    "AMD", "ARM", "ASML", "TSM", "QCOM", "INTC", "MU", "SMCI", "AMAT", "KLAC",

    # --- AI INFRASTRUKTÚRA / CLOUD ---
    "ORCL", "CRM", "NOW", "SNOW", "DDOG", "NET", "PLTR", "AI", "PATH", "GTLB",

    # --- AI KISEBB / SPEKULATÍV ---
    "IONQ", "RGTI", "SOUN", "BBAI", "MSTR", "ACHR", "JOBY", "RKLB",

    # --- KATONAI / DEFENSE ---
    "LMT", "RTX", "NOC", "GD", "BA", "KTOS", "LDOS", "CACI", "BAH", "HII",
    "TDG", "HEI", "AXON", "AVAV",

    # --- ENERGIA / NUCLEAR (AI adatközpontok miatt) ---
    "CEG", "VST", "NNE", "SMR", "OKLO", "CCJ", "URG",

    # --- FINTECH / KRIPTO KAPCSOLT ---
    "COIN", "PYPL", "SOFI", "HOOD", "MARA", "RIOT", "BTC-USD", "ETH-USD",

    # --- EURÓPAI ---
    "RHM.DE", "AIR.PA", "SAP.DE",
]

ATR_PERIOD = 14
ATR_MULTIPLIER_DAILY = 1.75
ATR_MULTIPLIER_FROM_HIGH = 3.7

ALERTED_FILE = "alerted_today.json"

def load_alerted():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(ALERTED_FILE):
        data = json.load(open(ALERTED_FILE))
        if data.get("date") == today:
            return set(data.get("symbols", []))
    return set()

def save_alerted(symbols):
    today = datetime.now().strftime("%Y-%m-%d")
    json.dump({"date": today, "symbols": list(symbols)}, open(ALERTED_FILE, "w"))

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def calculate_atr(data, period=14):
    high = data["High"].squeeze() if hasattr(data["High"], 'squeeze') else data["High"]
    low = data["Low"].squeeze() if hasattr(data["Low"], 'squeeze') else data["Low"]
    close = data["Close"].squeeze() if hasattr(data["Close"], 'squeeze') else data["Close"]
    if hasattr(high, 'columns'):
        high = high.iloc[:, 0]
        low = low.iloc[:, 0]
        close = close.iloc[:, 0]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return float(tr.rolling(window=period).mean().iloc[-1])

def calculate_rsi(data, period=14):
    close = data["Close"].squeeze() if hasattr(data["Close"], 'squeeze') else data["Close"]
    if hasattr(close, 'columns'):
        close = close.iloc[:, 0]
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return float((100 - (100 / (1 + rs))).iloc[-1])

def to_float(val):
    if hasattr(val, 'iloc'):
        val = val.iloc[-1] if len(val.shape) > 1 else val
    if hasattr(val, 'item'):
        return float(val.item())
    return float(val)

def get_series(data, col):
    s = data[col]
    if isinstance(s.columns if hasattr(s, 'columns') else None, pd.Index):
        s = s.iloc[:, 0]
    return s.squeeze()

def check_stock(symbol, data, alerted_today):
    try:
        if data.empty or len(data) < ATR_PERIOD + 2:
            print(f"{symbol}: nincs elég adat")
            return

        close = get_series(data, "Close")
        high = get_series(data, "High")
        low = get_series(data, "Low")
        volume = get_series(data, "Volume")

        atr = float(calculate_atr(data, ATR_PERIOD))
        current_price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        local_high = float(high.iloc[-30:].max())

        import math
        if any(math.isnan(x) for x in [atr, current_price, prev_close, local_high]):
            print(f"{symbol}: NaN értékek, kihagyva")
            return
        daily_change_pct = (current_price - prev_close) / prev_close * 100
        drop_from_high_pct = (current_price - local_high) / local_high * 100

        atr_pct = (atr / current_price) * 100
        threshold_daily = -atr_pct * ATR_MULTIPLIER_DAILY
        threshold_from_high = -atr_pct * ATR_MULTIPLIER_FROM_HIGH

        rsi = float(calculate_rsi(data))
        avg_volume = float(volume.iloc[-15:-1].mean())
        volume_change = (float(volume.iloc[-1]) / avg_volume - 1) * 100

        from_high_alert = drop_from_high_pct <= threshold_from_high
        daily_alert = daily_change_pct <= threshold_daily

        print(f"{symbol}: napi {daily_change_pct:.1f}% (küszöb {threshold_daily:.1f}%) | "
              f"csúcstól {drop_from_high_pct:.1f}% (küszöb {threshold_from_high:.1f}%)")

        if (from_high_alert or daily_alert) and symbol not in alerted_today:
            if from_high_alert and daily_alert:
                trigger = "⚡ Mindkét feltétel teljesült!"
            elif from_high_alert:
                trigger = "📌 Csúcstól való esés miatt"
            else:
                trigger = "📌 Nagy napi esés miatt"

            message = (
                f"🚨 <b>{symbol}</b> – Vételi lehetőség?\n"
                f"{trigger}\n\n"
                f"💰 Jelenlegi ár: <b>${current_price:.2f}</b>\n"
                f"📉 Csúcstól esés (30 nap): <b>{drop_from_high_pct:.1f}%</b>\n"
                f"   └ 30 napos max: ${local_high:.2f}\n"
                f"📉 Mai esés: <b>{daily_change_pct:.1f}%</b>\n\n"
                f"📊 RSI: {rsi:.0f} {'(túladott!)' if rsi < 35 else ''}\n"
                f"📦 Volumen: {volume_change:+.0f}% az átlagtól\n"
                f"📐 ATR küszöb: {atr_pct:.1f}% (adaptív)\n\n"
                f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            send_telegram(message)
            alerted_today.add(symbol)
            save_alerted(alerted_today)
            print(f"  → Riasztás elküldve!")
        else:
            print(f"  → Nincs riasztás")

    except Exception as e:
        print(f"Hiba {symbol} esetén: {e}")

def main():
    print(f"=== Ellenőrzés: {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    print(f"Részvények száma: {len(WATCHLIST)}")

    # Európai, kripto és speciális tickerek egyenkénti letöltése
    single_symbols = [s for s in WATCHLIST if "." in s or "-" in s]
    us_symbols = [s for s in WATCHLIST if "." not in s and "-" not in s]

    # US részvények párhuzamos letöltése
    print("US adatok letöltése...")
    all_data = yf.download(
        tickers=" ".join(us_symbols),
        period="60d",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False
    )

    alerted_today = load_alerted()

    for symbol in us_symbols:
        try:
            data = all_data[symbol] if symbol in all_data.columns.get_level_values(0) else None
            if data is None or data.empty:
                print(f"{symbol}: nem sikerült letölteni")
                continue
            check_stock(symbol, data, alerted_today)
        except Exception as e:
            print(f"Hiba {symbol} esetén: {e}")

    # Európai + kripto egyenkénti letöltése
    print("Európai + kripto adatok letöltése...")
    for symbol in single_symbols:
        try:
            data = yf.download(symbol, period="60d", interval="1d",
                               auto_adjust=True, progress=False)
            if data.empty:
                print(f"{symbol}: nem sikerült letölteni")
                continue
            check_stock(symbol, data, alerted_today)
        except Exception as e:
            print(f"Hiba {symbol} esetén: {e}")

if __name__ == "__main__":
    main()
