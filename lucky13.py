import time
import random
import os
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

# 📌 Configuratie-instellingen voor notificaties
def load_notification_settings():
    """Laad notificatie-instellingen uit een configuratiebestand"""
    if os.path.exists("config.json"):
        with open("config.json", "r") as file:
            return json.load(file)
    return {}

# 📌 Notificatie naar dashboard sturen
def send_notification(message_type, message):
    """Verstuur notificatie naar het dashboard"""
    settings = load_notification_settings()
    if settings.get(message_type, False):
        socketio.emit('new_notification', {'type': message_type, 'message': message})

# 📌 Verbinding maken met Bybit API via ccxt
def connect_to_bybit():
    """Verbind met Bybit via ccxt"""
    api_key = 'BlgHo4zOTHeThKDWsj'  
    api_secret = 'cWwuFxIBZLzyBWJ4NrWpkIY5RS18O3Mns3DR'  
    
    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': api_secret,
    })
    
    return exchange

# 📌 Functie om de actuele prijs op te halen
def get_current_price(symbol):
    """Haal de huidige prijs op voor een bepaald symbool"""
    exchange = connect_to_bybit()
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']  # Laatste prijs
    except ccxt.NetworkError as e:
        logging.error(f"Netwerkfout bij ophalen van prijs voor {symbol}: {e}. Probeer opnieuw...")
        return get_current_price(symbol)  # Probeer opnieuw
    except ccxt.BaseError as e:
        logging.error(f"Fout bij ophalen van prijs voor {symbol}: {e}. Probeer opnieuw...")
        return get_current_price(symbol)  # Probeer opnieuw

# 📌 Functie om accountbalans op te halen van Bybit via ccxt
def fetch_account_balance():
    """Haal de accountbalans op van Bybit via ccxt"""
    exchange = connect_to_bybit()
    try:
        balance = exchange.fetch_balance()
        if 'total' in balance and 'USDT' in balance['total']:
            usdt_balance = balance['total']['USDT']
            logging.info(f"Beschikbaar USDT saldo: {usdt_balance}")
            return {'total': {'USDT': usdt_balance}}
        else:
            logging.error("Saldo USDT niet gevonden.")
            return {'total': {'USDT': 0}}
    except ccxt.NetworkError as e:
        logging.error(f"Netwerkfout bij het ophalen van saldo: {e}. Probeer opnieuw...")
        return fetch_account_balance()  # Probeer opnieuw
    except ccxt.BaseError as e:
        logging.error(f"Fout bij het ophalen van saldo: {e}. Probeer opnieuw...")
        return fetch_account_balance()  # Probeer opnieuw

# 📌 Functie om actieve trades op te halen van Bybit via ccxt
def get_active_trades():
    """Haal de actieve trades op van Bybit via ccxt"""
    exchange = connect_to_bybit()
    try:
        exchange.load_markets()  # Zorg ervoor dat markten geladen zijn
        active_trades = exchange.fetch_open_orders(symbol='BTC/USDT')  # Haal actieve orders op voor BTC/USDT
        trades = []
        for order in active_trades:
            trades.append({
                'symbol': order['symbol'],
                'status': order['status'],
                'current_profit': random.uniform(-STOP_LOSS_PERCENTAGE, TAKE_PROFIT_PERCENTAGE)
            })
        return trades
    except ccxt.NetworkError as e:
        logging.error(f"Netwerkfout bij het ophalen van actieve trades: {e}. Probeer opnieuw...")
        return get_active_trades()  # Probeer opnieuw
    except ccxt.ExchangeError as e:
        logging.error(f"Fout bij het ophalen van actieve trades: {e}. Probeer opnieuw...")
        return get_active_trades()  # Probeer opnieuw
    except Exception as e:
        logging.error(f"Onverwachte fout bij het ophalen van actieve trades: {e}. Probeer opnieuw...")
        return get_active_trades()  # Probeer opnieuw

