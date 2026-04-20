import requests
from flask import Flask
import threading

TELEGRAM_TOKEN = "TU_TOKEN"
CHAT_ID = "TU_CHAT_ID"

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo 🚀"

def send_test():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": "🔥 BOT NUEVO FUNCIONANDO 🔥"
    })
    print("RESPUESTA TELEGRAM:", r.text)

def start():
    send_test()

if __name__ == "__main__":
    threading.Thread(target=start).start()
    app.run(host="0.0.0.0", port=8080)
