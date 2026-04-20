import os
import requests
import pandas as pd
import time
import threading
from flask import Flask
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("API_KEY")

app = Flask(__name__)
last_trade_time = None

@app.route("/")
def home():
    return "PRECISION BOT ONLINE 🎯"

def send(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def get_data(symbol):
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/2025-01-01/2026-12-31?apiKey={API_KEY}"
    r = requests.get(url).json()
    if 'results' not in r:
        return None
    df = pd.DataFrame(r['results'])
    df['close'] = df['c']
    df['volume'] = df['v']
    return df

def add_indicators(df):
    df['ema9'] = EMAIndicator(df['close'], 9).ema_indicator()
    df['ema21'] = EMAIndicator(df['close'], 21).ema_indicator()
    df['rsi'] = RSIIndicator(df['close'], 14).rsi()
    df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    df['rvol'] = df['volume'] / df['volume'].rolling(20).mean()
    return df

def vix_change(vix, n=10):
    return (vix['close'].iloc[-1] - vix['close'].iloc[-n]) / vix['close'].iloc[-n] * 100

def vix_turn(vix):
    # giro = la última vela cambia la pendiente de las 3 previas
    return (vix['close'].iloc[-1] < vix['close'].iloc[-2] and
            vix['close'].iloc[-2] > vix['close'].iloc[-3] > vix['close'].iloc[-4]) or \
           (vix['close'].iloc[-1] > vix['close'].iloc[-2] and
            vix['close'].iloc[-2] < vix['close'].iloc[-3] < vix['close'].iloc[-4])

def low_range(df):
    rng = (df['close'].iloc[-10:].max() - df['close'].iloc[-10:].min()) / df['close'].iloc[-10:].mean()
    return rng < 0.002

def valid_time():
    now = datetime.utcnow()
    h, m = now.hour, now.minute
    # NY aprox UTC: 14–21
    if (h == 14 and m < 40): return False
    if (h == 17): return False
    return 14 <= h <= 20

def cooldown():
    global last_trade_time
    if last_trade_time is None: return True
    return datetime.utcnow() - last_trade_time > timedelta(minutes=12)

def vwap_band_ok(price, vwap):
    # solo operar cerca de VWAP (±0.3%)
    return abs(price - vwap) / vwap < 0.003

def delta_strike(price, direction):
    # aproximación práctica: ligeramente ITM
    if direction == "CALL":
        return round(price - 1)  # ~delta 0.35–0.45 en intradía
    else:
        return round(price + 1)

def trend_5m_proxy(df):
    # proxy simple: usa medias de 1m para inferir 5m
    return df['ema21'].iloc[-1] - df['ema21'].iloc[-5]

def signal_loop():
    global last_trade_time
    send("🎯 PRECISION BOT ACTIVO")
    send("BOT VIVO Y MONITOREANDO 📡")
    
    while True:
        try:
            if not valid_time():
                time.sleep(60); continue

            spy = get_data("SPY")
            vix = get_data("VIX")
            if spy is None or vix is None:
                time.sleep(60); continue

            spy = add_indicators(spy)
            vix = add_indicators(vix)

            if low_range(spy) or not cooldown():
                time.sleep(60); continue

            last = spy.iloc[-1]
            prev = spy.iloc[-2]

            vix_move = vix_change(vix, 10)
            turn = vix_turn(vix)

            # volumen relativo
            if last['rvol'] < 1.2:
                time.sleep(60); continue

            # CALL precisión
            if (
                vix_move > 4 and turn and
                last['rsi'] < 35 and last['rsi'] > prev['rsi'] and
                last['close'] < last['vwap'] and vwap_band_ok(last['close'], last['vwap']) and
                prev['ema9'] < prev['ema21'] and last['ema9'] > last['ema21'] and
                trend_5m_proxy(spy) >= 0
            ):
                price = round(last['close'], 2)
                strike = delta_strike(price, "CALL")
                send(f"""🎯 CALL PRECISION
Precio: {price}
Strike: {strike} CALL (0DTE)
Setup: Reversión VWAP + giro VIX + RVOL
Confianza: MUY ALTA""")
                last_trade_time = datetime.utcnow()

            # PUT precisión
            if (
                vix_move < -4 and turn and
                last['rsi'] > 65 and last['rsi'] < prev['rsi'] and
                last['close'] > last['vwap'] and vwap_band_ok(last['close'], last['vwap']) and
                prev['ema9'] > prev['ema21'] and last['ema9'] < last['ema21'] and
                trend_5m_proxy(spy) <= 0
            ):
                price = round(last['close'], 2)
                strike = delta_strike(price, "PUT")
                send(f"""🎯 PUT PRECISION
Precio: {price}
Strike: {strike} PUT (0DTE)
Setup: Rechazo VWAP + giro VIX + RVOL
Confianza: MUY ALTA""")
                last_trade_time = datetime.utcnow()

            time.sleep(60)

        except Exception as e:
            print(e)
            time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=signal_loop).start()
    app.run(host="0.0.0.0", port=8080)
