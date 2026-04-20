import requests
import pandas as pd
import time
import threading
from flask import Flask
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from datetime import datetime

# ================= CONFIG =================
TELEGRAM_TOKEN = "TU_TOKEN"
CHAT_ID = "TU_CHAT_ID"
API_KEY = "TU_API_KEY"
# ==========================================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot activo "

def send(msg):
    print("ENVIANDO MENSAJE A TELEGRAM:", msg)
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    print("RESPUESTA TELEGRAM:", r.text)

def get_data(symbol):
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/2025-01-01/2026-12-31?apiKey={API_KEY}"
    r = requests.get(url).json()
    
    if 'results' not in r:
        return None

    df = pd.DataFrame(r['results'])
    df['close'] = df['c']
    df['open'] = df['o']
    df['high'] = df['h']
    df['low'] = df['l']
    df['volume'] = df['v']
    return df

def indicators(df):
    df['ema9'] = EMAIndicator(df['close'], 9).ema_indicator()
    df['ema21'] = EMAIndicator(df['close'], 21).ema_indicator()
    df['rsi'] = RSIIndicator(df['close'], 14).rsi()
    df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    return df

def vix_impulse(vix):
    return (vix['close'].iloc[-1] - vix['close'].iloc[-10]) / vix['close'].iloc[-10] * 100

def signal_loop():
    print("INICIANDO BOT...")  
    send("BOT FUNCIONANDO 🚀")  

    while True:
        try:
            spy = get_data("SPY")
            vix = get_data("VIX")

            if spy is None or vix is None:
                time.sleep(60)
                continue

            spy = indicators(spy)
            vix = indicators(vix)

            last = spy.iloc[-1]
            move = vix_impulse(vix)

            if move > 5 and last['rsi'] < 35:
                price = round(last['close'], 2)
                strike = round(price)

                send(f"🚨 CALL\nPrecio: {price}\nStrike: {strike}")

            if move < -5 and last['rsi'] > 65:
                price = round(last['close'], 2)
                strike = round(price)

                send(f"🚨 PUT\nPrecio: {price}\nStrike: {strike}")

            time.sleep(60)

        except Exception as e:
            print(e)
            time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=signal_loop).start()
    app.run(host="0.0.0.0", port=8080)
