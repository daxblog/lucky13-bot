import time
import random
import os
import signal
import sys
import json
import ccxt
import logging
from flask_socketio import SocketIO
from flask import Flask
import eventlet
import eventlet.wsgi

# Logging setup (Fix Unicode probleem door UTF-8 encoding)
DEBUG_MODE = False
LOG_FILE = "bot.log"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)]
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
WINNINGS_FILE = "winnings.json"
running = True

# SIGTERM-signaal afvangen voor veilige afsluiting
def handle_exit(sig, frame):
    global running
    logging.info("Bot wordt gestopt...")
    running = False

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

# Verbinding maken met Bybit API
def connect_to_bybit():
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")

    # Log de API-sleutels om te controleren of ze goed geladen worden
    logging.info(f"API Key: {api_key}")
    logging.info(f"API Secret: {api_secret}")

    if not api_key or not api_secret:
        logging.error("API-sleutels ontbreken! Zorg ervoor dat de environment variables correct zijn ingesteld.")
        sys.exit(1)

    try:
        exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
        })
        return exchange
    except Exception as e:
        logging.error(f"Fout bij verbinden met Bybit API: {e}")
        sys.exit(1)

# Functie om accountbalans op te halen
def fetch_account_balance():
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        logging.info(f"Balans opgehaald: {balance}")  # Log volledige balansinformatie
        usdt_balance = balance['total'].get('USDT', 0)
        logging.info(f"USDT balans: {usdt_balance}")  # Log alleen de USDT balans
        with open(BALANCE_FILE, "w", encoding="utf-8") as file:
            json.dump({"USDT": usdt_balance}, file)
        socketio.emit('update_balance', {'balance': usdt_balance})
        return {'total': usdt_balance}
    except (ccxt.NetworkError, ccxt.BaseError) as e:
        logging.warning(f"Fout bij ophalen saldo: {e}")
        if os.path.exists(BALANCE_FILE):
            with open(BALANCE_FILE, "r", encoding="utf-8") as file:
                try:
                    balance_data = json.load(file)
                    logging.warning(f"Gebruik van lokaal opgeslagen saldo: {balance_data.get('USDT', 0)}")
                    return {'total': balance_data.get("USDT", 0)}
                except json.JSONDecodeError:
                    logging.error("Error bij het lezen van lokaal saldo bestand. Zet saldo op 0.")
                    return {'total': 0}
        return {'total': 0}

# Simuleer het ophalen van de huidige prijs
def get_current_price(symbol):
    return round(random.uniform(20000, 50000), 2) if symbol == "BTC/USDT" else round(random.uniform(1000, 4000), 2)

# Trading-logica
def start_bot():
    global running
    logging.info("Trading bot gestart en actief...")

    open_trades = {}
    while running:
        symbol = random.choice(TRADING_SYMBOLS)
        balance = fetch_account_balance()
        usdt_balance = balance['total']

        if usdt_balance < 10:
            logging.warning(f"Portfolio te laag: slechts {usdt_balance} USDT beschikbaar.")
            time.sleep(5)
            continue

        current_price = get_current_price(symbol)
        trade_amount = (usdt_balance * TRADE_PERCENTAGE) / current_price
        investment = trade_amount * current_price
        stop_loss_price = current_price * (1 - STOP_LOSS_PERCENTAGE)
        take_profit_price = current_price * (1 + TAKE_PROFIT_PERCENTAGE)

        logging.info(f"Nieuwe trade op {symbol} geopend tegen {current_price} USDT. "
                     f"SL: {stop_loss_price} USDT, TP: {take_profit_price} USDT. "
                     f"Totale investering: {investment} USDT")
        
        open_trades[symbol] = {
            "entry_price": current_price,
            "stop_loss": stop_loss_price,
            "take_profit": take_profit_price
        }

        time.sleep(5)

        # Simuleer trade-afhandeling
        final_price = get_current_price(symbol)
        profit = final_price - current_price
        percentage_change = (profit / current_price) * 100
        logging.info(f"{symbol} huidige winst/verlies: {percentage_change:.2f}% ten opzichte van investering.")
        
        if final_price <= stop_loss_price or final_price >= take_profit_price:
            logging.info(f"Trade op {symbol} gesloten tegen {final_price} USDT. "
                         f"Winst/verlies: {profit:.2f} USDT ({percentage_change:.2f}%)")
            del open_trades[symbol]

        time.sleep(5)

# Start de bot in de achtergrond
def start():
    socketio.start_background_task(start_bot)

if __name__ == "__main__":
    logging.info("Lucky13 Bot wordt gestart...")
    port = int(os.environ.get("PORT", 5000))
    start()
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
    logging.info("Bot is gestopt.")
    sys.exit(0)
