import subprocess
import os
import json
import logging
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

# ✅ Logging setup (forceer UTF-8 om emoji-fouten te voorkomen)
LOG_FILE = "app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # ✅ Voorkomt UnicodeEncodeError bij emoji's
)

# ✅ Flask en SocketIO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ✅ Variabelen
BOT_PROCESS = None  
BOT_SCRIPT = "lucky13.py"
CONFIG_FILE = "config.json"
BALANCE_FILE = "balance.json"
WINNINGS_FILE = "winnings.json"

# ✅ Root route om de HTML-pagina van het dashboard te tonen
@app.route("/")
def home():
    return render_template("index.html")  

# ✅ Config laden
def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            logging.error("⚠️ Fout bij laden van config.json. Reset naar standaardwaarden.")
    return {'trade_percentage': 0.02, 'stop_loss_percentage': 0.03, 'take_profit_percentage': 0.05}

# ✅ Account balans ophalen
def fetch_account_balance():
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, "r", encoding="utf-8") as file:
                balance_data = json.load(file)
                return {'total': balance_data.get('USDT', 0)}
        except (json.JSONDecodeError, IOError):
            logging.error("⚠️ Balansbestand is corrupt. Reset naar 0 USDT.")
    return {'total': 0}

# ✅ Simuleer actieve trades
def get_active_trades():
    return [{'symbol': s, 'status': 'active', 'current_profit': round(random.uniform(-0.03, 0.05), 2)} for s in ['BTCUSDT', 'ETHUSDT', 'XRPUSDT']]

# ✅ Dashboard data updaten
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    socketio.emit('update_balance', {'balance': balance['total']})
    socketio.emit('update_trades', {'trades': active_trades})

# ✅ Periodieke update van het dashboard
def update_dashboard_periodically():
    def run():
        while True:
            with app.app_context():
                send_dashboard_data()
            socketio.sleep(10)

    socketio.start_background_task(run)

# ✅ Periodieke update van bot-status
def update_bot_status_periodically():
    def run():
        global BOT_PROCESS
        while True:
            bot_running = BOT_PROCESS is not None and BOT_PROCESS.poll() is None
            
            if BOT_PROCESS and BOT_PROCESS.poll() is not None:
                logging.warning("⚠️ Bot is onverwachts gestopt!")
                BOT_PROCESS = None  # Reset de process-variabele

            socketio.emit('bot_status', {'running': bot_running})
            socketio.sleep(10)

    socketio.start_background_task(run)

# ✅ Nieuwe route voor logberichten
@socketio.on('log_message')
def handle_log_message(data):
    log_message = data.get('log', '')
    logging.info(f"Logbericht van bot: {log_message}")
    socketio.emit('log_message', {'log': log_message})

# ✅ Bot starten
@app.route("/start-bot", methods=["POST"])
def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None:
        return jsonify({"status": "⚠️ Bot draait al!"})

    try:
        BOT_PROCESS = subprocess.Popen(
            ["python", BOT_SCRIPT],
            stdout=subprocess.PIPE,  # Log naar stdout
            stderr=subprocess.PIPE,  # Log naar stderr
            universal_newlines=True
        )
        
        # Logberichten van de bot doorsturen naar het dashboard via WebSocket
        def log_output(stream):
            for line in iter(stream.readline, ''):
                socketio.emit('log_message', {'log': line.strip()})
            stream.close()

        # Start loggen van stdout en stderr
        socketio.start_background_task(log_output, BOT_PROCESS.stdout)
        socketio.start_background_task(log_output, BOT_PROCESS.stderr)

        logging.info("✅ Bot gestart!")
        socketio.emit('bot_status', {'running': True})  
        return jsonify({"status": "✅ Bot gestart!"})
    except Exception as e:
        logging.error(f"❌ Fout bij starten van de bot: {e}")
        return jsonify({"status": "❌ Fout bij starten van bot", "error": str(e)})

# ✅ Bot stoppen
@app.route("/stop-bot", methods=["POST"])
def stop_bot():
    global BOT_PROCESS
    if BOT_PROCESS is None:
        return jsonify({"status": "⚠️ Bot is niet actief!"})

    try:
        BOT_PROCESS.terminate()
        BOT_PROCESS.wait()
        BOT_PROCESS = None
        logging.info("❌ Bot gestopt!")
        socketio.emit('bot_status', {'running': False})  
        return jsonify({"status": "✅ Bot gestopt!"})
    except Exception as e:
        logging.error(f"❌ Fout bij stoppen van de bot: {e}")
        return jsonify({"status": "❌ Fout bij stoppen van bot", "error": str(e)})

# ✅ API om instellingen te updaten
@app.route("/api/settings", methods=["POST"])
def update_settings():
    new_settings = request.json
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(new_settings, file, indent=4)
    logging.info("✅ Instellingen bijgewerkt!")
    return jsonify({"message": "✅ Instellingen bijgewerkt!"})

# ✅ Start achtergrondtaken en run Flask server
if __name__ == "__main__":
    logging.info("🚀 Dashboard gestart!")
    
    socketio.start_background_task(update_dashboard_periodically)
    socketio.start_background_task(update_bot_status_periodically)
    
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))