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

# Logging setup (Console, bestand en WebSocket)
DEBUG_MODE = False
LOG_FILE = "bot.log"

# Stel de log formatter in
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Configureer het loggen naar bestand
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

# Configureer het loggen naar de console (CMD)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

# Voeg een custom SocketIO handler toe
class SocketIOHandler(logging.Handler):
    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio

    def emit(self, record):
        log_entry = self.format(record)
        self.socketio.emit('log_message', {'log': log_entry})  # Stuur log naar front-end via WebSocket

# Flask setup
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Voeg de SocketIOHandler toe aan de logging configuratie
socket_handler = SocketIOHandler(socketio)
socket_handler.setFormatter(log_formatter)
logging.getLogger().addHandler(socket_handler)

# Voeg file en console handler toe aan root logger
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    handlers=[file_handler, console_handler, socket_handler]
)

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

# Functie om accountbalans rechtstreeks uit Bybit te halen met retry-mechanisme
def fetch_account_balance():
    exchange = connect_to_bybit()
    max_retries = 3  # Aantal keren dat de bot opnieuw probeert bij een fout
    retry_delay = 5  # Wacht 5 seconden tussen pogingen

    for attempt in range(1, max_retries + 1):
        try:
            balance = exchange.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0)  # Haal alleen USDT saldo op
            logging.info(f"[INFO] Balans succesvol opgehaald uit Bybit: {usdt_balance} USDT")
            socketio.emit('update_balance', {'balance': usdt_balance})  # Realtime update via WebSocket
            return {'total': usdt_balance}

        except (ccxt.NetworkError, ccxt.BaseError) as e:
            logging.warning(f"[WAARSCHUWING] Poging {attempt}/{max_retries} mislukt bij ophalen balans: {e}")
            
            if attempt < max_retries:
                logging.info(f"[INFO] Nieuwe poging binnen {retry_delay} seconden...")
                time.sleep(retry_delay)
            else:
                logging.error("[FOUT] Alle pogingen om de balans op te halen zijn mislukt. Bybit API mogelijk onbereikbaar.")
                return {'total': 0}  # Zet balans op 0 bij mislukking

# Simuleer het ophalen van de huidige prijs
def get_current_price(symbol):
    return round(random.uniform(20000, 50000), 2) if symbol == "BTC/USDT" else round(random.uniform(1000, 4000), 2)

# Trading-logica met trailing stop loss
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

        # Simuleer trade-afhandeling met trailing stop loss
        while running and symbol in open_trades:
            final_price = get_current_price(symbol)
            profit = final_price - current_price
            percentage_change = (profit / current_price) * 100

            logging.info(f"{symbol} huidige prijs: {final_price} USDT, winst/verlies: {percentage_change:.2f}%")

            # **Trailing Stop Loss Logica**
            if final_price > open_trades[symbol]["entry_price"]:
                new_stop_loss = final_price * (1 - STOP_LOSS_PERCENTAGE)
                if new_stop_loss > open_trades[symbol]["stop_loss"]:  # Alleen verhogen
                    open_trades[symbol]["stop_loss"] = new_stop_loss
                    logging.info(f"Nieuwe trailing stop loss voor {symbol}: {new_stop_loss:.2f} USDT")

            # Trade sluiten als stop loss of take profit bereikt is
            if final_price <= open_trades[symbol]["stop_loss"] or final_price >= open_trades[symbol]["take_profit"]:
                logging.info(f"Trade op {symbol} gesloten tegen {final_price} USDT. "
                             f"Winst/verlies: {profit:.2f} USDT ({percentage_change:.2f}%)")
                del open_trades[symbol]
                break  # Stop de loop en begin een nieuwe trade

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