# 🚀 Gold Daily Candle Flip Bot (XAU/USD, Swissquote)
from flask import Flask
import threading, os, time, requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

app = Flask(__name__)

@app.route("/")
def home():
    return "Gold Candle Bot Running!"

def run_bot():
    # --- Load env vars ---
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    last_direction = None
    gold_candle = None  # Track forming daily candle

    # --- Telegram notifier ---
    def send_telegram(msg: str):
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10
            )
        except:
            pass  # silence all errors

    # --- Swissquote forming daily candle ---
    def get_today_candle():
        nonlocal gold_candle
        url = "https://forex-data-feed.swissquote.com/public-quotes/bboquotes/instrument/XAU/USD"
        r = requests.get(url, timeout=10).json()
        price = float(r[0]["spreadProfilePrices"][0]["bid"])  # Use bid as reference

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        wat_time = now + timedelta(hours=1)  # UTC → WAT
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
            today = get_today_candle()
            open_price, close_price = today['open'], today['close']
            direction = "bullish" if close_price > open_price else "bearish"

            # 🔄 Alert on every flip, even multiple times a day
            if last_direction is not None and last_direction != direction:
                msg = (f"⚡ *GOLD (XAU/USD)* Daily Candle Flip!\n"
                       f"📅 {today['date']}\n"
                       f"Now: {direction.upper()} "
                       f"(O:{open_price} → C:{close_price})\n"
                       f"H:{today['high']} L:{today['low']}")
                send_telegram(msg)

            last_direction = direction

        except:
            pass  # silence all errors

        time.sleep(300)  # Check every 5 minutes


# Run bot in background thread
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
