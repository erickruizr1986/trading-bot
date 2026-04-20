import requests
import pandas as pd
import time
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from datetime import datetime

# ================= CONFIG =================
TELEGRAM_TOKEN = "TU_TOKEN"
CHAT_ID = "TU_CHAT_ID"
API_KEY = "TU_API_KEY"
# ==========================================

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

# ================= FILTROS =================

def market_hours():
    now = datetime.utcnow()
    ny_hour = now.hour - 4
    return (9 <= ny_hour <= 11) or (14 <= ny_hour <= 16)

def avoid_news():
    # evita días típicos de alta volatilidad (simplificado)
    day = datetime.utcnow().day
    return day <= 3

def strong_trend(df):
    return abs(df['ema9'].iloc[-1] - df['ema21'].iloc[-1]) > 0.1

def rejection(df):
    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    wick = last['high'] - last['low']
    return wick > body * 2

def volume_spike(df):
    return df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1] * 1.2

def vix_impulse(vix):
    return (vix['close'].iloc[-1] - vix['close'].iloc[-10]) / vix['close'].iloc[-10] * 100

# ================= SCORE =================

def score(spy, vix):
    s = 0
    
    if abs(vix_impulse(vix)) > 5:
        s += 25
        
    if volume_spike(spy):
        s += 20
        
    if strong_trend(spy):
        s += 20
        
    if rejection(spy):
        s += 15
        
    if abs(spy['close'].iloc[-1] - spy['vwap'].iloc[-1]) < 0.3:
        s += 10
        
    if spy['rsi'].iloc[-1] < 35 or spy['rsi'].iloc[-1] > 65:
        s += 10
        
    return s

# ================= STRIKE =================

def best_strike(price, strength):
    if strength >= 90:
        return round(price - 1)  # ITM
    return round(price)         # ATM

# ================= SIGNAL =================

def signal(spy, vix):
    if not market_hours():
        return None, 0

    if avoid_news():
        return None, 0

    last = spy.iloc[-1]
    move = vix_impulse(vix)
    sc = score(spy, vix)

    if sc < 80:
        return None, sc

    # CALL
    if move > 5 and last['rsi'] < 35 and rejection(spy):
        return "CALL", sc

    # PUT
    if move < -5 and last['rsi'] > 65 and rejection(spy):
        return "PUT", sc

    return None, sc

# ================= LOOP =================

while True:
    try:
        spy = get_data("SPY")
        vix = get_data("VIX")

        if spy is None or vix is None:
            time.sleep(60)
            continue

        spy = indicators(spy)
        vix = indicators(vix)

        sig, sc = signal(spy, vix)

        if sig:
            price = round(spy['close'].iloc[-1], 2)
            strike = best_strike(price, sc)

            msg = f"""
🚨 SETUP INSTITUCIONAL {sig}

Activo: SPY
Precio: {price}

Strike: {strike} {sig}
Expiración: HOY (0DTE)

Confianza: {sc}%

Checklist:
✔ VIX con impulso real
✔ Volumen institucional
✔ Rechazo confirmado
✔ Tendencia válida

Gestión:
SL: -20%
TP: +50% / +80%
"""
            send(msg)

        time.sleep(60)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(60)
