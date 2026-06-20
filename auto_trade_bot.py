"""
Gandiv AI Trading Assistant - Standalone Auto Trade Bot
This script runs independently of Streamlit (for GitHub Actions scheduling).
It reads/writes the same gandiv_data.json file used by the Streamlit app.
Includes Circuit Breaker check (shares state with Streamlit app via the JSON file).
"""

import datetime
import json
import os
import yfinance as yf

DATA_FILE = "gandiv_data.json"

STOCK_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
    "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
    "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
    "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
    "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS", "BAJAJFINSV.NS",
    "DRREDDY.NS", "CIPLA.NS", "GRASIM.NS", "HEROMOTOCO.NS",
    "EICHERMOT.NS", "DIVISLAB.NS", "TATAMOTORS.NS", "M&M.NS", "BPCL.NS"
]

# ---------- AUTO TRADE SETTINGS (same defaults as app) ----------
MAX_POSITIONS = 5
CAPITAL_PER_TRADE = 10000
MIN_SCORE = 75
TARGET_PCT = 8.0
SL_PCT = 5.0

# ---------- CIRCUIT BREAKER SETTINGS (must match app defaults) ----------
DAILY_LOSS_LIMIT_PCT = 5.0
CIRCUIT_BREAKER_ENABLED = True


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
    """Returns True if trading should proceed, False if circuit breaker is active."""
    today_str = str(datetime.date.today())
    current_total = calculate_portfolio_value(data)

    # Reset start-of-day value on new day
    if data.get("circuit_breaker_date") != today_str:
        data["circuit_breaker_date"] = today_str
        data["circuit_breaker_start_value"] = current_total
        data["circuit_breaker_triggered"] = False

    day_start = data.get("circuit_breaker_start_value") or current_total
    day_change_pct = ((current_total - day_start) / day_start) * 100 if day_start > 0 else 0

    if CIRCUIT_BREAKER_ENABLED and day_change_pct <= -DAILY_LOSS_LIMIT_PCT:
        data["circuit_breaker_triggered"] = True

    if data.get("circuit_breaker_triggered"):
        log.append(f"CIRCUIT BREAKER ACTIVE: Today's change {round(day_change_pct,2)}% <= -{DAILY_LOSS_LIMIT_PCT}% limit. New buys blocked.")
        return False

    log.append(f"Circuit Breaker OK: Today's change {round(day_change_pct,2)}% (limit -{DAILY_LOSS_LIMIT_PCT}%)")
    return True


def run_auto_trade():
    data = load_data()
    log = []

    # ---------- STEP 0: CIRCUIT BREAKER CHECK ----------
    trading_allowed = check_circuit_breaker(data, log)

    # ---------- STEP 1: CHECK EXISTING HOLDINGS FOR TARGET/SL ----------
    # NOTE: Selling is always allowed, even if circuit breaker is active
    # (closing positions reduces risk, it should never be blocked).
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
                positions_to_sell.append((sym, pos["qty"], cp, "TARGET_HIT"))
            elif change_pct <= -SL_PCT:
                positions_to_sell.append((sym, pos["qty"], cp, "STOPLOSS_HIT"))
        except Exception as e:
            log.append(f"Error checking {sym}: {e}")

    for sym, qty, cp, reason in positions_to_sell:
        holding = data["paper_portfolio"][sym]
        proceeds = cp * qty
        profit = (cp - holding["avg_price"]) * qty
        profit_pct = round(((cp - holding["avg_price"]) / holding["avg_price"]) * 100, 2)

        data["paper_cash"] += proceeds
        data["paper_trade_history"].append({
            "Date": str(datetime.date.today()),
            "Stock": sym,
            "Qty": qty,
            "Buy Price": round(holding["avg_price"], 2),
            "Sell Price": cp,
            "P&L": round(profit, 2),
            "P&L %": profit_pct
        })
        del data["paper_portfolio"][sym]
        log.append(f"{reason}: SOLD {qty} {sym} @ {cp} | P&L: {round(profit,2)} ({profit_pct}%)")

    # ---------- STEP 2: SCAN FOR NEW BUY OPPORTUNITIES (only if circuit breaker allows) ----------
    if not trading_allowed:
        log.append("Skipping new buys - Circuit Breaker is active.")
    else:
        current_positions = len(data["paper_portfolio"])
        slots_available = MAX_POSITIONS - current_positions

        if slots_available > 0:
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
            top_candidates = candidates[:slots_available]

            for c in top_candidates:
                qty = int(CAPITAL_PER_TRADE / c["Price"])
                if qty < 1:
                    continue
                cost = qty * c["Price"]
                if cost > data["paper_cash"]:
                    continue

                data["paper_cash"] -= cost
                data["paper_portfolio"][c["Stock"]] = {"qty": qty, "avg_price": c["Price"]}
                log.append(f"BOUGHT {qty} x {c['Stock']} @ {c['Price']} | Score: {c['Score']}/100")

    # ---------- SAVE ----------
    data["last_auto_trade_run"] = str(datetime.datetime.now())
    save_data(data)

    # ---------- PRINT LOG (visible in GitHub Actions logs) ----------
    print(f"=== Auto Trade Run: {datetime.datetime.now()} ===")
    for entry in log:
        print(entry)
    print(f"Open Positions: {len(data['paper_portfolio'])}")
    print(f"Cash: {data['paper_cash']:.2f}")


if __name__ == "__main__":
    run_auto_trade()
                    
