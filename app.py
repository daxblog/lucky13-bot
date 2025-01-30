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

# Initialiseer Flask en SocketIO
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Variabele om het bot-proces bij te houden
BOT_PROCESS = None  
BOT_SCRIPT = "lucky13.py"  # De naam van het bot-script

CONFIG_FILE = "config.json"

# 📌 Configuratie-instellingen laden
def load_settings():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    return {
        'trade_percentage': 0.02,
        'stop_loss_percentage': 0.03,
        'take_profit_percentage': 0.05
    }

# 📌 Instellingen opslaan
def save_settings(settings):
    with open(CONFIG_FILE, "w") as file:
        json.dump(settings, file, indent=4)

# 📌 Simulatie: Actieve trades ophalen
def get_active_trades():
    trades = []
    for symbol in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']:
        trade = {
            'symbol': symbol,
            'status': 'active',
            'current_profit': round(random.uniform(-0.03, 0.05), 2)
        }
        trades.append(trade)
    return trades

# 📌 Simulatie: Accountbalans ophalen
def fetch_account_balance():
    return {'total': {'USDT': 1000}}

# 📌 Verzend accountinformatie naar het dashboard
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    socketio.emit('update_balance', {'balance': balance['total']['USDT']})
    socketio.emit('update_trades', {'trades': active_trades})

# 📌 Periodieke functie voor het updaten van het dashboard
def update_dashboard_periodically():
    while True:
        send_dashboard_data()
        time.sleep(10)  # Elke 10 seconden bijwerken

# 📌 Start de bot (`lucky13.py`) als een apart proces
@app.route("/start-bot", methods=["POST"])
def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None:
        return jsonify({"status": "Bot is already running!"})
    
    BOT_PROCESS = subprocess.Popen(["python", BOT_SCRIPT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logging.info("Bot gestart.")
    return jsonify({"status": "Bot started successfully!"})

# 📌 Stop de bot door het proces te beëindigen
@app.route("/stop-bot", methods=["POST"])
def stop_bot():
    global BOT_PROCESS
    if BOT_PROCESS is None:
        return jsonify({"status": "Bot is not running!"})

    os.kill(BOT_PROCESS.pid, signal.SIGTERM)
    BOT_PROCESS = None
    logging.info("Bot gestopt.")
    return jsonify({"status": "Bot stopped successfully!"})

# 📌 Controleer of de bot draait
@app.route("/bot-status", methods=["GET"])
def bot_status():
    return jsonify({"running": BOT_PROCESS is not None})

# 📌 API om logs op te halen
@app.route("/logs", methods=["GET"])
def get_logs():
    try:
        with open(LOG_FILE, "r") as file:
            logs = file.readlines()
        return jsonify({"logs": logs[-50:]})  # Laatste 50 regels tonen
    except Exception as e:
        return jsonify({"error": str(e)})

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
    threading.Thread(target=update_dashboard_periodically, daemon=True).start()
    logging.info("Server gestart op poort %d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