# 📌 Plaats een echte koop- of verkooporder op Bybit via ccxt
def place_order(symbol, side, amount):
    """Plaats een order op Bybit via ccxt"""
    exchange = connect_to_bybit()
    
    try:
        if side == 'buy':
            order = exchange.create_market_buy_order(symbol, amount)
        elif side == 'sell':
            order = exchange.create_market_sell_order(symbol, amount)
        return order
    except ccxt.NetworkError as e:
        logging.error(f"Netwerkfout bij het plaatsen van order voor {symbol}: {e}. Probeer opnieuw...")
        return place_order(symbol, side, amount)  # Probeer opnieuw
    except ccxt.BaseError as e:
        logging.error(f"Fout bij het plaatsen van order voor {symbol}: {e}. Probeer opnieuw...")
        return place_order(symbol, side, amount)  # Probeer opnieuw

# 📌 Simulatie van echte trade winst/verlies en order uitvoeren
def trade_simulation():
    """Plaats echte orders op basis van de simulatie"""
    while os.path.exists("bot_running.txt"):
        # Verbind met Bybit
        exchange = connect_to_bybit()

        # Kies een willekeurig trading symbool
        symbol = random.choice(TRADING_SYMBOLS)
        current_price = get_current_price(symbol)

        # Bereken de hoeveelheid die je wilt kopen (bijvoorbeeld 2% van de balans)
        balance = fetch_account_balance()
        amount_to_trade = balance['total']['USDT'] * TRADE_PERCENTAGE / current_price

        # Simuleer een trading beslissing op basis van willekeurige winst/verlies
        profit_or_loss = random.uniform(-STOP_LOSS_PERCENTAGE, TAKE_PROFIT_PERCENTAGE)

        # Plaats een order op basis van winst of verlies
        if profit_or_loss > 0:  # Als winst, koop
            print(f"Kooporder plaatsen op {symbol} voor {amount_to_trade} USDT")
            place_order(symbol, 'buy', amount_to_trade)
            send_notification("notify_profit", f"Trade op {symbol} - Winst: {profit_or_loss}%")
        elif profit_or_loss < 0:  # Als verlies, verkoop
            print(f"Verkooporder plaatsen op {symbol} voor {amount_to_trade} USDT")
            place_order(symbol, 'sell', amount_to_trade)
            send_notification("notify_loss", f"Trade op {symbol} - Verlies: {profit_or_loss}%")

        time.sleep(5)  # Wacht 5 seconden voor de volgende simulatie

# 📌 Bot-status bijhouden
def check_bot_running():
    """Controleer of de bot actief is (bestaat het bestand 'bot_running.txt')"""
    return os.path.exists("bot_running.txt")

# 📌 Functie voor het starten van de bot en het simuleren van trades
def start_bot():
    """Start de bot en simuleer de trading"""
    while True:
        if not check_bot_running():
            break
        trade_simulation()

# 📌 Functie voor het starten van de bot
def run_bot():
    """Start de bot en zet 'bot_running.txt' op om aan te geven dat de bot draait"""
    with open("bot_running.txt", "w") as f:
        f.write("running")  # Bot is gestart

    thread = threading.Thread(target=start_bot)
    thread.start()

# 📌 Stop de bot
def stop_bot():
    """Stop de bot door het bestand 'bot_running.txt' te verwijderen"""
    if os.path.exists("bot_running.txt"):
        os.remove("bot_running.txt")

# 📌 Verzend accountinformatie en actieve trades naar het dashboard
def send_dashboard_data():
    """Verzend de accountbalans en actieve trades naar het dashboard"""
    balance = fetch_account_balance()
    active_trades = get_active_trades()

    # Verzenden van accountinformatie naar het dashboard
    socketio.emit('update_balance', {'balance': balance['total']['USDT']})
    
    # Verzenden van actieve trades naar het dashboard
    socketio.emit('update_trades', {'trades': active_trades})

# 📌 Periodieke functie om het dashboard bij te werken
def update_dashboard_periodically():
    """Update het dashboard periodiek"""
    while os.path.exists("bot_running.txt"):
        send_dashboard_data()
        time.sleep(10)  # Update elke 10 seconden

# 📌 Bot starten en dashboard updaten
def start():
    """Start de bot en de periodieke updates voor het dashboard"""
    run_bot()
    update_dashboard_periodically()

if __name__ == "__main__":  # ✅ Correct gebruik van __name__
    start()
    
    # ✅ Host aangepast voor Heroku (0.0.0.0 en dynamische poort)
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
