# 🚀 Daily Candle Flip Bot (BTC, ETH, GOLD)
from flask import Flask
import threading, os, time, requests, pandas as pd
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from binance.client import Client

app = Flask(__name__)

@app.route("/")
def home():
    return "Daily Candle Bot Running!"

def run_bot():
    # --- Load env vars ---
    load_dotenv()
    API_KEY = os.getenv("BINANCE_API_KEY")
    API_SECRET = os.getenv("BINANCE_API_SECRET")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    BINANCE_SYMBOLS = ["BTCUSDT", "ETHUSDT"]
    SWISSQUOTE_SYMBOLS = ["XAU/USD"]
    SYMBOLS = BINANCE_SYMBOLS + SWISSQUOTE_SYMBOLS

    client = Client(API_KEY, API_SECRET)
    last_direction = {}
    gold_candle = None  # Track Gold forming daily candle

    # --- Telegram notifier ---
    def send_telegram(msg: str):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            print("Telegram error:", e)

    # --- Binance forming daily candle ---
    def get_today_candle_binance(symbol):
        klines = client.futures_klines(symbol=symbol, interval="1d", limit=2)
        df = pd.DataFrame(klines, columns=[
            'time','open','high','low','close','volume',
            'close_time','qav','trades','tbb','tbq','ignore'
        ])
        for col in ['open','high','low','close']:
            df[col] = df[col].astype(float)
        df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
        return df.iloc[-1]  # Current forming candle

    # --- Swissquote forming daily candle ---
    def get_today_candle_swissquote(symbol):
        nonlocal gold_candle
        url = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
        r = requests.get(url, timeout=10).json()
        price = float(r[0]["spreadProfilePrices"][0]["bid"])  # Use bid as reference

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        wat_time = now + timedelta(hours=1)  # Convert UTC → WAT
        today_date = wat_time.date()

        # Reset Gold daily candle at 1AM WAT (00:00 UTC)
        if gold_candle is None or gold_candle["date"] != today_date:
            gold_candle = {
                "date": today_date,
                "time": wat_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price
            }
        else:
            gold_candle["close"] = price
            gold_candle["high"] = max(gold_candle["high"], price)
            gold_candle["low"] = min(gold_candle["low"], price)

        return gold_candle

    # --- main loop ---
    while True:
        try:
            for symbol in SYMBOLS:
                if symbol in BINANCE_SYMBOLS:
                    today = get_today_candle_binance(symbol)
                    today_date = today['time'].date()
                    open_price, close_price = today['open'], today['close']
                elif symbol in SWISSQUOTE_SYMBOLS:
                    today = get_today_candle_swissquote(symbol)
                    today_date = today["date"]
                    open_price, close_price = today['open'], today['close']
                else:
                    continue

                # Detect bullish/bearish
                direction = "bullish" if close_price > open_price else "bearish"
                key = f"{symbol}_{today_date}"

                # Alert only if flip occurs
                if last_direction.get(key) != direction:
                    if last_direction.get(key) is not None:
                        msg = (f"⚡ *{symbol}* Daily Candle Flip!\n"
                               f"📅 {today_date}\n"
                               f"Now: {direction.upper()} "
                               f"(O:{open_price} → C:{close_price})")
                        send_telegram(msg)

                last_direction[key] = direction  # Update

        except Exception as e:
            print("Error:", e)

        time.sleep(300)  # Check every 5 minutes


# Run bot in background thread
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
