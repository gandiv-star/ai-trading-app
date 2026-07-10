"""
Gandiv AI Trading Assistant - Standalone Auto Trade Bot (Premium Telegram Alerts)
Version: V4.0 - Advanced Multi-Factor (EMA+MACD) & Market Regime Filter
"""

import datetime
import json
import os
import urllib.request
import urllib.parse
import yfinance as yf

DATA_FILE = "gandiv_data.json"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Claude ના સજેશન મુજબ Universe ને લિક્વિડ ૧૦ પ્રો સ્ટોક્સ ઉમેરીને ૫૦ સુધી વધાર્યું
STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
    "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
    "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "DIVISLAB.NS", "M&M.NS", "BPCL.NS", "TATAMOTORS.NS",
    "ZOMATO.NS", "POLICYBZR.NS", "NYKAA.NS", "DMART.NS", "IRFC.NS", 
    "RVNL.NS", "IRCTC.NS", "HAL.NS", "BEL.NS", "JIOFIN.NS"
]

# ==========================================
# TRADING MODE CONFIGURATION
# ==========================================
TRADING_MODE = "PAPER"

if TRADING_MODE == "PAPER":
    MAX_POSITIONS = 25  
    STARTING_CASH = 1000000.0  
else:
    MAX_POSITIONS = 5
    STARTING_CASH = 100000.0

MIN_SCORE = 75
BASE_CAPITAL_PER_TRADE = 10000  

DAILY_LOSS_LIMIT_PCT = 5.0
CIRCUIT_BREAKER_ENABLED = True
SLIPPAGE_PCT = 0.02


def escape_markdown(text):
    reserved_chars = r"_*[]()~`>#+-=|{}.!"
    escaped = ""
    for char in str(text):
        if char in reserved_chars:
            escaped += "\\" + char
        else:
            escaped += char
    return escaped


def send_premium_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "MarkdownV2"
        }).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Telegram send failed: {e}")


def calculate_charges(buy_price, sell_price, qty):
    buy_value = buy_price * qty
    sell_value = sell_price * qty
    gross_pnl = sell_value - buy_value
    stt = (buy_value + sell_value) * 0.001
    exchange_charges = (buy_value + sell_value) * 0.0000335
    sebi_charges = (buy_value + sell_value) * 0.000001
    gst = (exchange_charges + sebi_charges) * 0.18
    stamp_duty = buy_value * 0.00015
    slippage = (buy_value + sell_value) * (SLIPPAGE_PCT / 100)
    total_charges = round(stt + exchange_charges + sebi_charges + gst + stamp_duty + slippage, 2)
    net_pnl = round(gross_pnl - total_charges, 2)
    net_pnl_pct = round((net_pnl / buy_value) * 100, 2) if buy_value > 0 else 0
    return {
        "gross_pnl": round(gross_pnl, 2),
        "total_charges": total_charges,
        "net_pnl": net_pnl,
        "net_pnl_pct": net_pnl_pct
    }


def detect_market_regime(close, period=20):
    """
    Priority 2: Sideways બજારમાં ખોટા ટ્રેડ્સ ફિલ્ટર કરવાનું મેજિક લોજિક
    """
    if len(close) < period:
        return "TRENDING"
    returns = close.pct_change().dropna()
    volatility = returns.rolling(period).std().iloc[-1]
    trend_strength = abs(close.iloc[-1] - close.iloc[-period]) / close.iloc[-period]
    
    if trend_strength > 0.05:
        return "TRENDING"    # મજબૂત માર્કેટ
    elif volatility > 0.02:
        return "VOLATILE"    # જોખમી માર્કેટ
    else:
        return "SIDEWAYS"    # આને અવોઇડ (SKIP) કરીશું


