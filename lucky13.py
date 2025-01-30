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

BALANCE_FILE = "balance.json"  # Lokaal bestand om balans op te slaan
running = True

def handle_exit(sig, frame):
    global running
    print("Bot wordt gestopt...")
    running = False

# SIGTERM-signaal afvangen voor veilige afsluiting
signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# 📌 Verbinding maken met Bybit API
def connect_to_bybit():
    api_key = 'BlgHo4zOTHeThKDWsj'  
    api_secret = 'cWwuFxIBZLzyBWJ4NrWpkIY5RS18O3Mns3DR'  
    
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
    })
    
    return exchange

# 📌 Functie om accountbalans op te halen en lokaal op te slaan
def fetch_account_balance():
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['total'].get('USDT', 0)
        
        # Opslaan in lokaal bestand
        with open(BALANCE_FILE, "w") as file:
            json.dump({"USDT": usdt_balance}, file)
        
        return {'total': {'USDT': usdt_balance}}
    except (ccxt.NetworkError, ccxt.BaseError) as e:
        logging.warning(f"Fout bij het ophalen van saldo: {e}")
        
        # Laatste bekende balans ophalen als API faalt
        if os.path.exists(BALANCE_FILE):
            with open(BALANCE_FILE, "r") as file:
                return {'total': json.load(file)}
        
        return {'total': {'USDT': 0}}

# 📌 Verzend dashboardgegevens
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    
    socketio.emit('update_balance', {'balance': balance['total']['USDT']})
    socketio.emit('update_trades', {'trades': active_trades})
    logging.info(f"Dashboard geüpdatet: Balans {balance['total']['USDT']} USDT")

# 📌 Start bot en update dashboard periodiek
def start():
    global running
    thread = threading.Thread(target=start_bot)
    thread.start()
    
    while running:
        send_dashboard_data()
        time.sleep(10)

if __name__ == "__main__":
    print("Lucky13 Bot gestart!")
    start()
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=DEBUG_MODE)
    print("Bot is gestopt.")
    sys.exit(0)
