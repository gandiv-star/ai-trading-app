"""
Gandiv AI Trading Assistant - Standalone Auto Trade Bot (Premium Telegram Alerts)
Updated: Full MarkdownV2 Support & Standard Formatting (No Backslash in f-string)
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

STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
    "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
    "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "DIVISLAB.NS", "M&M.NS", "BPCL.NS", "TATAMOTORS.NS"
]

# ==========================================
# TRADING MODE CONFIGURATION
# ==========================================
TRADING_MODE = "PAPER"

if TRADING_MODE == "PAPER":
    MAX_POSITIONS = 25  # ૧૦૦% સક્સેસ ટેસ્ટિંગ માટે લિમિટ ૨૫ કરી દીધી
    CAPITAL_PER_TRADE = 10000
    STARTING_CASH = 1000000.0  # અહીં ₹૧૦,૦૦,૦૦૦ સેટ છે
else:
    MAX_POSITIONS = 5
    CAPITAL_PER_TRADE = 20000
    STARTING_CASH = 100000.0

MIN_SCORE = 75
TARGET_PCT = 4.0
SL_PCT = 2.5
DAILY_LOSS_LIMIT_PCT = 5.0
CIRCUIT_BREAKER_ENABLED = True
SLIPPAGE_PCT = 0.02


def escape_markdown(text):
    """
    MarkdownV2 માટે અનિવાર્ય અક્ષરોને ઓટોમેટીક સેફ કરે છે જેથી બોટ ક્યારેય અટકે નહીં.
    """
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


def fetch_technical_data(symbol, period="1y"):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=period)
        if hist.empty:
            return None
        close = hist["Close"]
        current_price = round(close.iloc[-1], 2)
        ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.mean()
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else close.mean()
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = (100 - (100 / (1 + rs))).iloc[-1]
        trend = "Bullish" if ma50 > ma200 else "Bearish"
        return {
            "current_price": current_price,
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "rsi": round(rsi, 2),
            "trend": trend,
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
            td = fetch_technical_data(sym)
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
            td = fetch_technical_data(sym)
            if not td:
                continue
            cp = td["current_price"]
            avg = pos["avg_price"]
            change_pct = ((cp - avg) / avg) * 100
            if change_pct >= TARGET_PCT:
                positions_to_sell.append((sym, pos["qty"], cp, avg, "TARGET"))
            elif change_pct <= -SL_PCT:
                positions_to_sell.append((sym, pos["qty"], cp, avg, "STOPLOSS"))
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
            f"🤖 *Strategy:* AI Auto Watchlist Scanner \(V36\)\n"
            f"📉 *Action:* SELL / SQUARE\-OFF \({reason}\)\n"
            f"🏷️ *Symbol:* {escape_markdown(clean_sym)} \(NSE\)\n\n"
            f"📊 *TRANSACTION DETAILS:*\n"
            f"📍 Entry Price: ₹{escape_markdown(round(avg, 2))}\n"
            f"📍 Exit Price: ₹{escape_markdown(cp)}\n"
            f"📦 Total Quantity: {qty} Shares\n\n"
            f"💰 *FINANCIAL SUMMARY:*\n"
            f"💵 Gross P\&L: ₹{escape_markdown(charges['gross_pnl'])}\n"
            f"🧾 Upstox Charges \& Taxes: ₹{escape_markdown(charges['total_charges'])}\n"
            f"📉 Slippage Cost \({SLIPPAGE_PCT}\%\): Included\n"
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
                    td = fetch_technical_data(symbol)
                    if not td:
                        continue
                    rsi = td["rsi"]
                    trend = td["trend"]
                    cp = td["current_price"]
                    ma50 = td["ma50"]
                    score = 50
                    if trend == "Bullish": score += 20
                    if 45 <= rsi <= 65: score += 20
                    elif rsi < 30: score += 5
                    if cp > ma50: score += 10
                    if score >= MIN_SCORE:
                        candidates.append({"Stock": symbol, "Score": score, "Price": cp, "RSI": rsi})
                except Exception as e:
                    log.append(f"Error scanning {symbol}: {e}")

            candidates.sort(key=lambda x: x["Score"], reverse=True)
            for c in candidates[:slots]:
                qty = int(CAPITAL_PER_TRADE / c["Price"])
                if qty < 1:
                    continue
                cost = qty * c["Price"]
                if cost > data["paper_cash"]:
                    continue
                data["paper_cash"] -= cost
                data["paper_portfolio"][c["Stock"]] = {"qty": qty, "avg_price": c["Price"]}
                log.append(f"BOUGHT {qty} x {c['Stock']} @ {c['Price']} | Score: {c['Score']}/100")

                target = round(c["Price"] * (1 + TARGET_PCT/100), 2)
                sl = round(c["Price"] * (1 - SL_PCT/100), 2)
                rr = round(TARGET_PCT / SL_PCT, 2)
                clean_buy_sym = c['Stock'].replace('.NS', '')

                text = (
                    f"⚡ *NEW LIVE TRADE EXECUTED* ⚡\n"
                    f"`───────────────────────────── ALGO TRIGGER ──`\n"
                    f"🤖 *Strategy:* AI Auto Watchlist Scanner \(V36\)\n"
                    f"📈 *Action:* BUY / LONG \({TRADING_MODE}\)\n"
                    f"🏷️ *Symbol:* {escape_markdown(clean_buy_sym)} \(NSE\)\n\n"
                    f"📊 *TRADE DETAILS:*\n"
                    f"📍 Entry Price: ₹{escape_markdown(c['Price'])}\n"
                    f"📦 Order Quantity: {qty} Shares\n"
                    f"💰 Total Invested: ₹{escape_markdown(round(cost, 2))}\n"
                    f"🧠 AI Score: {c['Score']}/100 \| RSI: {escape_markdown(c['RSI'])}\n\n"
                    f"🎯 *TARGETS & PROTECTION:*\n"
                    f"🟢 Target: ₹{escape_markdown(target)} \(\+{TARGET_PCT}\%\)\n"
                    f"🔴 Stop Loss: ₹{escape_markdown(sl)} \(\-{SL_PCT}\%\)\n"
                    f"🛡️ Risk\-Reward Ratio: 1:{escape_markdown(rr)}\n"
                    f"📉 Est\. Slippage: {SLIPPAGE_PCT}\% Included\n"
                    f"`──────────────────────────────────────────────`"
                )
                trade_messages.append(text)

    data["last_auto_trade_run"] = str(datetime.datetime.now())

    # Auto Equity Curve Snapshot (daily at market close)
    today_str = str(datetime.date.today())
    portfolio_val = calculate_portfolio_value(data)
    
    if "equity_curve" not in data:
        data["equity_curve"] = []
        
    existing_dates = [e["Date"] for e in data["equity_curve"]]
    
    if today_str not in existing_dates:
        data["equity_curve"].append({
            "Date": today_str,
            "Value": portfolio_val
        })
        log.append(f"Auto Equity Snapshot Created: ₹{portfolio_val}")
    else:
        for e in data["equity_curve"]:
            if e["Date"] == today_str:
                e["Value"] = portfolio_val
        log.append(f"Auto Equity Snapshot Updated: ₹{portfolio_val}")

    save_data(data)

    if trade_messages:
        portfolio_value = calculate_portfolio_value(data)
        
        # આ પ્યોર અને કન્વર્ટેડ વેલ્યુઝ છે જેથી f-string ની અંદર ડાયરેક્ટ વેરીએબલ રન થાય (કોઈ બૅકસ્લેશ નથી)
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
    print(f"Mode: {TRADING_MODE} | Max Positions: {MAX_POSITIONS}")
    for entry in log:
        print(entry)
    print(f"Open Positions: {len(data['paper_portfolio'])}")
    print(f"Cash: {data['paper_cash']:.2f}")


if __name__ == "__main__":
    run_auto_trade()
                                           
