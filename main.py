# 🚀 Multi-Pair Daily Candle Flip Bot (Swissquote)
from flask import Flask
import threading, os, time, requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

app = Flask(__name__)

@app.route("/")
def home():
    return "Daily Candle Bot Running!"

def run_bot():
    # --- Load env vars ---
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    # Pairs to monitor
    SYMBOLS = ["XAU/USD", "GBP/USD", "EUR/USD", "AUD/USD", "GBP/JPY", "USD/JPY"]

    # Store per-symbol state
    candles = {}         # forming candle {symbol: {open,high,low,close,date}}
    last_direction = {}  # last known direction {symbol: "bullish"/"bearish"}

    # --- Telegram notifier ---
    def send_telegram(msg: str):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except:
            pass  # fail silently, no logging

    # --- Get forming candle for any symbol from Swissquote ---
    def get_today_candle(symbol):
        url_symbol = symbol.replace("/", "")
        url = f"https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/{url_symbol}"
        r = requests.get(url, timeout=10).json()
        price = float(r[0]["spreadProfilePrices"][0]["bid"])

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        wat_time = now + timedelta(hours=1)  # UTC → WAT
        today_date = wat_time.date()

        # Reset candle at 1 AM WAT (00:00 UTC)
        if symbol not in candles or candles[symbol]["date"] != today_date:
            candles[symbol] = {
                "date": today_date,
                "time": wat_time,
                "open": price,
                "high": price,
                "low": price,
                "close": price
            }
        else:
            candles[symbol]["close"] = price
            candles[symbol]["high"] = max(candles[symbol]["high"], price)
            candles[symbol]["low"] = min(candles[symbol]["low"], price)

        return candles[symbol]

    # --- main loop ---
    while True:
        try:
            for symbol in SYMBOLS:
                today = get_today_candle(symbol)
                open_price, close_price = today['open'], today['close']
                direction = "bullish" if close_price > open_price else "bearish"

                # Alert if flip happens
                if last_direction.get(symbol) is not None and last_direction[symbol] != direction:
                    msg = (f"⚡ *{symbol}* Daily Candle Flip!\n"
                           f"📅 {today['date']}\n"
                           f"Now: {direction.upper()} "
                           f"(O:{open_price} → C:{close_price})\n"
                           f"H:{today['high']} L:{today['low']}")
                    send_telegram(msg)

                last_direction[symbol] = direction  # always update

        except:
            pass  # ignore all errors silently

        time.sleep(300)  # Check every 5 minutes


# Run bot in background thread
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
