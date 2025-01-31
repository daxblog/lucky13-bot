import subprocess
import os
import json
import logging
import random
import eventlet  # 🔄 Fix voor live WebSocket-updates
from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO
from flask_cors import CORS

# 🔧 Eventlet inschakelen voor niet-blokkerende WebSockets
eventlet.monkey_patch()

# ✅ Logging setup
LOG_FILE = "app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)

# ✅ Flask en SocketIO setup
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ✅ Variabelen
BOT_PROCESS = None
BOT_SCRIPT = "lucky13.py"
BALANCE_FILE = "balance.json"

# ✅ Homepagina
@app.route("/")
def home():
    return render_template("index.html")

# ✅ Laad balansgegevens
def fetch_account_balance():
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, "r", encoding="utf-8") as file:
                balance_data = json.load(file)
                return {"total": balance_data.get("USDT", 0)}
        except (json.JSONDecodeError, IOError):
            logging.error("⚠️ Balansbestand is corrupt. Reset naar 0 USDT.")
    return {"total": 0}

# ✅ Simuleer actieve trades
def get_active_trades():
    return [
        {"symbol": s, "status": "active", "current_profit": round(random.uniform(-0.03, 0.05), 2)}
        for s in ["BTCUSDT", "ETHUSDT", "XRPUSDT"]
    ]

# ✅ Stuur live dashboard-updates
def send_dashboard_data():
    balance = fetch_account_balance()
    active_trades = get_active_trades()
    socketio.emit("update_balance", {"balance": balance["total"]})
    socketio.emit("update_trades", {"trades": active_trades})

# ✅ Live dashboard updates in een aparte achtergrondthread
def update_dashboard_continuously():
    while True:
        send_dashboard_data()
        socketio.sleep(5)  # 🔄 Update elke 5 sec

# ✅ Controleer of bot actief is
def update_bot_status_continuously():
    global BOT_PROCESS
    while True:
        bot_running = BOT_PROCESS is not None and BOT_PROCESS.poll() is None
        socketio.emit("bot_status", {"running": bot_running})
        socketio.sleep(5)  # 🔄 Check elke 5 sec

# ✅ Start de bot
@app.route("/start-bot", methods=["POST"])
def start_bot():
    global BOT_PROCESS
    if BOT_PROCESS is not None:
        return jsonify({"status": "⚠️ Bot draait al!"})

    try:
        BOT_PROCESS = subprocess.Popen(
            ["python", BOT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # 🔄 Flush stdout direct
        )

        # ✅ Real-time logs verzenden
        def log_output(stream):
            while True:
                line = stream.readline()
                if not line:
                    break  # 🔄 Stop als de stream leeg is
                socketio.emit("log_message", {"log": line.strip()})

        eventlet.spawn(log_output, BOT_PROCESS.stdout)
        eventlet.spawn(log_output, BOT_PROCESS.stderr)

        logging.info("✅ Bot gestart!")
        return jsonify({"status": "✅ Bot gestart!"})
    except Exception as e:
        logging.error(f"❌ Fout bij starten van de bot: {e}")
        return jsonify({"status": "❌ Fout bij starten van bot", "error": str(e)})

# ✅ Stop de bot
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
        socketio.emit("bot_status", {"running": False})
        return jsonify({"status": "✅ Bot gestopt!"})
    except Exception as e:
        logging.error(f"❌ Fout bij stoppen van de bot: {e}")
        return jsonify({"status": "❌ Fout bij stoppen van bot", "error": str(e)})

# ✅ Start Flask + WebSockets
if __name__ == "__main__":
    logging.info("🚀 Dashboard gestart!")
    eventlet.spawn(update_dashboard_continuously)
    eventlet.spawn(update_bot_status_continuously)
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), allow_unsafe_werkzeug=True)
