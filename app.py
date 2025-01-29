from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS  # Importeer CORS
import os
import time
import random
import json
import threading

# Initialiseer Flask en SocketIO
app = Flask(__name__)  # Correcte initialisatie

# Voeg CORS toe aan je app om cross-origin verzoeken toe te staan
CORS(app)  # Hiermee worden alle origin-toegang toegestaan

socketio = SocketIO(app, cors_allowed_origins="*")  # Hiermee configureer je de SocketIO connectie

# Bestandsnaam voor de configuratie
CONFIG_FILE = "config.json"

# 📌 Configuratie-instellingen laden
def load_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    return {
        'trade_percentage': 0.02,  # 2% van saldo wordt geïnvesteerd
        'stop_loss_percentage': 0.03,  # Stop loss op 3% verlies
        'take_profit_percentage': 0.05  # Take profit op 5% winst
    }

# 📌 Instellingen opslaan
def save_settings(settings):
    with open(CONFIG_FILE, "w") as file:
        json.dump(settings, file, indent=4)

# 📌 Functie om de actieve trades op te halen (simulatie)
def get_active_trades():
    trades = []
    for symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']:  # Voeg hier je eigen symbolen toe
        trade = {
            'symbol': symbol,
            'status': 'active',
            'current_profit': round(random.uniform(-0.03, 0.05), 2)  # Random winst/verlies
        }
        trades.append(trade)
    return trades

# 📌 Functie voor het ophalen van de accountbalans (simulatie)
def fetch_account_balance():
    # Simuleer een accountbalans van 1000 USDT
    return {'total': {'USDT': 1000}}

# 📌 Verzend accountinformatie naar het dashboard
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()

    # Verzend accountbalans naar het dashboard
    socketio.emit('update_balance', {'balance': balance['total']['USDT']})
    
    # Verzend actieve trades naar het dashboard
    socketio.emit('update_trades', {'trades': active_trades})

# 📌 Periodieke functie die dashboard data bijwerkt
def update_dashboard_periodically():
    while os.path.exists("bot_running.txt"):
        send_dashboard_data()
        time.sleep(10)  # Updates elke 10 seconden

# 📌 Start de bot en periodieke update van dashboard
def start_dashboard_updater():
    # Verifiëren of de bot al draait
    if os.path.exists("bot_running.txt"):
        update_dashboard_periodically()

# 📌 Start de bot (simulatie)
@app.route("/start-bot", methods=["POST"])
def start_bot():
    # Verifiëren of de bot al draait
    if os.path.exists("bot_running.txt"):
        return jsonify({"status": "Bot is already running!"})
    
    # Start de bot en schrijf naar bestand
    with open("bot_running.txt", "w") as f:
        f.write("running")  # Schrijf naar bestand zodat we weten dat de bot draait
    
    # Start de update van het dashboard in een aparte thread
    threading.Thread(target=start_dashboard_updater).start()
    
    return jsonify({"status": "Bot started successfully!"})

# 📌 Stop de bot
@app.route("/stop-bot", methods=["POST"])
def stop_bot():
    if os.path.exists("bot_running.txt"):
        os.remove("bot_running.txt")  # Verwijder het bestand om de bot te stoppen
        return jsonify({"status": "Bot stopped successfully!"})
    else:
        return jsonify({"status": "Bot is not running!"})

# 📌 Start de app en serveer de HTML-pagina
@app.route("/")
def index():
    return render_template("index.html")  # Zorg ervoor dat je een index.html hebt

# 📌 Route voor het ophalen van de instellingen
@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = load_settings()
    return jsonify(settings)

# 📌 Route voor het bijwerken van de instellingen
@app.route("/api/settings", methods=["POST"])
def update_settings():
    new_settings = request.json
    save_settings(new_settings)
    return jsonify({"message": "Instellingen bijgewerkt!"})

if __name__ == "__main__":  # Correct gebruik van __name__
    # Verkrijg de poort uit de omgevingsvariabelen van Heroku (of gebruik 5000 als fallback)
    port = int(os.environ.get("PORT", 5000))

    # Start de Flask server met SocketIO en dynamische poort
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