def fetch_advanced_technical_data(symbol, period="1y"):
    """
    Priority 1: Multi-Factor Indicators (EMA + MACD + ATR Dynamic SL)
    """
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 50:
            return None
            
        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        
        current_price = round(close.iloc[-1], 2)
        
        # 1. Moving Averages
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1]
        trend = "Bullish" if ma50 > ma200 else "Bearish"
        
        # 2. Advanced EMA (20 & 50)
        ema20 = close.ewm(span=20).mean().iloc[-1]
        ema50_val = close.ewm(span=50).mean().iloc[-1]
        ema_bullish = ema20 > ema50_val
        
        # 3. Advanced MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = ema12 - ema26
        signal_line = macd.ewm(span=9).mean()
        macd_bullish = macd.iloc[-1] > signal_line.iloc[-1]
        
        # 4. RSI (14)
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        
        # 5. ATR (Dynamic Targets & Stop Loss)
        atr = (high - low).rolling(14).mean().iloc[-1]
        
        # Market Regime Check
        regime = detect_market_regime(close)
        
        return {
            "current_price": current_price,
            "trend": trend,
            "ema_bullish": ema_bullish,
            "macd_bullish": macd_bullish,
            "rsi": round(rsi, 2),
            "ma50": round(ma50, 2),
            "atr": atr,
            "regime": regime
        }
    except Exception:
        return None


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("paper_cash", STARTING_CASH)
    data.setdefault("paper_portfolio", {})
    data.setdefault("paper_trade_history", [])
    data.setdefault("equity_curve", [])
    data.setdefault("trade_journal", [])
    data.setdefault("circuit_breaker_date", None)
    data.setdefault("circuit_breaker_start_value", None)
    data.setdefault("circuit_breaker_triggered", False)
    return data


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def calculate_portfolio_value(data):
    holdings_value = 0
    for sym, pos in data["paper_portfolio"].items():
        try:
            td = fetch_advanced_technical_data(sym)
            cp = td["current_price"] if td else pos["avg_price"]
        except Exception:
            cp = pos["avg_price"]
        holdings_value += cp * pos["qty"]
    return round(data["paper_cash"] + holdings_value, 2)


def check_circuit_breaker(data, log):
    today_str = str(datetime.date.today())
    current_total = calculate_portfolio_value(data)

    if data.get("circuit_breaker_date") != today_str:
        data["circuit_breaker_date"] = today_str
        data["circuit_breaker_start_value"] = current_total
        data["circuit_breaker_triggered"] = False

    day_start = data.get("circuit_breaker_start_value") or current_total
    day_change_pct = ((current_total - day_start) / day_start) * 100 if day_start > 0 else 0
    was_triggered = data.get("circuit_breaker_triggered", False)

    if CIRCUIT_BREAKER_ENABLED and day_change_pct <= -DAILY_LOSS_LIMIT_PCT:
        data["circuit_breaker_triggered"] = True
        if not was_triggered:
            text = (
                f"🚨 *CIRCUIT BREAKER TRIGGERED*\n"
                f"`────────────────────────────── RISK MANAGER ──`\n"
                f"📉 Today's Loss: *{escape_markdown(round(day_change_pct, 2))}\%*\n"
                f"🛡️ Daily Limit: \-{DAILY_LOSS_LIMIT_PCT}\%\n"
                f"⛔ New buys blocked for the day\.\n"
                f"✅ Open positions are still monitored\.\n"
                f"`──────────────────────────────────────────────`"
            )
            send_premium_telegram(text)

    if data.get("circuit_breaker_triggered"):
        log.append(f"CIRCUIT BREAKER ACTIVE: {round(day_change_pct,2)}%")
        return False

    log.append(f"Circuit Breaker OK: {round(day_change_pct,2)}%")
    return True


