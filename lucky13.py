import time
import random
import os
import signal
import sys
import threading
import json
import ccxt
import logging
from flask_socketio import SocketIO
from flask import Flask
import eventlet
import eventlet.wsgi

# Logging setup
DEBUG_MODE = False  # Zet op True voor gedetailleerde logs
LOG_FILE = "bot.log"
logging.basicConfig(
    filename=LOG_FILE if not DEBUG_MODE else None,
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Flask setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Trading instellingen
TRADING_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
TRADE_PERCENTAGE = 0.02
STOP_LOSS_PERCENTAGE = 0.03
TAKE_PROFIT_PERCENTAGE = 0.05

BALANCE_FILE = "balance.json"
running = True

# 📌 SIGTERM-signaal afvangen voor veilige afsluiting
def handle_exit(sig, frame):
    global running
    print("Bot wordt gestopt...")
    running = False

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# 📌 Verbinding maken met Bybit API
def connect_to_bybit():
    api_key = 'BlgHo4zOTHeThKDWsj'  
    api_secret = 'cWwuFxIBZLzyBWJ4NrWpkIY5RS18O3Mns3DR'  
    
    return ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
    })

# 📌 Functie om accountbalans op te halen en lokaal op te slaan
def fetch_account_balance():
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)

        # Opslaan in lokaal bestand
        with open(BALANCE_FILE, "w") as file:
            json.dump({"USDT": usdt_balance}, file)

        return {'total': usdt_balance}
    except (ccxt.NetworkError, ccxt.BaseError) as e:
        logging.warning(f"Fout bij ophalen saldo: {e}")

        # Laatste bekende balans ophalen als API faalt
        if os.path.exists(BALANCE_FILE):
            with open(BALANCE_FILE, "r") as file:
                try:
                    return {'total': json.load(file).get("USDT", 0)}
                except json.JSONDecodeError:
                    return {'total': 0}

        return {'total': 0}

# 📌 Simuleer het ophalen van de huidige prijs van een symbool
def get_current_price(symbol):
    return round(random.uniform(20000, 50000), 2) if symbol == "BTC/USDT" else round(random.uniform(1000, 4000), 2)

# 📌 Simuleer actieve trades ophalen
def get_active_trades():
    return [{'symbol': symbol, 'status': 'active', 'current_profit': round(random.uniform(-0.03, 0.05), 2)}
            for symbol in TRADING_SYMBOLS]

# 📌 Verzend dashboardgegevens
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()

    socketio.emit('update_balance', {'balance': balance['total']})
    socketio.emit('update_trades', {'trades': active_trades})
    logging.info(f"Dashboard geüpdatet: Balans {balance['total']} USDT")

# 📌 Trading-logica met trailing stop-loss
def start_bot():
    global running
    open_trades = {}

    while running:
        symbol = random.choice(TRADING_SYMBOLS)
        balance = fetch_account_balance()
        usdt_balance = balance['total']

        if usdt_balance > 10:  # Minimaal 10 USDT nodig
            current_price = get_current_price(symbol)

            if symbol not in open_trades:
                # Nieuwe trade openen
                trade_amount = (usdt_balance * TRADE_PERCENTAGE) / current_price
                entry_price = current_price
                stop_loss_price = entry_price * (1 - STOP_LOSS_PERCENTAGE)

                open_trades[symbol] = {
                    "entry_price": entry_price,
                    "highest_price": entry_price,
                    "stop_loss": stop_loss_price
                }

                logging.info(f"✅ Nieuwe trade op {symbol} geopend tegen {entry_price}, SL: {stop_loss_price}")

            else:
                # Update bestaande trade
                trade = open_trades[symbol]
                trade["highest_price"] = max(trade["highest_price"], current_price)

                # Bereken de nieuwe trailing stop-loss
                new_stop_loss = trade["highest_price"] * (1 - STOP_LOSS_PERCENTAGE)

                if new_stop_loss > trade["stop_loss"]:
                    trade["stop_loss"] = new_stop_loss
                    logging.info(f"🔼 Trailing stop-loss verhoogd voor {symbol}: {new_stop_loss}")

                # Stop-loss controleren
                if current_price <= trade["stop_loss"]:
                    logging.info(f"❌ Trade op {symbol} gesloten tegen {current_price} (SL geraakt)")
                    del open_trades[symbol]

        time.sleep(5)  # Wacht 5 seconden tussen trades

# 📌 Aparte thread voor het updaten van het dashboard
def dashboard_updater():
    while running:
        send_dashboard_data()
        time.sleep(10)

# 📌 Start de bot en de dashboard-updates
def start():
    global running
    threading.Thread(target=start_bot, daemon=True).start()
    threading.Thread(target=dashboard_updater, daemon=True).start()

if __name__ == "__main__":
    print("Lucky13 Bot gestart!")
    start()

    # 📌 Start de Flask server correct met eventlet
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
    
    print("Bot is gestopt.")
    sys.exit(0)
