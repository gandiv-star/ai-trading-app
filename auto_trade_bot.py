"""
Gandiv AI Trading Assistant - Standalone Auto Trade Bot (Premium Telegram Alerts)
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
TRADING_MODE = "PAPER"  # "PAPER" અથવા "LIVE" - આ એક line બદલવાથી બધું switch થશે

if TRADING_MODE == "PAPER":
    MAX_POSITIONS = 20
    CAPITAL_PER_TRADE = 5000
else:
    MAX_POSITIONS = 5
    CAPITAL_PER_TRADE = 10000

MIN_SCORE = 75
TARGET_PCT = 4.0
SL_PCT = 2.5
DAILY_LOSS_LIMIT_PCT = 5.0
CIRCUIT_BREAKER_ENABLED = True
SLIPPAGE_PCT = 0.02


def send_telegram(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
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


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("paper_cash", 100000.0)
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
                "🚨 <b>CIRCUIT BREAKER TRIGGERED</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📉 Today's Loss: <b>{round(day_change_pct,2)}%</b>\n"
                f"🛡️ Limit: -{DAILY_LOSS_LIMIT_PCT}%\n"
                "⛔ New buys blocked for today.\n"
                "✅ Existing positions still monitored.\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            send_telegram(text)

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

        emoji = "🎯" if reason == "TARGET" else "🛑"
        title = "TARGET HIT - PROFIT BOOKED" if reason == "TARGET" else "STOP LOSS HIT"
        pnl_emoji = "🟢" if charges["net_pnl"] >= 0 else "🔴"
        status = "PROFIT" if charges["net_pnl"] >= 0 else "LOSS"

        text = (
            f"{emoji} <b>{title}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📌 Symbol: <b>{sym.replace('.NS','')}</b>\n"
            f"📍 Entry: ₹{round(avg,2)}\n"
            f"📍 Exit: ₹{cp}\n"
            f"📦 Qty: {qty} shares\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"💵 Gross P&L: ₹{charges['gross_pnl']}\n"
            f"🧾 Charges (Tax+Slippage): ₹{charges['total_charges']}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{pnl_emoji} <b>NET P&L: ₹{charges['net_pnl']} ({charges['net_pnl_pct']}%)</b>\n"
            f"Status: {status}\n"
            "━━━━━━━━━━━━━━━━━━"
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

                text = (
                    "⚡ <b>NEW TRADE EXECUTED</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📈 Action: BUY (Paper)\n"
                    f"📌 Symbol: <b>{c['Stock'].replace('.NS','')}</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"📍 Entry: ₹{c['Price']}\n"
                    f"📦 Qty: {qty} shares\n"
                    f"💰 Invested: ₹{round(cost,2):,}\n"
                    f"🧠 AI Score: {c['Score']}/100 | RSI: {c['RSI']}\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    f"🟢 Target: ₹{target} (+{TARGET_PCT}%)\n"
                    f"🔴 Stop Loss: ₹{sl} (-{SL_PCT}%)\n"
                    f"⚖️ Risk:Reward = 1:{rr}\n"
                    "━━━━━━━━━━━━━━━━━━"
                )
                trade_messages.append(text)

    data["last_auto_trade_run"] = str(datetime.datetime.now())
    save_data(data)

    if trade_messages:
        portfolio_value = calculate_portfolio_value(data)
        for msg in trade_messages:
            send_telegram(msg)
        summary = (
            "📊 <b>RUN SUMMARY</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🔧 Mode: {TRADING_MODE}\n"
            f"💰 Portfolio Value: ₹{portfolio_value:,.2f}\n"
            f"💵 Available Cash: ₹{data['paper_cash']:,.2f}\n"
            f"📦 Open Positions: {len(data['paper_portfolio'])}/{MAX_POSITIONS}\n"
            "━━━━━━━━━━━━━━━━━━"
        )
        send_telegram(summary)

    print(f"=== Auto Trade Run: {datetime.datetime.now()} ===")
    print(f"Mode: {TRADING_MODE} | Max Positions: {MAX_POSITIONS}")
    for entry in log:
        print(entry)
    print(f"Open Positions: {len(data['paper_portfolio'])}")
    print(f"Cash: {data['paper_cash']:.2f}")


if __name__ == "__main__":
    run_auto_trade()