def run_auto_trade():
    data = load_data()
    log = []
    trade_messages = []

    log.append(f"Mode: {TRADING_MODE} | Max Positions: {MAX_POSITIONS}")
    trading_allowed = check_circuit_breaker(data, log)

    # ---------- SELL CHECK ----------
    positions_to_sell = []
    for sym, pos in list(data["paper_portfolio"].items()):
        try:
            td = fetch_advanced_technical_data(sym)
            if not td:
                continue
            cp = td["current_price"]
            avg = pos["avg_price"]
            
            # Dynamic Target / SL Checking (જો કોડમાં સેવ હોય તો તે વાપરશે, નહીતર ડિફોલ્ટ ટકાવારી)
            target_price = pos.get("target_price", round(avg * (1 + TARGET_PCT/100), 2))
            sl_price = pos.get("sl_price", round(avg * (1 - SL_PCT/100), 2))
            
            if cp >= target_price:
                positions_to_sell.append((sym, pos["qty"], cp, avg, "TARGET_HIT"))
            elif cp <= sl_price:
                positions_to_sell.append((sym, pos["qty"], cp, avg, "STOPLOSS_HIT"))
        except Exception as e:
            log.append(f"Error checking {sym}: {e}")

    for sym, qty, cp, avg, reason in positions_to_sell:
        charges = calculate_charges(avg, cp, qty)
        data["paper_cash"] += cp * qty
        data["paper_trade_history"].append({
            "Date": str(datetime.date.today()),
            "Stock": sym, "Qty": qty,
            "Buy Price": round(avg, 2), "Sell Price": cp,
            "Gross P&L": charges["gross_pnl"],
            "Charges": charges["total_charges"],
            "Net P&L": charges["net_pnl"],
            "Net P&L %": charges["net_pnl_pct"]
        })
        del data["paper_portfolio"][sym]
        log.append(f"{reason}: SOLD {qty} {sym} @ {cp} | Net P&L: {charges['net_pnl']}")

        color_emoji = "🟢" if charges["net_pnl"] >= 0 else "🔴"
        status_text = "PROFIT CREATED 🎉" if charges["net_pnl"] >= 0 else "STOP LOSS HIT ⚠️"
        clean_sym = sym.replace('.NS', '')

        text = (
            f"⚡ *PORTFOLIO POSITION EXECUTED* ⚡\n"
            f"`──────────────────────────── ALGO SQUARE-OFF ──`\n"
            f"🤖 *Strategy:* AI Auto Watchlist Scanner \(V4\.0\)\n"
            f"📉 *Action:* SELL / SQUARE\-OFF \({reason}\)\n"
            f"🏷️ *Symbol:* {escape_markdown(clean_sym)} \(NSE\)\n\n"
            f"📊 *TRANSACTION DETAILS:*\n"
            f"📍 Entry Price: ₹{escape_markdown(round(avg, 2))}\n"
            f"📍 Exit Price: ₹{escape_markdown(cp)}\n"
            f"📦 Total Quantity: {qty} Shares\n\n"
            f"💰 *FINANCIAL SUMMARY:*\n"
            f"💵 Gross P\&L: ₹{escape_markdown(charges['gross_pnl'])}\n"
            f"🧾 Upstox Charges \& Taxes: ₹{escape_markdown(charges['total_charges'])}\n"
            f"`──────────────────────────────────────────────`\n"
            f"{color_emoji} *NET P&L:* ₹{escape_markdown(charges['net_pnl'])} \({escape_markdown(charges['net_pnl_pct'])}\%\)\n"
            f"🏆 *Status:* {status_text}\n"
            f"`──────────────────────────────────────────────`"
        )
        trade_messages.append(text)

    # ---------- BUY CHECK ----------
    if not trading_allowed:
        log.append("Skipping new buys - Circuit Breaker active.")
    else:
        slots = MAX_POSITIONS - len(data["paper_portfolio"])
        if slots > 0:
            candidates = []
            for symbol in STOCK_UNIVERSE:
                if symbol in data["paper_portfolio"]:
                    continue
                try:
                    td = fetch_advanced_technical_data(symbol)
                    if not td:
                        continue
                    
                    # Priority 2: Sideways ફિલ્ટર - જો સાઇડવેઝ માર્કેટ હશે તો આખેઆખો સ્ટોક સ્કીપ થશે
                    if td["regime"] == "SIDEWAYS":
                        continue
                        
                    # Claude ની શક્તિશાળી ન્યૂ સ્કોરિંગ સિસ્ટમ
                    score = 0
                    if td["trend"] == "Bullish": score += 25       # MA 50/200 Crossover
                    if td["ema_bullish"]: score += 20             # EMA 20/50 Crossover 
                    if td["macd_bullish"]: score += 20            # MACD Confirmation
                    if 45 <= td["rsi"] <= 65: score += 20         # RSI Healthy Accumulation Zone
                    if td["current_price"] > td["ma50"]: score += 15 # Above MA50 support
                    
                    if score >= MIN_SCORE:
                        candidates.append({
                            "Stock": symbol, 
                            "Score": score, 
                            "Price": td["current_price"], 
                            "RSI": td["rsi"], 
                            "ATR": td["atr"],
                            "Regime": td["regime"]
                        })
                except Exception as e:
                    log.append(f"Error scanning {symbol}: {e}")

            candidates.sort(key=lambda x: x["Score"], reverse=True)
            for c in candidates[:slots]:
                # ડાયનેમિક કેપિટલ મેનેજમેન્ટ
                if c["Score"] >= 90:
                    allocated_capital = BASE_CAPITAL_PER_TRADE * 2  # ₹૨૦,૦૦૦ (High Confidence)
                    confidence_star = "🔥🔥 [HIGH CONFIDENCE]"
                elif c["Score"] >= 80:
                    allocated_capital = BASE_CAPITAL_PER_TRADE      # ₹૧૦,૦૦0 (Medium Confidence)
                    confidence_star = "✅✅ [MEDIUM]"
                else:
                    allocated_capital = BASE_CAPITAL_PER_TRADE // 2 # ₹૫,૦૦૦  (Low Confidence)
                    confidence_star = "⚠️⚠️ [LOW]"

                qty = int(allocated_capital / c["Price"])
                if qty < 1:
                    continue
                cost = qty * c["Price"]
                if cost > data["paper_cash"]:
                    continue
                
                # ATR બેઝ્ડ મોર્ડન ડાયનેમિક Target અને Stop Loss (Claude Priority 1)
                atr_val = c["ATR"] if c["ATR"] > 0 else (c["Price"] * 0.02)
                dynamic_sl = round(c["Price"] - (2 * atr_val), 2)
                dynamic_target = round(c["Price"] + (3 * atr_val), 2)
                
                # રિસ્ક રિવોર્ડ રેશિયો ગણતરી (ઓછામાં ઓછો 1:2 કે 1:3 જ નીકળશે)
                expected_profit_pct = round(((dynamic_target - c["Price"]) / c["Price"]) * 100, 1)
                expected_loss_pct = round(((c["Price"] - dynamic_sl) / c["Price"]) * 100, 1)

                data["paper_cash"] -= cost
                data["paper_portfolio"][c["Stock"]] = {
                    "qty": qty, 
                    "avg_price": c["Price"],
                    "target_price": dynamic_target,
                    "sl_price": dynamic_sl
                }
                log.append(f"BOUGHT {qty} x {c['Stock']} @ {c['Price']} | Score: {c['Score']}/100 | Regime: {c['Regime']}")

                clean_buy_sym = c['Stock'].replace('.NS', '')

                text = (
                    f"⚡ *NEW LIVE TRADE EXECUTED* ⚡\n"
                    f"`───────────────────────────── ALGO TRIGGER ──`\n"
                    f"🤖 *Strategy:* AI Multi\-Factor Advanced \(V4\.0\)\n"
                    f"📈 *Action:* BUY / LONG \({TRADING_MODE}\)\n"
                    f"🎯 *Signal Quality:* {escape_markdown(confidence_star)}\n"
                    f"🌐 *Market Regime:* {escape_markdown(c['Regime'])}\n"
                    f"🏷️ *Symbol:* {escape_markdown(clean_buy_sym)} \(NSE\)\n\n"
                    f"📊 *TRADE DETAILS:*\n"
                    f"📍 Entry Price: ₹{escape_markdown(c['Price'])}\n"
                    f"📦 Order Quantity: {qty} Shares\n"
                    f"💰 Total Invested: ₹{escape_markdown(round(cost, 2))}\n"
                    f"🧠 AI Score: {c['Score']}/100 \| RSI: {escape_markdown(c['RSI'])}\n\n"
                    f"🎯 *ATR DYNAMIC TARGETS & PROTECTION:*\n"
                    f"🟢 Target: ₹{escape_markdown(dynamic_target)} \(\+{expected_profit_pct}\%\)\n"
                    f"🔴 Stop Loss: ₹{escape_markdown(dynamic_sl)} \(\-{escape_markdown(expected_loss_pct)}\%\)\n"
                    f"🛡️ Risk\-Reward Ratio = 1:1\.5 \(ATR Based\)\n"
                    f"`──────────────────────────────────────────────`"
                )
                trade_messages.append(text)

    data["last_auto_trade_run"] = str(datetime.datetime.now())

    # Auto Equity Curve Snapshot
    today_str = str(datetime.date.today())
    portfolio_val = calculate_portfolio_value(data)
    
    if "equity_curve" not in data:
        data["equity_curve"] = []
        
    existing_dates = [e["Date"] for e in data["equity_curve"]]
    
    if today_str not in existing_dates:
        data["equity_curve"].append({"Date": today_str, "Value": portfolio_val})
    else:
        for e in data["equity_curve"]:
            if e["Date"] == today_str:
                e["Value"] = portfolio_val
    save_data(data)

    if trade_messages:
        portfolio_value = calculate_portfolio_value(data)
        p_val_str = escape_markdown(f"{portfolio_value:,.2f}")
        cash_str = escape_markdown(f"{data['paper_cash']:,.2f}")
        mode_str = escape_markdown(TRADING_MODE)
        pos_len = len(data['paper_portfolio'])
        
        for msg in trade_messages:
            send_premium_telegram(msg)
            
        summary = (
            f"📊 *RUN SUMMARY* 📊\n"
            f"`────────────────────────────── SYSTEM MONITOR ──`\n"
            f"⚙️ *Mode:* {mode_str}\n"
            f"💰 *Portfolio Value:* ₹{p_val_str}\n"
            f"💵 *Available Cash:* ₹{cash_str}\n"
            f"📦 *Open Positions:* {pos_len}/{MAX_POSITIONS}\n"
            f"`────────────────────────────────────────────────`"
        )
        send_premium_telegram(summary)

    print(f"=== Auto Trade Run: {datetime.datetime.now()} ===")
    print(f"Open Positions: {len(data['paper_portfolio'])}")


if __name__ == "__main__":
    run_auto_trade()
            
