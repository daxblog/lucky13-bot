import time
import random
import os
import signal
import sys
import json
import ccxt
import logging
import requests  # Voor Slack notificaties
import talib  # Bibliotheek voor technische analyse
import numpy as np
from flask_socketio import SocketIO
from flask import Flask
import eventlet
import eventlet.wsgi

# Slack Webhook URL
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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”

# Functie om Slack notificaties te verzenden
def send_slack_notification(message):
    try:
        payload = {"text": message}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code != 200:
            logging.error(f"Slack notificatie mislukt: {response.text}")
    except Exception as e:
        logging.error(f"Fout bij verzenden Slack notificatie: {e}")

# Logging setup
DEBUG_MODE = False
LOG_FILE = "bot.log"

log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    handlers=[file_handler, console_handler]
)

# Trading instellingen
TRADING_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
TRADE_PERCENTAGE = 0.02
STOP_LOSS_PERCENTAGE = 0.03
TAKE_PROFIT_PERCENTAGE = 0.05
running = True

# SIGTERM-signaal afvangen voor veilige afsluiting
def handle_exit(sig, frame):
    global running
    logging.info("Bot wordt gestopt...")
    send_slack_notification("🚨 Lucky13 bot wordt gestopt...")
    running = False

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# Bybit API verbinding
def connect_to_bybit():
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")

    if not api_key or not api_secret:
        logging.error("API-sleutels ontbreken!")
        send_slack_notification("❌ Fout: Bybit API-sleutels ontbreken!")
        sys.exit(1)

    try:
        return ccxt.bybit({'apiKey': api_key, 'secret': api_secret})
    except Exception as e:
        logging.error(f"Fout bij verbinden met Bybit API: {e}")
        send_slack_notification(f"❌ Fout bij Bybit API: {e}")
        sys.exit(1)

# Haal balans op uit Bybit
def fetch_account_balance():
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        return {'total': usdt_balance}
    except Exception as e:
        logging.error(f"Fout bij ophalen balans: {e}")
        send_slack_notification(f"❌ Balans ophalen mislukt: {e}")
        return {'total': 0}

# Simuleer prijs ophalen
def get_current_price(symbol):
    return round(random.uniform(20000, 50000), 2) if symbol == "BTC/USDT" else round(random.uniform(1000, 4000), 2)

# Bereken technische indicatoren
def calculate_technical_indicators(symbol):
    close_prices = [get_current_price(symbol) for _ in range(50)]
    sma = talib.SMA(np.array(close_prices), timeperiod=14)
    rsi = talib.RSI(np.array(close_prices), timeperiod=14)
    return sma[-1] if sma[-1] is not None else 0, rsi[-1] if rsi[-1] is not None else 0

# Analyseer of het een goed moment is om te traden
def is_good_trade(symbol):
    sma_value, rsi_value = calculate_technical_indicators(symbol)
    logging.info(f"SMA: {sma_value}, RSI: {rsi_value}")
    return rsi_value < 30 and get_current_price(symbol) > sma_value

# Start de trading bot
def start_bot():
    global running
    logging.info("Trading bot gestart...")
    send_slack_notification("✅ Lucky13 bot is gestart!")

    open_trades = {}
    while running:
        symbol = random.choice(TRADING_SYMBOLS)
        balance = fetch_account_balance()
        usdt_balance = balance['total']

        if usdt_balance < 10:
            logging.warning("❌ Te weinig saldo om te traden.")
            send_slack_notification(f"❌ Te laag saldo: {usdt_balance} USDT")
            time.sleep(5)
            continue

        if not is_good_trade(symbol):
            time.sleep(5)
            continue

        current_price = get_current_price(symbol)
        trade_amount = (usdt_balance * TRADE_PERCENTAGE) / current_price
        investment = trade_amount * current_price
        stop_loss_price = current_price * (1 - STOP_LOSS_PERCENTAGE)
        take_profit_price = current_price * (1 + TAKE_PROFIT_PERCENTAGE)

        logging.info(f"Nieuwe trade op {symbol}: {current_price} USDT")
        send_slack_notification(f"📈 Nieuwe trade: {symbol} @ {current_price} USDT\n"
                                f"🎯 TP: {take_profit_price} | 🛑 SL: {stop_loss_price}")

        open_trades[symbol] = {
            "entry_price": current_price,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price
        }

        time.sleep(5)

        while running and symbol in open_trades:
            final_price = get_current_price(symbol)
            profit = final_price - current_price
            percentage_change = (profit / current_price) * 100

            logging.info(f"{symbol} huidige prijs: {final_price} USDT, winst/verlies: {percentage_change:.2f}%")

            # Trailing Stop Loss
            if final_price > open_trades[symbol]["entry_price"]:
                new_stop_loss = final_price * (1 - STOP_LOSS_PERCENTAGE)
                if new_stop_loss > open_trades[symbol]["stop_loss"]:
                    open_trades[symbol]["stop_loss"] = new_stop_loss
                    logging.info(f"📉 Nieuwe SL voor {symbol}: {new_stop_loss} USDT")

            # Trade sluiten bij SL of TP
            if final_price <= open_trades[symbol]["stop_loss"] or final_price >= open_trades[symbol]["take_profit"]:
                logging.info(f"Trade gesloten: {symbol} @ {final_price} USDT")
                send_slack_notification(f"💰 Trade gesloten: {symbol} @ {final_price} USDT\n"
                                        f"🔹 Winst/Verlies: {profit:.2f} USDT ({percentage_change:.2f}%)")
                del open_trades[symbol]
                break

            time.sleep(5)

# Start de bot
def start():
    socketio.start_background_task(start_bot)

if __name__ == "__main__":
    logging.info("Lucky13 Bot wordt gestart...")
    port = int(os.environ.get("PORT", 5000))
    start()
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
    logging.info("Bot is gestopt.")
    send_slack_notification("⛔ Lucky13 bot is gestopt.")
    sys.exit(0)