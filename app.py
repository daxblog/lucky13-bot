import subprocess
import os
import json
import random
import logging
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

# Logging setup
LOG_FILE = "app.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Flask en SocketIO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# Variabelen
BOT_PROCESS = None  
BOT_SCRIPT = "lucky13.py"
CONFIG_FILE = "config.json"
BALANCE_FILE = "balance.json"
WINNINGS_FILE = "winnings.json"

# ✅ Verwijder "Lucky13 Bot Dashboard is running!" en geef een nette JSON-response
@app.route("/")
def home():
    return jsonify({"status": "API is online", "message": "Gebruik de beschikbare API-routes."})

# Dashboard route die een HTML-pagina retourneert
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")  # Zorg ervoor dat je een dashboard.html bestand hebt

# Config laden
def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error("Fout bij laden van config.json. Reset standaardwaarden.")
    return {'trade_percentage': 0.02, 'stop_loss_percentage': 0.03, 'take_profit_percentage': 0.05}

# Account balans ophalen
def fetch_account_balance():
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, "r") as file:
                balance_data = json.load(file)
                return {'total': balance_data.get('USDT', 0)}
        except (json.JSONDecodeError, IOError):
            logging.error("Balansbestand is corrupt. Reset naar 0 USDT.")
    return {'total': 0}

# Simuleer actieve trades
def get_active_trades():
    return [{'symbol': s, 'status': 'active', 'current_profit': round(random.uniform(-0.03, 0.05), 2)} for s in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']]

# Dashboard data updaten
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    socketio.emit('update_balance', {'balance': balance['total']})
    socketio.emit('update_trades', {'trades': active_trades})

# Periodieke update van het dashboard
def update_dashboard_periodically():
    def run():
        while True:
            with app.app_context():
                send_dashboard_data()
            socketio.sleep(10)

    socketio.start_background_task(run)

# Periodieke update van bot-status
def update_bot_status_periodically():
    def run():
        while True:
            bot_running = BOT_PROCESS is not None and BOT_PROCESS.poll() is None
            socketio.emit('bot_status', {'running': bot_running})
            socketio.sleep(10)

    socketio.start_background_task(run)

# Bot starten
@app.route("/start-bot", methods=["POST"])
def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None:
        return jsonify({"status": "Bot is already running!"})

    try:
        BOT_PROCESS = subprocess.Popen(
            ["python", BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        socketio.emit('bot_status', {'running': True})  # ✅ Directe update
        return jsonify({"status": "Bot started successfully!"})
    except Exception as e:
        return jsonify({"status": "Failed to start bot", "error": str(e)})

# Bot stoppen
@app.route("/stop-bot", methods=["POST"])
def stop_bot():
    global BOT_PROCESS
    if BOT_PROCESS is None:
        return jsonify({"status": "Bot is not running!"})

    try:
        BOT_PROCESS.terminate()
        BOT_PROCESS.wait()
        BOT_PROCESS = None
        socketio.emit('bot_status', {'running': False})  # ✅ Directe update
        return jsonify({"status": "Bot stopped successfully!"})
    except Exception as e:
        return jsonify({"status": "Failed to stop bot", "error": str(e)})

# API om instellingen te updaten
@app.route("/api/settings", methods=["POST"])
def update_settings():
    new_settings = request.json
    with open(CONFIG_FILE, "w") as file:
        json.dump(new_settings, file, indent=4)
    return jsonify({"message": "Instellingen bijgewerkt!"})

# ✅ Verwijder gunicorn run call, gebruik de correcte manier om Heroku te draaien
if __name__ == "__main__":
    update_dashboard_periodically()
    update_bot_status_periodically()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
