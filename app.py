import subprocess
import os
import signal
import time
import json
import random
import threading
import logging
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
import eventlet  # Voeg eventlet toe om te zorgen voor betere concurrency met SocketIO

# Logging setup
LOG_FILE = "app.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Flask en SocketIO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")  # Gebruik eventlet voor concurrency

# Variabelen
BOT_PROCESS = None  
BOT_SCRIPT = "lucky13.py"
CONFIG_FILE = "config.json"
BALANCE_FILE = "balance.json"
WINNINGS_FILE = "winnings.json"  # Bestand voor de winsten

# 📌 Configuratie-instellingen laden
def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error("Fout bij het laden van config.json. Bestandsinhoud is ongeldig.")
    return {
        'trade_percentage': 0.02,
        'stop_loss_percentage': 0.03,
        'take_profit_percentage': 0.05
    }

# 📌 Instellingen opslaan
def save_settings(settings):
    with open(CONFIG_FILE, "w") as file:
        json.dump(settings, file, indent=4)

# 📌 Actieve trades ophalen (simulatie)
def get_active_trades():
    return [
        {
            'symbol': symbol,
            'status': 'active',
            'current_profit': round(random.uniform(-0.03, 0.05), 2)
        } for symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']
    ]

# 📌 Accountbalans ophalen vanuit balance.json
def fetch_account_balance():
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, "r") as file:
                balance_data = json.load(file)
                return {'total': balance_data.get('USDT', 0)}
        except json.JSONDecodeError:
            logging.error("Balansbestand is corrupt. Reset naar 0 USDT.")
    return {'total': 0}

# 📌 Winsten ophalen vanuit winnings.json
def fetch_winnings():
    if os.path.exists(WINNINGS_FILE):
        try:
            with open(WINNINGS_FILE, "r") as file:
                winnings_data = json.load(file)
                return winnings_data.get("total_win", 0)
        except json.JSONDecodeError:
            logging.error("Winningsbestand is corrupt. Reset naar 0 winst.")
    return 0

# 📌 Verzend accountinformatie naar het dashboard via SocketIO
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()

    logging.info("Dashboard geüpdatet: Balans %s USDT", balance['total'])
    socketio.emit('update_balance', {'balance': balance['total']})
    socketio.emit('update_trades', {'trades': active_trades})

# 📌 Periodieke functie voor het updaten van het dashboard
def update_dashboard_periodically():
    def run():
        while True:
            send_dashboard_data()
            time.sleep(10)  # Elke 10 seconden bijwerken

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

# 📌 Start de bot (`lucky13.py`) als een apart proces
@app.route("/start-bot", methods=["POST"])
def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None:
        return jsonify({"status": "Bot is already running!"})

    try:
        BOT_PROCESS = subprocess.Popen(["python", BOT_SCRIPT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("Bot gestart.")
        return jsonify({"status": "Bot started successfully!"})
    except Exception as e:
        logging.error("Fout bij starten van de bot: %s", str(e))
        return jsonify({"status": "Failed to start bot", "error": str(e)})

# 📌 Stop de bot door het proces te beëindigen
@app.route("/stop-bot", methods=["POST"])
def stop_bot():
    global BOT_PROCESS
    if BOT_PROCESS is None:
        return jsonify({"status": "Bot is not running!"})

    try:
        BOT_PROCESS.terminate()  # Gebruik terminate() in plaats van os.kill voor een schonere afsluiting
        BOT_PROCESS.wait()  # Wacht tot het proces is beëindigd
        BOT_PROCESS = None
        logging.info("Bot gestopt.")
        return jsonify({"status": "Bot stopped successfully!"})
    except Exception as e:
        logging.error("Fout bij stoppen van de bot: %s", str(e))
        return jsonify({"status": "Failed to stop bot", "error": str(e)})

# 📌 Controleer of de bot draait
@app.route("/bot-status", methods=["GET"])
def bot_status():
    return jsonify({"running": BOT_PROCESS is not None})

# 📌 API om logs op te halen (laatste 50 regels)
@app.route("/logs", methods=["GET"])
def get_logs():
    try:
        with open(LOG_FILE, "r") as file:
            logs = file.readlines()
        return jsonify({"logs": logs[-50:]})  # Laatste 50 regels tonen
    except Exception as e:
        return jsonify({"error": str(e)})

# 📌 API om winsten op te halen
@app.route("/api/winnings", methods=["GET"])
def get_winnings():
    winnings = fetch_winnings()
    return jsonify({"winnings": winnings})

# 📌 Dashboardpagina serveren
@app.route("/")
def index():
    return render_template("index.html")

# 📌 API om instellingen op te halen
@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = load_settings()
    return jsonify(settings)

# 📌 API om instellingen bij te werken
@app.route("/api/settings", methods=["POST"])
def update_settings():
    new_settings = request.json
    save_settings(new_settings)
    logging.info("Instellingen bijgewerkt: %s", new_settings)
    return jsonify({"message": "Instellingen bijgewerkt!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    update_dashboard_periodically()
    logging.info("Server gestart op poort %d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False)  # Zorg ervoor dat debug=False is in productie