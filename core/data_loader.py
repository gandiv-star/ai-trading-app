"""
Gandiv AI Trading Terminal - Core Data & Quant Engine (v5.0 Pro)
Features: Market Regime Detection, 100-Point Confluence Scoring, ATR Calculations
"""

import pandas as pd
import numpy as np
import yfinance as yf

def calculate_atr(df, period=14):
    """Calculates Average True Range (ATR) for dynamic stop loss"""
    try:
        high = df['High']
        low = df['Low']
        close = df['Close']
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0
    except Exception:
        return 0.0

def detect_market_regime(df, period=20):
    """
    Identifies Market Regime: TRENDING, SIDEWAYS, or VOLATILE using ADX & Returns
    """
    try:
        if len(df) < 30:
            return "UNKNOWN"

        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Calculate ADX (Average Directional Index) approximation
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr = np.maximum(high - low, np.maximum(abs(high - close.shift(1)), abs(low - close.shift(1))))
        atr = pd.Series(tr).rolling(14).mean()

        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-6)
        adx = dx.rolling(14).mean().iloc[-1]

        # Price Trend & Volatility
        trend_strength = abs(close.iloc[-1] - close.iloc[-period]) / close.iloc[-period]
        volatility = close.pct_change().tail(period).std()

        if adx > 22 or trend_strength > 0.04:
            return "TRENDING"
        elif volatility > 0.022:
            return "VOLATILE"
        else:
            return "SIDEWAYS"
    except Exception:
        return "TRENDING"

def calculate_confluence_score(df):
    """
    V5.0 Quant Engine: Calculates 100-Point Confluence Score & AI Confidence Reason
    """
    try:
        if len(df) < 50:
            return 0, "Insufficient Data", "UNKNOWN", 0.0

        close = df["Close"]
        volume = df["Volume"]
        
        # Completed Candle Data (iloc[-2])
        prev_close = float(close.iloc[-2])
        prev_open = float(df["Open"].iloc[-2])
        curr_price = float(close.iloc[-1])

        # Technical Indicators
        ema20 = float(close.ewm(span=20).mean().iloc[-2])
        ema50 = float(close.ewm(span=50).mean().iloc[-2])
        ma200 = float(close.rolling(200).mean().iloc[-2]) if len(close) >= 200 else float(close.rolling(50).mean().iloc[-2])
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-6)
        rsi = float((100 - (100 / (1 + rs))).iloc[-2])

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        is_macd_bullish = bool(macd.iloc[-2] > signal.iloc[-2])

        # Volume Spurt Check
        avg_vol = float(volume.tail(20).mean())
        curr_vol = float(volume.iloc[-1])
        is_volume_high = curr_vol > (avg_vol * 1.2)

        # Market Regime
        regime = detect_market_regime(df)
        atr_val = calculate_atr(df)

        # SCORING SYSTEM (100 MARKS)
        score = 0
        reasons = []

        # 1. Trend Alignment (25 Marks)
        if prev_close > ema20 and ema20 > ema50:
            score += 25
            reasons.append("Strong Uptrend (EMA 20>50)")
        elif prev_close > ema20:
            score += 15
            reasons.append("Above EMA 20")

        # 2. Momentum & RSI (25 Marks)
        if 48 <= rsi <= 68:
            score += 25
            reasons.append(f"Healthy RSI ({round(rsi,1)})")
        elif rsi > 40:
            score += 10

        # 3. MACD Confirmation (20 Marks)
        if is_macd_bullish:
            score += 20
            reasons.append("MACD Bullish Cross")

        # 4. Volume Spurt (15 Marks)
        if is_volume_high:
            score += 15
            reasons.append("High Volume Spurt")

        # 5. Price Candle Quality & Regime Match (15 Marks)
        if prev_close > prev_open:
            score += 10
            reasons.append("Bullish Closed Candle")
        
        if regime == "TRENDING":
            score += 5
        elif regime == "SIDEWAYS":
            # Penalty for Sideways market to avoid fake breakouts
            score -= 10

        score = max(min(score, 100), 0)
        confidence_text = " | ".join(reasons) if reasons else "Weak Technical Setup"

        return score, confidence_text, regime, atr_val

    except Exception as e:
        return 0, f"Error: {str(e)}", "UNKNOWN", 0.0

def fetch_technical_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="60d", interval="1d")
        if df.empty:
            return None
        return df
    except Exception:
        return None

def calculate_charges(buy_price, sell_price, qty):
    buy_val = buy_price * qty
    sell_val = sell_price * qty
    gross_pnl = sell_val - buy_val
    charges = round((buy_val + sell_val) * 0.0012, 2)
    net_pnl = round(gross_pnl - charges, 2)
    net_pnl_pct = round((net_pnl / buy_val) * 100, 2) if buy_val > 0 else 0.0
    return {"gross_pnl": gross_pnl, "total_charges": charges, "net_pnl": net_pnl, "net_pnl_pct": net_pnl_pct}
    
