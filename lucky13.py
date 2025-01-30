import time
import random
import os
import signal
import sys
from flask_socketio import SocketIO
from flask import Flask
import threading
import json
import ccxt
import logging

# Logging setup
logging.basicConfig(level=logging.DEBUG)

# Flask setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Trading instellingen
TRADING_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']
TRADE_PERCENTAGE = 0.02
STOP_LOSS_PERCENTAGE = 0.03
TAKE_PROFIT_PERCENTAGE = 0.05

running = True

def handle_exit(sig, frame):
    global running
    print("Bot wordt gestopt...")
    running = False

# SIGTERM-signaal afvangen voor veilige afsluiting
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# 📌 Configuratie-instellingen voor notificaties
def load_notification_settings():
    if os.path.exists("config.json"):
        with open("config.json", "r") as file:
            return json.load(file)
    return {}

# 📌 Notificatie naar dashboard sturen
def send_notification(message_type, message):
    settings = load_notification_settings()
    if settings.get(message_type, False):
        socketio.emit('new_notification', {'type': message_type, 'message': message})

# 📌 Verbinding maken met Bybit API
def connect_to_bybit():
    api_key = 'BlgHo4zOTHeThKDWsj'  
    api_secret = 'cWwuFxIBZLzyBWJ4NrWpkIY5RS18O3Mns3DR'  
    
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
    })
    
    return exchange

# 📌 Functie om de actuele prijs op te halen
def get_current_price(symbol, retries=3):
    exchange = connect_to_bybit()
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except ccxt.NetworkError as e:
        logging.error(f"Netwerkfout bij ophalen van prijs voor {symbol}: {e}")
        if retries > 0:
            time.sleep(2)
            return get_current_price(symbol, retries - 1)
        else:
            return None
    except ccxt.BaseError as e:
        logging.error(f"Fout bij ophalen van prijs voor {symbol}: {e}")
        if retries > 0:
            time.sleep(2)
            return get_current_price(symbol, retries - 1)
        else:
            return None

# 📌 Functie om accountbalans op te halen
def fetch_account_balance():
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        return {'total': {'USDT': balance['total'].get('USDT', 0)}}
    except (ccxt.NetworkError, ccxt.BaseError) as e:
        logging.error(f"Fout bij het ophalen van saldo: {e}")
        return {'total': {'USDT': 0}}

# 📌 Functie om actieve trades op te halen
def get_active_trades():
    exchange = connect_to_bybit()
    try:
        active_trades = exchange.fetch_open_orders(symbol='BTC/USDT')
        return [{'symbol': order['symbol'], 'status': order['status']} for order in active_trades]
    except Exception as e:
        logging.error(f"Fout bij het ophalen van actieve trades: {e}")
        return []

# 📌 Plaats een koop- of verkooporder
def place_order(symbol, side, amount):
    exchange = connect_to_bybit()
    try:
        return exchange.create_market_order(symbol, side, amount)
    except Exception as e:
        logging.error(f"Fout bij order {symbol}: {e}")
        return None

# 📌 Simulatie van trades
def trade_simulation():
    global running
    while running:
        symbol = random.choice(TRADING_SYMBOLS)
        current_price = get_current_price(symbol)
        if current_price is None:
            continue
        balance = fetch_account_balance()
        amount_to_trade = balance['total']['USDT'] * TRADE_PERCENTAGE / current_price
        profit_or_loss = random.uniform(-STOP_LOSS_PERCENTAGE, TAKE_PROFIT_PERCENTAGE)
        if profit_or_loss > 0:
            place_order(symbol, 'buy', amount_to_trade)
            send_notification("notify_profit", f"Trade op {symbol} - Winst: {profit_or_loss}%")
        elif profit_or_loss < 0:
            place_order(symbol, 'sell', amount_to_trade)
            send_notification("notify_loss", f"Trade op {symbol} - Verlies: {profit_or_loss}%")
        time.sleep(5)

# 📌 Bot starten
def start_bot():
    global running
    while running:
        trade_simulation()

# 📌 Start bot en update dashboard periodiek
def start():
    global running
    thread = threading.Thread(target=start_bot)
    thread.start()
    while running:
        send_dashboard_data()
        time.sleep(10)

# 📌 Verzend dashboardgegevens
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    socketio.emit('update_balance', {'balance': balance['total']['USDT']})
    socketio.emit('update_trades', {'trades': active_trades})

if __name__ == "__main__":
    print("Lucky13 Bot gestart!")
    start()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
    print("Bot is gestopt.")
    sys.exit(0)
