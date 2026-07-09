import datetime
import json
import os
import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Gandiv AI Trading",
    page_icon="📈",
    layout="wide"
)

# ==========================================
# DARK THEME CSS
# ==========================================
st.markdown("""
<style>
    /* Dark Background */
    .stApp {
        background-color: #0D1117;
    }

    /* Main Title */
    h1 {
        background: linear-gradient(135deg, #00FF88, #00BFFF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2rem;
    }

    /* Headers */
    h2, h3, h4 {
        color: #00BFFF !important;
        font-weight: 700;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #161B22;
        border-radius: 12px;
        padding: 4px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: #8B949E !important;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #00FF88, #00BFFF) !important;
        color: #0D1117 !important;
    }

    /* Metric Cards */
    [data-testid="stMetric"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 0 15px rgba(0, 255, 136, 0.08);
    }
    [data-testid="stMetricLabel"] {
        color: #8B949E !important;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: #00FF88 !important;
        font-weight: 800;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #00FF88, #00BFFF);
        color: #0D1117 !important;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 700;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 35px rgba(0, 255, 136, 0.6);
    }
    .stButton > button p {
        color: #0D1117 !important;
        font-weight: 700;
    }

    /* Input Fields */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        background-color: #161B22 !important;
        color: #E6EDF3 !important;
        border: 1px solid #30363D !important;
        border-radius: 8px !important;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background-color: #161B22 !important;
        color: #E6EDF3 !important;
        border: 1px solid #30363D !important;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border: 1px solid #30363D;
        border-radius: 10px;
        overflow: hidden;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
    }

    /* Success/Error/Warning/Info */
    .stSuccess {
        background-color: rgba(0, 255, 136, 0.1) !important;
        border: 1px solid #00FF88 !important;
        border-radius: 10px;
    }
    .stError {
        background-color: rgba(255, 23, 68, 0.1) !important;
        border: 1px solid #FF1744 !important;
        border-radius: 10px;
    }
    .stWarning {
        background-color: rgba(255, 160, 0, 0.1) !important;
        border: 1px solid #FFA000 !important;
        border-radius: 10px;
    }
    .stInfo {
        background-color: rgba(0, 191, 255, 0.1) !important;
        border: 1px solid #00BFFF !important;
        border-radius: 10px;
    }

    /* General Text */
    p, label, span, div {
        color: #E6EDF3 !important;
    }

    /* Divider */
    hr {
        border-color: #30363D !important;
    }

    /* Slider */
    .stSlider label p {
        color: #E6EDF3 !important;
        font-weight: 600 !important;
    }

    /* Caption */
    .stCaption {
        color: #8B949E !important;
    }

    /* Checkbox */
    .stCheckbox label p {
        color: #E6EDF3 !important;
    }

    /* Radio */
    .stRadio label p {
        color: #E6EDF3 !important;
    }

    /* Markdown text */
    .stMarkdown p {
        color: #E6EDF3 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# AI MODEL
# ==========================================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

# ==========================================
# DATA PERSISTENCE
# ==========================================
DATA_FILE = "gandiv_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            st.session_state.paper_cash = data.get("paper_cash", 100000.0)
            st.session_state.paper_portfolio = data.get("paper_portfolio", {})
            st.session_state.paper_trade_history = data.get("paper_trade_history", [])
            st.session_state.equity_curve = data.get("equity_curve", [])
            st.session_state.trade_journal = data.get("trade_journal", [])
        except Exception:
            st.session_state.paper_cash = 100000.0
            st.session_state.paper_portfolio = {}
            st.session_state.paper_trade_history = []
            st.session_state.equity_curve = []
            st.session_state.trade_journal = []
    else:
        st.session_state.paper_cash = 100000.0
        st.session_state.paper_portfolio = {}
        st.session_state.paper_trade_history = []
        st.session_state.equity_curve = []
        st.session_state.trade_journal = []

def save_data():
    data = {
        "paper_cash": st.session_state.paper_cash,
        "paper_portfolio": st.session_state.paper_portfolio,
        "paper_trade_history": st.session_state.paper_trade_history,
        "equity_curve": st.session_state.equity_curve,
        "trade_journal": st.session_state.trade_journal,
    }
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Save Error: {e}")

if "data_loaded" not in st.session_state:
    load_data()
    st.session_state.data_loaded = True

# ==========================================
# SHARED DATA
# ==========================================
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

SECTOR_MAP = {
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS"],
    "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS"],
    "Auto": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "HEROMOTOCO.NS", "EICHERMOT.NS"],
    "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS"],
    "Metal": ["TATASTEEL.NS", "JSWSTEEL.NS"],
    "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS"],
    "Finance": ["BAJFINANCE.NS", "BAJAJFINSV.NS"],
    "Infra": ["LT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS"],
    "Telecom": ["BHARTIARTL.NS"],
    "Paints": ["ASIANPAINT.NS"],
    "Consumer": ["TITAN.NS"]
}

# ==========================================
# HELPER FUNCTIONS
# ==========================================
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
            "hist": hist
        }
    except:
        return None

def calculate_charges(buy_price, sell_price, qty, slippage_pct=0.02):
    buy_value = buy_price * qty
    sell_value = sell_price * qty
    gross_pnl = sell_value - buy_value

    # Upstox Equity Delivery - Official Charges
    brokerage = 0  # Free delivery
    stt = (buy_value + sell_value) * 0.001
    exchange_charges = (buy_value + sell_value) * 0.0000335
    sebi_charges = (buy_value + sell_value) * 0.000001
    gst = (brokerage + exchange_charges + sebi_charges) * 0.18
    stamp_duty = buy_value * 0.00015
    slippage = (buy_value + sell_value) * (slippage_pct / 100)

    total_charges = round(stt + exchange_charges + sebi_charges + gst + stamp_duty + slippage, 2)
    net_pnl = round(gross_pnl - total_charges, 2)
    net_pnl_pct = round((net_pnl / buy_value) * 100, 2) if buy_value > 0 else 0

    return {
        "buy_value": round(buy_value, 2),
        "sell_value": round(sell_value, 2),
        "gross_pnl": round(gross_pnl, 2),
        "brokerage": 0,
        "stt": round(stt, 2),
        "exchange_charges": round(exchange_charges, 4),
        "sebi_charges": round(sebi_charges, 4),
        "gst": round(gst, 4),
        "stamp_duty": round(stamp_duty, 2),
        "slippage": round(slippage, 2),
        "total_charges": total_charges,
        "net_pnl": net_pnl,
        "net_pnl_pct": net_pnl_pct
    }

# ==========================================
# TITLE + TABS
# ==========================================
st.title("📈 Gandiv AI Trading Terminal")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Dashboard",
    "💰 Trading",
    "🔍 Scanners",
    "🤖 AI Tools",
    "📊 Analytics"
])
# ==========================================
# TAB 1: DASHBOARD
# ==========================================
with tab1:
    st.subheader("🏠 Market Dashboard")

    # Portfolio Summary
    dash_holdings_value = 0
    for sym, pos in st.session_state.paper_portfolio.items():
        try:
            td = fetch_technical_data(sym)
            cp = td["current_price"] if td else pos["avg_price"]
        except:
            cp = pos["avg_price"]
        dash_holdings_value += cp * pos["qty"]

    dash_total = round(st.session_state.paper_cash + dash_holdings_value, 2)
    dash_invested = sum(pos["qty"] * pos["avg_price"] for pos in st.session_state.paper_portfolio.values())
    dash_pnl = round(dash_holdings_value - dash_invested, 2)
    dash_pnl_pct = round((dash_pnl / dash_invested) * 100, 2) if dash_invested > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Total Value", f"₹{dash_total:,.2f}")
    col2.metric("📈 Holdings", f"₹{dash_holdings_value:,.2f}")
    col3.metric("💵 Cash", f"₹{st.session_state.paper_cash:,.2f}")
    if dash_pnl >= 0:
        col4.metric("📊 Unrealized P&L", f"₹{dash_pnl:,.2f}", f"+{dash_pnl_pct}%")
    else:
        col4.metric("📊 Unrealized P&L", f"₹{dash_pnl:,.2f}", f"{dash_pnl_pct}%")

    st.divider()

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown("#### 🌐 Market Pulse")
        if st.button("📡 Check Nifty", key="dash_nifty"):
            try:
                nifty = fetch_technical_data("^NSEI", period="6mo")
                if nifty:
                    mood = "🟢 Bullish" if nifty["trend"] == "Bullish" else "🔴 Bearish"
                    n1, n2, n3 = st.columns(3)
                    n1.metric("Nifty", f"{nifty['current_price']}")
                    n2.metric("RSI", f"{nifty['rsi']}")
                    n3.metric("Trend", mood)
            except Exception as e:
                st.error(f"Error: {e}")

    with col_d2:
        st.markdown("#### 🤖 Bot Status")
        pos_count = len(st.session_state.paper_portfolio)
        MAX_POS_DISPLAY = 25
        if pos_count >= MAX_POS_DISPLAY:
            st.error(f"🔴 Portfolio Full ({pos_count}/{MAX_POS_DISPLAY})")
        elif pos_count >= MAX_POS_DISPLAY * 0.7:
            st.warning(f"🟡 {pos_count}/{MAX_POS_DISPLAY} Positions Open")
        else:
            st.success(f"🟢 {pos_count}/{MAX_POS_DISPLAY} - Ready to Trade")
        if "last_auto_trade_run" in st.session_state:
            st.caption(f"Last Bot Run: {st.session_state.last_auto_trade_run}")

    st.divider()

    # Open Positions
    st.markdown("#### 📋 Open Positions")
    if st.session_state.paper_portfolio:
        for sym, pos in st.session_state.paper_portfolio.items():
            try:
                td = fetch_technical_data(sym)
                cp = td["current_price"] if td else pos["avg_price"]
            except:
                cp = pos["avg_price"]
            pnl = round((cp - pos["avg_price"]) * pos["qty"], 2)
            pnl_pct = round(((cp - pos["avg_price"]) / pos["avg_price"]) * 100, 2)
            color = "🟢" if pnl >= 0 else "🔴"
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.write(f"**{sym.replace('.NS','')}**")
            c2.write(f"₹{cp}")
            c3.write(f"Qty: {pos['qty']}")
            c4.write(f"{color} ₹{pnl}")
            c5.write(f"{pnl_pct}%")
    else:
        st.info("કોઈ Open Positions નથી.")

    st.divider()

    # Circuit Breaker
    st.markdown("#### 🚨 Circuit Breaker")
    if "circuit_breaker_triggered" not in st.session_state:
        st.session_state.circuit_breaker_triggered = False
    if "circuit_breaker_date" not in st.session_state:
        st.session_state.circuit_breaker_date = None
    if "circuit_breaker_start_value" not in st.session_state:
        st.session_state.circuit_breaker_start_value = None

    today_str = str(datetime.date.today())
    if st.session_state.circuit_breaker_date != today_str:
        st.session_state.circuit_breaker_date = today_str
        st.session_state.circuit_breaker_start_value = dash_total
        st.session_state.circuit_breaker_triggered = False

    day_start = st.session_state.circuit_breaker_start_value or dash_total
    day_change = round(((dash_total - day_start) / day_start) * 100, 2) if day_start > 0 else 0

    cb1, cb2, cb3 = st.columns(3)
    cb1.metric("Today Start", f"₹{day_start:,.2f}")
    cb2.metric("Current", f"₹{dash_total:,.2f}")
    cb3.metric("Today Change", f"{day_change}%")

    if day_change <= -5.0:
        st.session_state.circuit_breaker_triggered = True
        st.error("🚨 CIRCUIT BREAKER! Daily -5% exceeded. Trading Blocked.")
        if st.button("🔓 Override", key="cb_override"):
            st.session_state.circuit_breaker_triggered = False
            st.success("✅ Resumed")
    else:
        st.success(f"✅ Safe | Today: {day_change}% | Limit: -5.0%")

# ==========================================
# TAB 2: TRADING
# ==========================================
with tab2:
    st.subheader("💰 Paper Trading Terminal")
    st.metric("💵 Available Cash", f"₹{st.session_state.paper_cash:,.2f}")

    trade_tab1, trade_tab2, trade_tab3, trade_tab4 = st.tabs([
        "✅ Buy/Sell", "📡 Live Tracker", "📒 History", "🧮 Calculator"
    ])

    with trade_tab1:
        col_buy, col_sell = st.columns(2)

        with col_buy:
            st.markdown("#### ✅ Buy Stock")
            pt_symbol = st.text_input("Symbol", value="RELIANCE.NS", key="pt_buy_symbol")
            pt_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="pt_buy_qty")
            st.caption("Upstox Delivery = 0% Brokerage")

            if st.button("✅ Buy Now", key="buy_btn"):
                try:
                    td = fetch_technical_data(pt_symbol)
                    if td:
                        price = td["current_price"]
                        cost = round(price * pt_qty, 2)
                        stamp = round(cost * 0.00015, 2)
                        total_cost = round(cost + stamp, 2)

                        if total_cost > st.session_state.paper_cash:
                            st.error(f"❌ Cash ઓછું! જોઈએ: ₹{total_cost:,.2f}")
                        else:
                            st.session_state.paper_cash -= total_cost
                            if pt_symbol in st.session_state.paper_portfolio:
                                ex = st.session_state.paper_portfolio[pt_symbol]
                                total_qty = ex["qty"] + pt_qty
                                new_avg = ((ex["qty"] * ex["avg_price"]) + cost) / total_qty
                                st.session_state.paper_portfolio[pt_symbol] = {
                                    "qty": total_qty, "avg_price": round(new_avg, 2)
                                }
                            else:
                                st.session_state.paper_portfolio[pt_symbol] = {
                                    "qty": pt_qty, "avg_price": price
                                }
                            save_data()
                            st.success(f"✅ BOUGHT {pt_qty}x {pt_symbol} @ ₹{price}")
                            st.caption(f"Stamp Duty: ₹{stamp} | Total Cost: ₹{total_cost}")
                    else:
                        st.error("Data મળ્યો નથી")
                except Exception as e:
                    st.error(f"Error: {e}")

        with col_sell:
            st.markdown("#### 🔴 Sell Stock")
            if st.session_state.paper_portfolio:
                sell_symbol = st.selectbox(
                    "Stock", list(st.session_state.paper_portfolio.keys()), key="sell_sym"
                )
                holding = st.session_state.paper_portfolio[sell_symbol]
                st.caption(f"Held: {holding['qty']} | Avg: ₹{round(holding['avg_price'],2)}")
                sell_qty = st.number_input(
                    "Qty", min_value=1, max_value=int(holding["qty"]),
                    value=int(holding["qty"]), key="sell_qty"
                )
                slip_pct = st.slider("Slippage %", 0.0, 0.1, 0.02, 0.01, key="slip_pct")
                st.caption(f"Slippage: {slip_pct}%")

                if st.button("🔴 Sell Now", key="sell_btn"):
                    try:
                        td = fetch_technical_data(sell_symbol)
                        if td:
                            cp = td["current_price"]
                            charges = calculate_charges(
                                holding["avg_price"], cp, sell_qty, slip_pct
                            )
                            proceeds = cp * sell_qty
                            st.session_state.paper_cash += proceeds

                            st.session_state.paper_trade_history.append({
                                "Date": str(datetime.date.today()),
                                "Stock": sell_symbol.replace(".NS",""),
                                "Qty": sell_qty,
                                "Buy ₹": round(holding["avg_price"], 2),
                                "Sell ₹": cp,
                                "Gross P&L": charges["gross_pnl"],
                                "Charges": charges["total_charges"],
                                "Net P&L": charges["net_pnl"],
                                "Net %": charges["net_pnl_pct"]
                            })

                            remaining = holding["qty"] - sell_qty
                            if remaining <= 0:
                                del st.session_state.paper_portfolio[sell_symbol]
                            else:
                                st.session_state.paper_portfolio[sell_symbol]["qty"] = remaining

                            save_data()

                            if charges["net_pnl"] >= 0:
                                st.success(f"🟢 SOLD {sell_qty}x {sell_symbol} @ ₹{cp}")
                            else:
                                st.error(f"🔴 SOLD {sell_qty}x {sell_symbol} @ ₹{cp}")

                            r1, r2, r3 = st.columns(3)
                            r1.metric("Gross P&L", f"₹{charges['gross_pnl']}")
                            r2.metric("Total Charges", f"₹{charges['total_charges']}")
                            r3.metric("Net P&L", f"₹{charges['net_pnl']}",
                                     f"{charges['net_pnl_pct']}%")

                            with st.expander("📋 Charge Breakdown"):
                                st.write(f"🏦 Brokerage: ₹0 (Upstox Free)")
                                st.write(f"📊 STT: ₹{charges['stt']}")
                                st.write(f"🏛️ Exchange: ₹{charges['exchange_charges']}")
                                st.write(f"📋 SEBI: ₹{charges['sebi_charges']}")
                                st.write(f"🧾 GST: ₹{charges['gst']}")
                                st.write(f"📮 Stamp Duty: ₹{charges['stamp_duty']}")
                                st.write(f"⚡ Slippage ({slip_pct}%): ₹{charges['slippage']}")
                                st.write(f"**💰 Total: ₹{charges['total_charges']}**")
                        else:
                            st.error("Data મળ્યો નથી")
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.info("કોઈ Holdings નથી.")

        st.divider()
        st.markdown("#### ♻️ Reset Account")
        if st.button("🔄 Reset Paper Trading", key="reset_btn"):
            st.session_state.paper_cash = 100000.0
            st.session_state.paper_portfolio = {}
            st.session_state.paper_trade_history = []
            save_data()
            st.success("✅ Reset! Cash: ₹1,00,000")

    with trade_tab2:
        st.markdown("#### 📡 Live Portfolio Tracker")
        if st.session_state.paper_portfolio:
            if st.button("🔄 Refresh Prices", key="refresh_btn"):
                rows = []
                total_inv = 0
                total_cur = 0
                with st.spinner("Live prices..."):
                    for sym, pos in st.session_state.paper_portfolio.items():
                        try:
                            td = fetch_technical_data(sym)
                            cp = td["current_price"] if td else pos["avg_price"]
                        except:
                            cp = pos["avg_price"]
                        inv = pos["qty"] * pos["avg_price"]
                        cur = pos["qty"] * cp
                        pnl = cur - inv
                        pnl_pct = round((pnl/inv)*100, 2) if inv > 0 else 0
                        charges = calculate_charges(pos["avg_price"], cp, pos["qty"])
                        total_inv += inv
                        total_cur += cur
                        rows.append({
                            "Stock": sym.replace(".NS",""),
                            "Qty": pos["qty"],
                            "Avg ₹": round(pos["avg_price"],2),
                            "Current ₹": cp,
                            "Invested": f"₹{round(inv,2):,}",
                            "Value": f"₹{round(cur,2):,}",
                            "Gross P&L": f"₹{round(pnl,2)}",
                            "Charges": f"₹{charges['total_charges']}",
                            "Net P&L": f"₹{charges['net_pnl']}",
                            "Net %": f"{charges['net_pnl_pct']}%"
                        })

                st.dataframe(rows, use_container_width=True)
                total_pnl = total_cur - total_inv
                t1, t2, t3 = st.columns(3)
                t1.metric("Invested", f"₹{total_inv:,.2f}")
                t2.metric("Current", f"₹{total_cur:,.2f}")
                t3.metric("Total P&L", f"₹{round(total_pnl,2):,.2f}")
        else:
            st.info("Portfolio Empty")

    with trade_tab3:
        st.markdown("#### 📒 Trade History (Net of Charges)")
        if st.session_state.paper_trade_history:
            hist_df = pd.DataFrame(st.session_state.paper_trade_history)
            st.dataframe(hist_df, use_container_width=True)

            if "Net P&L" in hist_df.columns:
                total_net = hist_df["Net P&L"].sum()
                total_charges = hist_df["Charges"].sum() if "Charges" in hist_df.columns else 0
                wins = len(hist_df[hist_df["Net P&L"] > 0])
                losses = len(hist_df[hist_df["Net P&L"] <= 0])
                wr = round((wins/len(hist_df))*100, 2) if len(hist_df) > 0 else 0

                h1, h2, h3, h4 = st.columns(4)
                h1.metric("Net P&L", f"₹{round(total_net,2)}")
                h2.metric("Charges Paid", f"₹{round(total_charges,2)}")
                h3.metric("Win Rate", f"{wr}%")
                h4.metric("Trades", len(hist_df))
        else:
            st.info("હજુ Closed Trades નથી.")

    with trade_tab4:
        st.markdown("#### 🧮 Brokerage Calculator (Upstox + Slippage)")
        st.caption("Trade confirm કરતા પહેલા exact cost check કરો")

        c1, c2 = st.columns(2)
        with c1:
            calc_buy = st.number_input("Buy Price (₹)", min_value=0.01, value=1000.0, key="calc_buy")
            calc_qty = st.number_input("Quantity", min_value=1, value=10, key="calc_qty")
        with c2:
            calc_sell = st.number_input("Sell Price (₹)", min_value=0.01, value=1050.0, key="calc_sell")
            calc_slip = st.slider("Slippage %", 0.0, 0.1, 0.02, 0.01, key="calc_slip")
            st.caption(f"Slippage: {calc_slip}%")

        if st.button("🧮 Calculate", key="calc_btn"):
            ch = calculate_charges(calc_buy, calc_sell, calc_qty, calc_slip)

            st.markdown("---")
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("**📊 Trade Summary**")
                st.write(f"Buy Value: ₹{ch['buy_value']:,}")
                st.write(f"Sell Value: ₹{ch['sell_value']:,}")
                st.write(f"Gross P&L: ₹{ch['gross_pnl']}")

            with r2:
                st.markdown("**💸 Charges Breakdown**")
                st.write(f"Brokerage: ₹0 (Free)")
                st.write(f"STT: ₹{ch['stt']}")
                st.write(f"Exchange: ₹{ch['exchange_charges']}")
                st.write(f"SEBI: ₹{ch['sebi_charges']}")
                st.write(f"GST: ₹{ch['gst']}")
                st.write(f"Stamp Duty: ₹{ch['stamp_duty']}")
                st.write(f"Slippage: ₹{ch['slippage']}")
                st.write(f"**Total Charges: ₹{ch['total_charges']}**")

            st.divider()
            if ch["net_pnl"] >= 0:
                st.success(f"🟢 Net P&L: ₹{ch['net_pnl']} ({ch['net_pnl_pct']}%)")
            else:
                st.error(f"🔴 Net P&L: ₹{ch['net_pnl']} ({ch['net_pnl_pct']}%)")

            breakeven = round(calc_buy + (ch["total_charges"] / calc_qty), 2)
            st.info(f"📌 Breakeven Price: ₹{breakeven} (આ price પર જ Zero P&L)")
            # ==========================================
# TAB 3: SCANNERS
# ==========================================
with tab3:
    st.subheader("🔍 Market Scanners")

    scan_tab1, scan_tab2, scan_tab3, scan_tab4 = st.tabs([
        "🚀 Auto Scanner", "🔄 Sector", "💪 Rel. Strength", "🐋 Smart Money"
    ])

    with scan_tab1:
        st.markdown("#### 🚀 Auto Watchlist Scanner")
        st.caption("Top Breakout, Swing અને Momentum Stocks")

        tf_option = st.radio(
            "Timeframe",
            ["Daily (Swing)", "Weekly (Positional)"],
            horizontal=True,
            key="scan_tf"
        )
        period_map = {"Daily (Swing)": "6mo", "Weekly (Positional)": "1y"}
        scan_period = period_map[tf_option]

        if st.button("🚀 Run Scanner", key="auto_scan"):
            breakout_results = []
            swing_results = []
            momentum_results = []

            with st.spinner(f"{len(STOCK_UNIVERSE)} Stocks Scan ({tf_option})..."):
                for symbol in STOCK_UNIVERSE:
                    try:
                        td = fetch_technical_data(symbol, period=scan_period)
                        if not td:
                            continue
                        hist = td["hist"]
                        close = hist["Close"]
                        volume = hist["Volume"]
                        cp = td["current_price"]
                        ma50 = td["ma50"]
                        ma200 = td["ma200"]
                        rsi = td["rsi"]
                        trend = td["trend"]
                        avg_vol = volume.rolling(20).mean().iloc[-1]
                        cur_vol = volume.iloc[-1]
                        recent_high = close.iloc[-21:-1].max()

                        # Breakout
                        if cp > recent_high and cur_vol > avg_vol:
                            breakout_results.append({
                                "Stock": symbol.replace(".NS",""),
                                "Price": cp,
                                "Breakout %": round(((cp-recent_high)/recent_high)*100, 2),
                                "Vol Ratio": round(cur_vol/avg_vol, 2) if avg_vol > 0 else 0
                            })

                        # Swing
                        if trend == "Bullish" and 45 <= rsi <= 65 and cp > ma50:
                            swing_results.append({
                                "Stock": symbol.replace(".NS",""),
                                "Entry": cp,
                                "Target (5%)": round(cp*1.05, 2),
                                "SL (3%)": round(cp*0.97, 2),
                                "RSI": rsi,
                                "R:R": round((cp*1.05-cp)/(cp-cp*0.97), 2)
                            })

                        # Momentum
                        if cp > ma50 and cp > ma200 and rsi > 60 and cur_vol > avg_vol:
                            momentum_results.append({
                                "Stock": symbol.replace(".NS",""),
                                "Price": cp,
                                "RSI": rsi,
                                "MA50": ma50,
                                "Score": round(rsi + (cur_vol/avg_vol if avg_vol > 0 else 1)*10, 2)
                            })
                    except:
                        pass

            breakout_results.sort(key=lambda x: x["Breakout %"], reverse=True)
            swing_results.sort(key=lambda x: x["RSI"], reverse=True)
            momentum_results.sort(key=lambda x: x["Score"], reverse=True)

            st.markdown("### 🚀 Top 5 Breakouts")
            if breakout_results[:5]:
                st.dataframe(pd.DataFrame(breakout_results[:5]), use_container_width=True)
            else:
                st.info("કોઈ Breakout નથી.")

            st.markdown("### 📈 Top 5 Swing Trades")
            if swing_results[:5]:
                st.dataframe(pd.DataFrame(swing_results[:5]), use_container_width=True)
            else:
                st.info("કોઈ Swing Setup નથી.")

            st.markdown("### 🔥 Top 5 Momentum")
            if momentum_results[:5]:
                st.dataframe(pd.DataFrame(momentum_results[:5]), use_container_width=True)
            else:
                st.info("કોઈ Momentum Setup નથી.")

            st.success(f"✅ Scan Complete | {len(STOCK_UNIVERSE)} Stocks | {tf_option}")
            st.caption("⚠️ Technical Scan - Financial Advice નથી.")

    with scan_tab2:
        st.markdown("#### 🔄 Sector Rotation AI")
        st.caption("કયો Sector Strong/Weak છે")

        sector_tf = st.radio(
            "Timeframe",
            ["Daily", "Weekly"],
            horizontal=True,
            key="sector_tf"
        )
        sector_period = "6mo" if sector_tf == "Daily" else "1y"

        if st.button("🔄 Scan Sectors", key="sector_scan"):
            sector_results = []
            with st.spinner("Sectors Scan..."):
                for sector, stocks in SECTOR_MAP.items():
                    bullish = 0
                    total = 0
                    rsi_sum = 0
                    for sym in stocks:
                        try:
                            td = fetch_technical_data(sym, period=sector_period)
                            if td:
                                total += 1
                                rsi_sum += td["rsi"]
                                if td["trend"] == "Bullish":
                                    bullish += 1
                        except:
                            pass
                    if total > 0:
                        pct = round((bullish/total)*100, 1)
                        avg_rsi = round(rsi_sum/total, 1)
                        sector_results.append({
                            "Sector": sector,
                            "Status": "🟢 Strong" if pct >= 65 else "🟡 Neutral" if pct >= 35 else "🔴 Weak",
                            "Bullish": f"{bullish}/{total}",
                            "Bullish %": pct,
                            "Avg RSI": avg_rsi
                        })

            sector_results.sort(key=lambda x: x["Bullish %"], reverse=True)
            st.dataframe(pd.DataFrame(sector_results), use_container_width=True)

            if sector_results:
                top = sector_results[0]
                st.success(f"🏆 Strongest: {top['Sector']} ({top['Status']}) | {top['Bullish %']}% Bullish")

                # Best stock from top sector
                top_stocks = SECTOR_MAP[top["Sector"]]
                best_stock = None
                best_score = -999
                for sym in top_stocks:
                    try:
                        td = fetch_technical_data(sym, period=sector_period)
                        if td and td["trend"] == "Bullish":
                            score = td["rsi"] + (10 if td["current_price"] > td["ma50"] else 0)
                            if score > best_score:
                                best_score = score
                                best_stock = sym
                    except:
                        pass
                if best_stock:
                    st.info(f"🎯 Top Pick from {top['Sector']}: **{best_stock.replace('.NS','')}**")

    with scan_tab3:
        st.markdown("#### 💪 Relative Strength vs Nifty")
        st.caption("Nifty કરતાં વધુ strong stocks")

        rs_period = st.radio(
            "Compare Period",
            ["1 Month", "3 Months", "6 Months"],
            horizontal=True,
            key="rs_period"
        )
        rs_period_map = {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo"}
        rs_p = rs_period_map[rs_period]

        if st.button("💪 Run RS Scan", key="rs_scan"):
            with st.spinner("Nifty vs Stocks..."):
                nifty_hist = yf.Ticker("^NSEI").history(period=rs_p)
                if not nifty_hist.empty:
                    nifty_ret = round(((nifty_hist["Close"].iloc[-1] - nifty_hist["Close"].iloc[0]) / nifty_hist["Close"].iloc[0]) * 100, 2)
                    rs_results = []
                    for sym in STOCK_UNIVERSE:
                        try:
                            h = yf.Ticker(sym).history(period=rs_p)
                            if not h.empty and len(h) >= 2:
                                ret = round(((h["Close"].iloc[-1] - h["Close"].iloc[0]) / h["Close"].iloc[0]) * 100, 2)
                                rs_results.append({
                                    "Stock": sym.replace(".NS",""),
                                    "Return %": ret,
                                    "Nifty %": nifty_ret,
                                    "RS Score": round(ret - nifty_ret, 2)
                                })
                        except:
                            pass

                    rs_results.sort(key=lambda x: x["RS Score"], reverse=True)
                    out = [r for r in rs_results if r["RS Score"] > 0]
                    under = [r for r in rs_results if r["RS Score"] <= 0]

                    st.metric(f"Nifty {rs_period} Return", f"{nifty_ret}%")

                    st.markdown("### 🏆 Outperformers")
                    if out:
                        st.dataframe(pd.DataFrame(out), use_container_width=True)
                    else:
                        st.info("કોઈ Outperformer નથી.")

                    with st.expander(f"📉 Underperformers ({len(under)})"):
                        if under:
                            st.dataframe(pd.DataFrame(under), use_container_width=True)

                    # Best opportunity
                    for r in out[:5]:
                        sym_full = r["Stock"] + ".NS"
                        td = fetch_technical_data(sym_full)
                        if td and td["trend"] == "Bullish":
                            st.success(f"🎯 Best: **{r['Stock']}** | RS: {r['RS Score']} | RSI: {td['rsi']} | 🟢 Bullish")
                            break

    with scan_tab4:
        st.markdown("#### 🐋 Smart Money Tracker")
        st.caption("Volume Spikes - Smart Money ક્યાં Active છે")

        if st.button("🐋 Run Smart Money Scan", key="sm_scan"):
            smart_results = []
            with st.spinner("Volume Spikes Scan..."):
                for sym in STOCK_UNIVERSE:
                    try:
                        h = yf.Ticker(sym).history(period="3mo")
                        if h.empty or len(h) < 21:
                            continue
                        close = h["Close"]
                        volume = h["Volume"]
                        cp = round(close.iloc[-1], 2)
                        cv = volume.iloc[-1]
                        avg_v = volume.iloc[-21:-1].mean()
                        if avg_v == 0:
                            continue
                        vr = round(cv/avg_v, 2)
                        chg = round(((close.iloc[-1]-close.iloc[-2])/close.iloc[-2])*100, 2)
                        rh = close.iloc[-21:-1].max()
                        rl = close.iloc[-21:-1].min()

                        signal = None
                        if cp > rh and vr >= 1.5:
                            signal = "🚀 Breakout + Volume"
                        elif cp < rl and vr >= 1.5:
                            signal = "🔻 Breakdown + Volume"
                        elif vr >= 2.0 and chg > 0:
                            signal = "📈 Accumulation"
                        elif vr >= 2.0 and chg < 0:
                            signal = "📉 Distribution"
                        elif vr >= 1.5:
                            signal = "⚡ Unusual Volume"

                        if signal:
                            smart_results.append({
                                "Stock": sym.replace(".NS",""),
                                "Price": cp,
                                "Change %": chg,
                                "Vol Ratio": vr,
                                "Signal": signal
                            })
                    except:
                        pass

            smart_results.sort(key=lambda x: x["Vol Ratio"], reverse=True)

            if smart_results:
                st.dataframe(pd.DataFrame(smart_results), use_container_width=True)
                best = [r for r in smart_results if "Breakout" in r["Signal"] or "Accumulation" in r["Signal"]]
                if best:
                    st.success(f"🏆 Best: **{best[0]['Stock']}** | {best[0]['Signal']} | Vol: {best[0]['Vol Ratio']}x")
            else:
                st.info("કોઈ Unusual Activity નથી.")
            st.caption("⚠️ Technical Scan - Financial Advice નથી.")
            # ==========================================
# TAB 4: AI TOOLS
# ==========================================
with tab4:
    st.subheader("🤖 AI Tools")

    ai_tab1, ai_tab2, ai_tab3, ai_tab4 = st.tabs([
        "🔍 Analysis", "🧑‍🏫 AI Coach", "📋 Portfolio Review", "⚖️ Rebalancer"
    ])

    with ai_tab1:
        st.markdown("#### 🔍 AI Stock Analysis")
        symbol = st.text_input("Stock Symbol", value="RELIANCE.NS", key="analysis_symbol")

        if st.button("🔍 Analyze", key="analyze_btn"):
            if symbol:
                try:
                    with st.spinner("Analyzing..."):
                        td = fetch_technical_data(symbol)
                        info = yf.Ticker(symbol).info

                    if td:
                        cp = info.get("currentPrice", td["current_price"])
                        mc = info.get("marketCap", "N/A")
                        pe = info.get("trailingPE", "N/A")

                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Price", f"₹{cp}")
                        c2.metric("RSI", td["rsi"])
                        c3.metric("Trend", "🟢" if td["trend"]=="Bullish" else "🔴")
                        c4.metric("PE Ratio", pe)

                        c5, c6 = st.columns(2)
                        c5.metric("50 DMA", f"₹{td['ma50']}")
                        c6.metric("200 DMA", f"₹{td['ma200']}")

                        prompt = f"""Professional Stock Analyst છો.
Stock: {symbol}
Price: ₹{cp}, PE: {pe}, Market Cap: {mc}
MA50: {td['ma50']}, MA200: {td['ma200']}, RSI: {td['rsi']}, Trend: {td['trend']}

ગુજરાતીમાં analysis આપો:
1. Company Analysis
2. મુખ્ય તકો
3. મુખ્ય જોખમો
4. Score /100
5. BUY / HOLD / AVOID
6. RSI Interpretation
7. Technical Score /100

છેલ્લે: 'આ નાણાકીય સલાહ નથી.'"""

                        with st.spinner("AI Analysis..."):
                            resp = model.generate_content(prompt)
                        st.markdown(resp.text)
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.markdown("#### 📈 AI Swing Trade Finder")
        swing_tf = st.radio("Period", ["3 Months", "6 Months"], horizontal=True, key="swing_tf")
        swing_p = "3mo" if swing_tf == "3 Months" else "6mo"

        if st.button("🚀 Find Swing Trades", key="swing_btn"):
            swing_list = []
            with st.spinner("Scanning..."):
                for sym in STOCK_UNIVERSE:
                    try:
                        td = fetch_technical_data(sym, period=swing_p)
                        if td and td["trend"] == "Bullish" and 45 <= td["rsi"] <= 65:
                            cp = td["current_price"]
                            target = round(cp * 1.05, 2)
                            sl = round(cp * 0.97, 2)
                            charges_est = calculate_charges(cp, target, 1)
                            swing_list.append({
                                "Stock": sym.replace(".NS",""),
                                "Entry": cp,
                                "Target": target,
                                "SL": sl,
                                "RSI": td["rsi"],
                                "R:R": round((target-cp)/(cp-sl), 2),
                                "Est.Net P&L(1qty)": f"₹{charges_est['net_pnl']}"
                            })
                    except:
                        pass
            swing_list.sort(key=lambda x: x["RSI"], reverse=True)
            if swing_list[:8]:
                st.dataframe(pd.DataFrame(swing_list[:8]), use_container_width=True)
                st.caption("Est. Net P&L = Upstox charges + Slippage after deduction")
            else:
                st.info("કોઈ Swing Setup નથી.")

        st.divider()
        st.markdown("#### ⭐ AI Watchlist")
        watchlist = st.text_area(
            "Stocks (Comma Separated)",
            "RELIANCE.NS,TCS.NS,HDFCBANK.NS",
            key="watchlist_input"
        )
        if st.button("📋 Analyze Watchlist", key="watchlist_btn"):
            for sym in watchlist.split(","):
                sym = sym.strip().upper()
                try:
                    td = fetch_technical_data(sym)
                    if td:
                        trend = "🟢 Bullish" if td["trend"] == "Bullish" else "🔴 Bearish"
                        score = 50
                        if td["trend"] == "Bullish": score += 20
                        if 45 <= td["rsi"] <= 65: score += 20
                        if td["current_price"] > td["ma50"]: score += 10
                        rating = "🔥 Strong" if score >= 85 else "✅ Buy" if score >= 75 else "🟡 Hold" if score >= 60 else "🔴 Avoid"
                        w1, w2, w3, w4, w5 = st.columns(5)
                        w1.write(f"**{sym.replace('.NS','')}**")
                        w2.write(f"₹{td['current_price']}")
                        w3.write(trend)
                        w4.write(f"RSI: {td['rsi']}")
                        w5.write(rating)
                    else:
                        st.warning(f"{sym} - Data નથી")
                except:
                    st.warning(f"{sym} - Error")

        st.divider()
        st.markdown("#### 🤖 AI Trade Advisor")
        trade_sym = st.text_input("Symbol", value="RELIANCE.NS", key="advisor_sym")

        if st.button("🚀 Get Trade Setup", key="advisor_btn"):
            try:
                td = fetch_technical_data(trade_sym)
                if td:
                    cp = td["current_price"]
                    score = 50
                    if td["ma50"] > td["ma200"]: score += 20
                    if td["rsi"] > 55: score += 15
                    elif td["rsi"] < 30: score += 10
                    if cp > td["ma50"]: score += 15

                    advice = "🔥 BUY" if score >= 80 else "🟡 HOLD" if score >= 65 else "🔴 AVOID"
                    target = round(cp * 1.08, 2)
                    sl = round(cp * 0.95, 2)
                    charges_est = calculate_charges(cp, target, 1)

                    a1, a2, a3, a4 = st.columns(4)
                    a1.metric("Score", f"{score}/100")
                    a2.metric("Entry", f"₹{cp}")
                    a3.metric("Target", f"₹{target}")
                    a4.metric("SL", f"₹{sl}")

                    st.success(f"Recommendation: {advice}")
                    st.caption(f"Est. Net P&L if Target hit (1 qty): ₹{charges_est['net_pnl']}")

                    if st.button("💾 Save to Journal", key="save_j"):
                        if "trade_journal" not in st.session_state:
                            st.session_state.trade_journal = []
                        st.session_state.trade_journal.append({
                            "Date": str(datetime.date.today()),
                            "Stock": trade_sym,
                            "Score": score,
                            "Advice": advice,
                            "Entry": cp,
                            "Target": target,
                            "SL": sl
                        })
                        save_data()
                        st.success("✅ Saved!")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        st.markdown("#### 📒 Trade Journal")
        if "trade_journal" not in st.session_state:
            st.session_state.trade_journal = []
        if st.session_state.trade_journal:
            st.dataframe(
                pd.DataFrame(st.session_state.trade_journal),
                use_container_width=True
            )

    with ai_tab2:
        st.markdown("#### 🧑‍🏫 Gemini AI Trade Coach")
        st.caption("'Should I buy Reliance?' 'TCS entry ક્યારે?'")

        coach_q = st.text_input(
            "Question",
            value="Should I buy Reliance?",
            key="coach_q"
        )

        if st.button("🤖 Ask AI Coach", key="coach_btn"):
            if coach_q.strip():
                try:
                    NAMES = {
                        "reliance": "RELIANCE.NS", "tcs": "TCS.NS",
                        "infosys": "INFY.NS", "infy": "INFY.NS",
                        "hdfc": "HDFCBANK.NS", "hdfcbank": "HDFCBANK.NS",
                        "icici": "ICICIBANK.NS", "sbi": "SBIN.NS",
                        "itc": "ITC.NS", "wipro": "WIPRO.NS",
                        "titan": "TITAN.NS", "sunpharma": "SUNPHARMA.NS",
                        "maruti": "MARUTI.NS", "lt": "LT.NS",
                        "airtel": "BHARTIARTL.NS", "bharti": "BHARTIARTL.NS",
                        "kotak": "KOTAKBANK.NS", "axis": "AXISBANK.NS",
                        "ntpc": "NTPC.NS", "ongc": "ONGC.NS",
                        "tatamotors": "TATAMOTORS.NS", "mahindra": "M&M.NS",
                        "bajaj": "BAJFINANCE.NS", "hcl": "HCLTECH.NS",
                        "techm": "TECHM.NS", "adani": "ADANIPORTS.NS",
                        "tatasteel": "TATASTEEL.NS", "jsw": "JSWSTEEL.NS"
                    }

                    detected = None
                    for name, sym in NAMES.items():
                        if name in coach_q.lower():
                            detected = sym
                            break

                    context = ""
                    if detected:
                        td = fetch_technical_data(detected)
                        if td:
                            cp = td["current_price"]
                            target = round(cp * 1.08, 2)
                            sl = round(cp * 0.95, 2)
                            charges_est = calculate_charges(cp, target, 1)

                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Price", f"₹{cp}")
                            c2.metric("RSI", td["rsi"])
                            c3.metric("Trend", "🟢" if td["trend"]=="Bullish" else "🔴")
                            c4.metric("Est.Net P&L", f"₹{charges_est['net_pnl']}")

                            context = f"""
Detected: {detected}
Price: ₹{cp}, RSI: {td['rsi']}, Trend: {td['trend']}
MA50: {td['ma50']}, MA200: {td['ma200']}
Suggested Target: ₹{target}, SL: ₹{sl}
Est. Net P&L (charges+slippage after): ₹{charges_est['net_pnl']}
"""

                    prompt = f"""Professional Trading Coach છો.
Question: "{coach_q}"
{context if context else "General trading question"}

ગુજરાતીમાં answer આપો:
1. Recommendation: BUY/WAIT/AVOID
2. Entry: ₹
3. Target: ₹
4. Stop Loss: ₹
5. Risk: Low/Medium/High
6. Probability: %
7. Reasoning (2-3 lines)

છેલ્લે: 'આ નાણાકીય સલાહ નથી.'"""

                    with st.spinner("AI Coach thinking..."):
                        resp = model.generate_content(prompt)
                    st.markdown(resp.text)
                except Exception as e:
                    st.error(f"Error: {e}")

    with ai_tab3:
        st.markdown("#### 📋 AI Portfolio Review")

        if st.button("🤖 Review My Portfolio", key="review_btn"):
            if not st.session_state.paper_portfolio:
                st.info("Portfolio Empty - Stocks Buy કરો.")
            else:
                with st.spinner("Portfolio Analyzing..."):
                    rows = []
                    total_inv = 0
                    total_cur = 0
                    sector_exp = {}

                    for sym, pos in st.session_state.paper_portfolio.items():
                        try:
                            td = fetch_technical_data(sym)
                            cp = td["current_price"] if td else pos["avg_price"]
                            rsi = td["rsi"] if td else "N/A"
                            trend = td["trend"] if td else "N/A"
                        except:
                            cp = pos["avg_price"]
                            rsi = trend = "N/A"

                        inv = pos["qty"] * pos["avg_price"]
                        cur = pos["qty"] * cp
                        pnl = cur - inv
                        pnl_pct = round((pnl/inv)*100, 2) if inv > 0 else 0
                        charges = calculate_charges(pos["avg_price"], cp, pos["qty"])
                        total_inv += inv
                        total_cur += cur

                        sec = "Other"
                        for s, stocks in SECTOR_MAP.items():
                            if sym in stocks:
                                sec = s
                                break
                        sector_exp[sec] = sector_exp.get(sec, 0) + cur

                        rows.append({
                            "Stock": sym.replace(".NS",""),
                            "Qty": pos["qty"],
                            "Avg ₹": round(pos["avg_price"], 2),
                            "Current ₹": cp,
                            "Gross P&L": f"₹{round(pnl,2)}",
                            "Net P&L": f"₹{charges['net_pnl']}",
                            "Net %": f"{charges['net_pnl_pct']}%",
                            "RSI": rsi,
                            "Trend": trend,
                            "Sector": sec
                        })

                    port_df = pd.DataFrame(rows)
                    st.dataframe(port_df, use_container_width=True)

                    total_pnl = round(total_cur - total_inv, 2)
                    p1, p2, p3 = st.columns(3)
                    p1.metric("Invested", f"₹{total_inv:,.2f}")
                    p2.metric("Current", f"₹{total_cur:,.2f}")
                    p3.metric("P&L", f"₹{total_pnl:,.2f}")

                    st.markdown("#### 🏭 Sector Exposure")
                    sec_df = pd.DataFrame([
                        {
                            "Sector": s,
                            "Value": round(v, 2),
                            "Allocation %": round((v/total_cur)*100, 1) if total_cur > 0 else 0
                        }
                        for s, v in sector_exp.items()
                    ]).sort_values("Allocation %", ascending=False)
                    st.dataframe(sec_df, use_container_width=True)

                    prompt = f"""Portfolio Manager છો.
Invested: ₹{total_inv:.2f}
Current: ₹{total_cur:.2f}
P&L: ₹{total_pnl:.2f}
Holdings: {port_df[['Stock','Net P&L','Net %','RSI','Trend','Sector']].to_string(index=False)}
Sector Exposure: {sec_df.to_string(index=False)}

ગુજરાતીમાં:
1. Portfolio Health Score /100
2. Diversification
3. Risk Concentration
4. Underperforming Stocks
5. Strong Holdings
6. Action Suggestions (Hold/Trim/Add)

છેલ્લે: 'આ નાણાકીય સલાહ નથી.'"""

                    with st.spinner("AI Review..."):
                        resp = model.generate_content(prompt)
                    st.markdown(resp.text)

    with ai_tab4:
        st.markdown("#### ⚖️ AI Portfolio Rebalancer")

        if st.button("⚖️ Get Suggestions", key="rebal_btn"):
            if not st.session_state.paper_portfolio:
                st.info("Portfolio Empty")
            else:
                with st.spinner("Analyzing..."):
                    rows = []
                    total_cur = 0

                    for sym, pos in st.session_state.paper_portfolio.items():
                        try:
                            td = fetch_technical_data(sym)
                            cp = td["current_price"] if td else pos["avg_price"]
                            rsi = td["rsi"] if td else 50
                            trend = td["trend"] if td else "N/A"
                            ma50 = td["ma50"] if td else cp
                            ma200 = td["ma200"] if td else cp
                        except:
                            cp = pos["avg_price"]
                            rsi, trend, ma50, ma200 = 50, "N/A", cp, cp

                        cur = pos["qty"] * cp
                        pnl_pct = round(((cp - pos["avg_price"]) / pos["avg_price"]) * 100, 2)
                        total_cur += cur

                        score = 50
                        if trend == "Bullish": score += 20
                        else: score -= 10
                        if 40 <= rsi <= 65: score += 15
                        elif rsi > 75: score -= 15
                        elif rsi < 25: score += 5
                        if cp > ma50: score += 10
                        if cp > ma200: score += 5
                        score = max(0, min(100, score))

                        action = "🟢 HOLD/ADD" if score >= 70 else "🟡 HOLD" if score >= 45 else "🔴 TRIM/EXIT"
                        rows.append({
                            "Stock": sym.replace(".NS",""),
                            "Current ₹": cp,
                            "P&L %": pnl_pct,
                            "Score": score,
                            "Action": action
                        })

                    hold_df = pd.DataFrame(rows)
                    if total_cur > 0:
                        values = [
                            st.session_state.paper_portfolio[sym]["qty"] * st.session_state.paper_portfolio[sym]["avg_price"]
                            for sym in st.session_state.paper_portfolio.keys()
                        ]
                        hold_df["Alloc %"] = [round((v/total_cur)*100, 1) for v in values]

                    hold_df = hold_df.sort_values("Score", ascending=False)
                    st.dataframe(hold_df, use_container_width=True)

                    weak = hold_df[hold_df["Score"] < 45]["Stock"].tolist()
                    strong = hold_df[hold_df["Score"] >= 70]["Stock"].tolist()

                    r1, r2 = st.columns(2)
                    with r1:
                        st.markdown("**🔴 Exit Candidates:**")
                        for s in weak:
                            st.write(f"• {s}")
                        if not weak:
                            st.success("None - All holdings healthy ✅")
                    with r2:
                        st.markdown("**🟢 Strong Holdings:**")
                        for s in strong:
                            st.write(f"• {s}")

                    # New ideas
                    new_ideas = []
                    existing = set(st.session_state.paper_portfolio.keys())
                    for sym in STOCK_UNIVERSE:
                        if sym in existing:
                            continue
                        try:
                            td = fetch_technical_data(sym)
                            if td and td["trend"] == "Bullish" and 45 <= td["rsi"] <= 65:
                                new_ideas.append(sym.replace(".NS",""))
                        except:
                            pass
                        if len(new_ideas) >= 3:
                            break

                    st.markdown("**💡 New Ideas:**")
                    if new_ideas:
                        st.write(", ".join(new_ideas))
                    else:
                        st.write("હાલ કોઈ new bullish setup નથી.")

                    prompt = f"""Portfolio Manager છો.
Holdings Analysis:
{hold_df.to_string(index=False)}
Exit Candidates: {', '.join(weak) if weak else 'None'}
Strong: {', '.join(strong) if strong else 'None'}
New Ideas: {', '.join(new_ideas) if new_ideas else 'None'}

ગુજરાતીમાં (6-8 lines):
1. Rebalancing Strategy
2. Specific shifts (sell X, buy Y)
3. Concentration risk
4. Priority order

છેલ્લે: 'આ નાણાકીય સલાહ નથી.'"""

                    with st.spinner("AI Strategy..."):
                        resp = model.generate_content(prompt)
                    st.markdown(resp.text)
# ==========================================
# TAB 5: ANALYTICS
# ==========================================
with tab5:
    st.subheader("📊 Analytics & Performance")

    an_tab1, an_tab2, an_tab3, an_tab4 = st.tabs([
        "📈 Charts", "📊 Portfolio Stats", "🧪 Backtesting", "🛡️ Risk & Bot"
    ])

    with an_tab1:
        st.markdown("#### 📈 Professional Chart")

        chart_symbol = st.text_input("Symbol", value="RELIANCE.NS", key="chart_sym")
        chart_period = st.radio(
            "Period",
            ["3 Months", "6 Months", "1 Year"],
            horizontal=True,
            key="chart_period"
        )
        chart_period_map = {"3 Months": "3mo", "6 Months": "6mo", "1 Year": "1y"}
        c_period = chart_period_map[chart_period]

        if st.button("📈 Generate Chart", key="chart_btn"):
            try:
                with st.spinner("Loading chart..."):
                    hist = yf.Ticker(chart_symbol).history(period=c_period)

                if not hist.empty:
                    close = hist["Close"]
                    high = hist["High"]
                    low = hist["Low"]
                    open_ = hist["Open"]
                    volume = hist["Volume"]
                    dates = hist.index

                    ma20 = close.rolling(20).mean()
                    ma50 = close.rolling(50).mean()

                    delta = close.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rsi = 100 - (100 / (1 + gain/loss))

                    # Buy/Sell signals
                    buy_sig = []
                    sell_sig = []
                    for i in range(1, len(close)):
                        if ma20.iloc[i] > ma50.iloc[i] and ma20.iloc[i-1] <= ma50.iloc[i-1]:
                            buy_sig.append(i)
                        elif ma20.iloc[i] < ma50.iloc[i] and ma20.iloc[i-1] >= ma50.iloc[i-1]:
                            sell_sig.append(i)

                    fig = make_subplots(
                        rows=3, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.04,
                        row_heights=[0.6, 0.2, 0.2],
                        subplot_titles=(
                            f"{chart_symbol} - Candlestick",
                            "Volume",
                            "RSI (14)"
                        )
                    )

                    # Candlestick
                    fig.add_trace(go.Candlestick(
                        x=dates, open=open_, high=high, low=low, close=close,
                        increasing_line_color="#00FF88",
                        decreasing_line_color="#FF1744",
                        name="Price"
                    ), row=1, col=1)

                    # MA Lines
                    fig.add_trace(go.Scatter(
                        x=dates, y=ma20,
                        line=dict(color="#00BFFF", width=1.5),
                        name="MA20"
                    ), row=1, col=1)

                    fig.add_trace(go.Scatter(
                        x=dates, y=ma50,
                        line=dict(color="#FFA000", width=1.5),
                        name="MA50"
                    ), row=1, col=1)

                    # Buy signals
                    if buy_sig:
                        fig.add_trace(go.Scatter(
                            x=[dates[i] for i in buy_sig],
                            y=[low.iloc[i] * 0.99 for i in buy_sig],
                            mode="markers",
                            marker=dict(symbol="triangle-up", size=12, color="#00FF88"),
                            name="Buy Signal"
                        ), row=1, col=1)

                    # Sell signals
                    if sell_sig:
                        fig.add_trace(go.Scatter(
                            x=[dates[i] for i in sell_sig],
                            y=[high.iloc[i] * 1.01 for i in sell_sig],
                            mode="markers",
                            marker=dict(symbol="triangle-down", size=12, color="#FF1744"),
                            name="Sell Signal"
                        ), row=1, col=1)

                    # Volume
                    vol_colors = [
                        "#00FF88" if close.iloc[i] >= open_.iloc[i] else "#FF1744"
                        for i in range(len(close))
                    ]
                    fig.add_trace(go.Bar(
                        x=dates, y=volume,
                        marker_color=vol_colors,
                        name="Volume",
                        opacity=0.7
                    ), row=2, col=1)

                    # RSI
                    fig.add_trace(go.Scatter(
                        x=dates, y=rsi,
                        line=dict(color="#9C27B0", width=1.5),
                        name="RSI"
                    ), row=3, col=1)

                    fig.add_hline(y=70, line_dash="dash", line_color="#FF1744", opacity=0.5, row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="#00FF88", opacity=0.5, row=3, col=1)
                    fig.add_hline(y=50, line_dash="dot", line_color="#8B949E", opacity=0.3, row=3, col=1)

                    fig.update_layout(
                        height=700,
                        template="plotly_dark",
                        paper_bgcolor="#0D1117",
                        plot_bgcolor="#161B22",
                        font=dict(color="#E6EDF3"),
                        xaxis_rangeslider_visible=False,
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom", y=1.02,
                            xanchor="right", x=1,
                            font=dict(color="#E6EDF3")
                        ),
                        margin=dict(l=10, r=10, t=60, b=10)
                    )
                    fig.update_yaxes(
                        gridcolor="#21262D",
                        title_font=dict(color="#8B949E")
                    )
                    fig.update_xaxes(gridcolor="#21262D")

                    st.plotly_chart(fig, use_container_width=True)

                    ch1, ch2, ch3, ch4 = st.columns(4)
                    ch1.metric("Price", f"₹{round(close.iloc[-1],2)}")
                    ch2.metric("RSI", round(rsi.iloc[-1], 2))
                    ch3.metric("MA20", f"₹{round(ma20.iloc[-1],2)}")
                    ch4.metric("Trend", "🟢 Bullish" if ma20.iloc[-1] > ma50.iloc[-1] else "🔴 Bearish")
                else:
                    st.error("Data મળ્યો નથી.")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        st.markdown("#### 📈 Portfolio Equity Curve")

        # Current value calculation
        eq_hv = 0
        for sym, pos in st.session_state.paper_portfolio.items():
            try:
                td = fetch_technical_data(sym)
                cp = td["current_price"] if td else pos["avg_price"]
            except:
                cp = pos["avg_price"]
            eq_hv += cp * pos["qty"]

        eq_total = round(st.session_state.paper_cash + eq_hv, 2)
        st.metric("Current Portfolio Value", f"₹{eq_total:,.2f}")

        if st.button("📸 Record Snapshot", key="snap_btn"):
            today_str = str(datetime.date.today())
            existing = [e["Date"] for e in st.session_state.equity_curve]
            if today_str in existing:
                for e in st.session_state.equity_curve:
                    if e["Date"] == today_str:
                        e["Value"] = eq_total
            else:
                st.session_state.equity_curve.append({
                    "Date": today_str, "Value": eq_total
                })
            save_data()
            st.success(f"✅ Snapshot: ₹{eq_total:,.2f} on {today_str}")

        if len(st.session_state.equity_curve) >= 2:
            eq_df = pd.DataFrame(st.session_state.equity_curve)
            eq_df["Date"] = pd.to_datetime(eq_df["Date"])
            eq_df = eq_df.sort_values("Date").set_index("Date")
            start_val = eq_df["Value"].iloc[0]
            eq_df["Profit"] = eq_df["Value"] - start_val
            eq_df["Peak"] = eq_df["Value"].cummax()
            eq_df["Drawdown %"] = ((eq_df["Value"] - eq_df["Peak"]) / eq_df["Peak"]) * 100

            fig2 = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.7, 0.3],
                subplot_titles=("Portfolio Value", "Drawdown %")
            )

            fig2.add_trace(go.Scatter(
                x=eq_df.index, y=eq_df["Value"],
                mode="lines+markers",
                line=dict(color="#00FF88", width=2.5),
                marker=dict(size=7, color="#00FF88"),
                fill="tozeroy",
                fillcolor="rgba(0,255,136,0.08)",
                name="Portfolio Value"
            ), row=1, col=1)

            fig2.add_hline(
                y=start_val,
                line_dash="dash",
                line_color="#8B949E",
                opacity=0.5,
                row=1, col=1
            )

            fig2.add_trace(go.Scatter(
                x=eq_df.index, y=eq_df["Drawdown %"],
                line=dict(color="#FF1744", width=1.5),
                fill="tozeroy",
                fillcolor="rgba(255,23,68,0.08)",
                name="Drawdown %"
            ), row=2, col=1)

            fig2.update_layout(
                height=500,
                template="plotly_dark",
                paper_bgcolor="#0D1117",
                plot_bgcolor="#161B22",
                font=dict(color="#E6EDF3"),
                margin=dict(l=10, r=10, t=40, b=10)
            )
            fig2.update_yaxes(gridcolor="#21262D")
            fig2.update_xaxes(gridcolor="#21262D")

            st.plotly_chart(fig2, use_container_width=True)

            growth = round(((eq_df["Value"].iloc[-1] - start_val) / start_val) * 100, 2)
            max_dd = round(eq_df["Drawdown %"].min(), 2)

            eq1, eq2, eq3 = st.columns(3)
            eq1.metric("Start", f"₹{start_val:,.2f}")
            eq2.metric("Growth", f"{growth}%")
            eq3.metric("Max Drawdown", f"{max_dd}%")

            with st.expander("📋 Snapshot History"):
                st.dataframe(
                    eq_df[["Value","Profit","Drawdown %"]].reset_index(),
                    use_container_width=True
                )

            if st.button("🗑️ Clear History", key="clear_eq"):
                st.session_state.equity_curve = []
                save_data()
                st.success("✅ Cleared")
        else:
            st.info("2+ Snapshots જોઈએ Equity Curve માટે. Daily 'Record Snapshot' click કરો.")

    with an_tab2:
        st.markdown("#### 📊 Portfolio Analytics Pro")

        if st.session_state.paper_trade_history:
            hist_df = pd.DataFrame(st.session_state.paper_trade_history)
            pnl_col = "Net P&L" if "Net P&L" in hist_df.columns else "P&L"

            total_trades = len(hist_df)
            wins = hist_df[hist_df[pnl_col] > 0]
            losses = hist_df[hist_df[pnl_col] <= 0]
            win_rate = round((len(wins)/total_trades)*100, 2) if total_trades > 0 else 0
            realized = round(hist_df[pnl_col].sum(), 2)
            total_charges = hist_df["Charges"].sum() if "Charges" in hist_df.columns else 0

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Total Trades", total_trades)
            a2.metric("Win Rate", f"{win_rate}%")
            a3.metric("Net Realized P&L", f"₹{realized}")
            a4.metric("Total Charges Paid", f"₹{round(total_charges,2)}")

            best = hist_df.loc[hist_df[pnl_col].idxmax()]
            worst = hist_df.loc[hist_df[pnl_col].idxmin()]
            b1, b2 = st.columns(2)
            b1.metric("🏆 Best Trade", best["Stock"], f"₹{best[pnl_col]}")
            b2.metric("📉 Worst Trade", worst["Stock"], f"₹{worst[pnl_col]}")

            st.write(f"✅ Winning: {len(wins)} | ❌ Losing: {len(losses)}")
            st.dataframe(hist_df, use_container_width=True)
        else:
            st.info("Closed Trades નથી. Sell કર્યા પછી stats આવશે.")

        if st.session_state.paper_portfolio:
            unreal = 0
            for sym, pos in st.session_state.paper_portfolio.items():
                try:
                    td = fetch_technical_data(sym)
                    cp = td["current_price"] if td else pos["avg_price"]
                except:
                    cp = pos["avg_price"]
                unreal += (cp - pos["avg_price"]) * pos["qty"]
            st.metric("📈 Unrealized P&L (Open Positions)", f"₹{round(unreal,2)}")

    with an_tab3:
        st.markdown("#### 🧪 Strategy Backtesting")

        bt_tab1, bt_tab2, bt_tab3 = st.tabs([
            "📊 MA Crossover", "🚀 Momentum", "📉 RSI Pullback"
        ])

        with bt_tab1:
            bt1_sym = st.text_input("Symbol", value="RELIANCE.NS", key="bt1_sym")
            if st.button("🧪 Run MA Backtest", key="bt1_btn"):
                try:
                    with st.spinner("Backtesting..."):
                        hist = yf.Ticker(bt1_sym).history(period="3y")
                        close = hist["Close"]
                        ma50 = close.rolling(50).mean()
                        ma200 = close.rolling(200).mean()
                        delta = close.diff()
                        gain = delta.where(delta > 0, 0).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rsi_s = 100 - (100/(1+(gain/loss)))
                        volume = hist["Volume"]
                        avg_vol = volume.rolling(20).mean()

                        pos, entry = False, 0
                        trades, wins, losses, profit = 0, 0, 0, 0

                        for i in range(200, len(close)):
                            if not pos:
                                if (ma50.iloc[i] > ma200.iloc[i] and
                                    45 <= rsi_s.iloc[i] <= 65 and
                                    volume.iloc[i] > avg_vol.iloc[i]):
                                    entry = close.iloc[i]
                                    pos = True
                            else:
                                pct = ((close.iloc[i]-entry)/entry)*100
                                if pct >= 8:
                                    wins+=1; trades+=1; profit+=pct; pos=False
                                elif pct <= -4:
                                    losses+=1; trades+=1; profit+=pct; pos=False

                        wr = round((wins/trades)*100,2) if trades>0 else 0
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Trades", trades)
                        b2.metric("Win Rate", f"{wr}%")
                        b3.metric("Total Return", f"{round(profit,2)}%")
                        st.write(f"✅ Wins: {wins} | ❌ Losses: {losses}")
                        if wr >= 60: st.success("🔥 Excellent Strategy")
                        elif wr >= 50: st.warning("✅ Good Strategy")
                        else: st.error("⚠️ Needs Improvement")
                except Exception as e:
                    st.error(f"Error: {e}")

        with bt_tab2:
            bt2_sym = st.text_input("Symbol", value="ITC.NS", key="bt2_sym")
            if st.button("🚀 Run Momentum Backtest", key="bt2_btn"):
                try:
                    with st.spinner("Backtesting..."):
                        hist = yf.Ticker(bt2_sym).history(period="3y")
                        close = hist["Close"]
                        volume = hist["Volume"]
                        ma50 = close.rolling(50).mean()
                        ma200 = close.rolling(200).mean()
                        avg_vol = volume.rolling(20).mean()

                        pos, entry = False, 0
                        trades, wins, losses, profit = 0, 0, 0, 0

                        for i in range(200, len(close)):
                            bh = close.iloc[i-20:i].max()
                            if not pos:
                                if (close.iloc[i] > ma50.iloc[i] and
                                    close.iloc[i] > ma200.iloc[i] and
                                    close.iloc[i] > bh and
                                    volume.iloc[i] > avg_vol.iloc[i]):
                                    entry = close.iloc[i]; pos = True
                            else:
                                pct = ((close.iloc[i]-entry)/entry)*100
                                if pct >= 10:
                                    wins+=1; trades+=1; profit+=pct; pos=False
                                elif pct <= -5:
                                    losses+=1; trades+=1; profit+=pct; pos=False

                        wr = round((wins/trades)*100,2) if trades>0 else 0
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Trades", trades)
                        b2.metric("Win Rate", f"{wr}%")
                        b3.metric("Total Return", f"{round(profit,2)}%")
                        st.write(f"✅ Wins: {wins} | ❌ Losses: {losses}")
                        if wr >= 60: st.success("🔥 Excellent")
                        elif wr >= 50: st.warning("✅ Good")
                        else: st.error("⚠️ Weak")
                except Exception as e:
                    st.error(f"Error: {e}")

        with bt_tab3:
            bt3_sym = st.text_input("Symbol", value="ITC.NS", key="bt3_sym")
            if st.button("📉 Run RSI Backtest", key="bt3_btn"):
                try:
                    with st.spinner("Backtesting..."):
                        hist = yf.Ticker(bt3_sym).history(period="3y")
                        close = hist["Close"]
                        ma50 = close.rolling(50).mean()
                        ma200 = close.rolling(200).mean()
                        delta = close.diff()
                        gain = delta.where(delta > 0, 0).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rsi = 100-(100/(1+(gain/loss)))

                        pos, entry = False, 0
                        trades, wins, losses, profit = 0, 0, 0, 0

                        for i in range(200, len(close)):
                            if not pos:
                                if ma50.iloc[i] > ma200.iloc[i] and rsi.iloc[i] < 35:
                                    entry = close.iloc[i]; pos = True
                            else:
                                pct = ((close.iloc[i]-entry)/entry)*100
                                if pct >= 8:
                                    wins+=1; trades+=1; profit+=pct; pos=False
                                elif pct <= -4:
                                    losses+=1; trades+=1; profit+=pct; pos=False

                        wr = round((wins/trades)*100,2) if trades>0 else 0
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Trades", trades)
                        b2.metric("Win Rate", f"{wr}%")
                        b3.metric("Total Return", f"{round(profit,2)}%")
                        st.write(f"✅ Wins: {wins} | ❌ Losses: {losses}")
                        if wr >= 60: st.success("🔥 Excellent")
                        elif wr >= 50: st.warning("✅ Good")
                        else: st.error("⚠️ Weak")
                except Exception as e:
                    st.error(f"Error: {e}")

    with an_tab4:
        st.markdown("#### 🛡️ Risk Manager")

        r1, r2 = st.columns(2)
        with r1:
            rm_cap = st.number_input("Capital (₹)", 1000, 10000000, 100000, 1000, key="rm_cap")
            rm_entry = st.number_input("Entry Price (₹)", 0.01, 100000.0, 1000.0, 0.5, key="rm_entry")
        with r2:
            rm_sl = st.number_input("Stop Loss (₹)", 0.01, 100000.0, 950.0, 0.5, key="rm_sl")
            rm_target = st.number_input("Target (₹)", 0.01, 100000.0, 1100.0, 0.5, key="rm_target")

        rm_risk = st.slider("Risk Per Trade (%)", 0.5, 10.0, 1.0, 0.5, key="rm_risk")
        st.caption(f"Risk: {rm_risk}%")

        if st.button("🧮 Calculate Position Size", key="rm_calc"):
            if rm_entry > rm_sl:
                rps = rm_entry - rm_sl
                rwps = rm_target - rm_entry
                rr = round(rwps/rps, 2) if rps > 0 else 0
                max_risk = rm_cap * (rm_risk/100)
                qty = int(max_risk/rps) if rps > 0 else 0
                pos_val = round(qty * rm_entry, 2)
                max_loss = round(qty * rps, 2)
                pot_profit = round(qty * rwps, 2)

                charges_sl = calculate_charges(rm_entry, rm_sl, qty)
                charges_tgt = calculate_charges(rm_entry, rm_target, qty)

                rr1, rr2, rr3 = st.columns(3)
                rr1.metric("Risk:Reward", f"1:{rr}")
                rr2.metric("Position Size", f"{qty} shares")
                rr3.metric("Position Value", f"₹{pos_val:,}")

                rr4, rr5 = st.columns(2)
                rr4.metric("Max Loss (Net)", f"₹{charges_sl['net_pnl']}")
                rr5.metric("Target Profit (Net)", f"₹{charges_tgt['net_pnl']}")

                if rr >= 2: st.success("✅ Good Setup (≥ 1:2)")
                elif rr >= 1: st.warning("🟡 Acceptable (1:1)")
                else: st.error("🔴 Poor Setup (< 1:1)")

                with st.expander("📋 Charge Preview"):
                    st.write("**If SL Hit:**")
                    st.write(f"Gross Loss: ₹{charges_sl['gross_pnl']} | Charges: ₹{charges_sl['total_charges']} | Net: ₹{charges_sl['net_pnl']}")
                    st.write("**If Target Hit:**")
                    st.write(f"Gross Profit: ₹{charges_tgt['gross_pnl']} | Charges: ₹{charges_tgt['total_charges']} | Net: ₹{charges_tgt['net_pnl']}")
            else:
                st.error("Entry > Stop Loss હોવો જોઈએ.")

        st.divider()
        st.markdown("#### 🤖 Auto Trade Bot")

        with st.expander("⚙️ Bot Settings"):
            at_max = st.number_input("Max Positions", 1, 10, 5, key="at_max")
            at_cap = st.number_input("Capital Per Trade (₹)", 1000, 50000, 10000, 1000, key="at_cap")
            at_score = st.slider("Min AI Score", 50, 100, 75, key="at_score")
            st.caption(f"Score: {at_score}")
            at_target_pct = st.slider("Target (%)", 2.0, 20.0, 4.0, 0.5, key="at_target_pct")
            st.caption(f"Target: {at_target_pct}%")
            at_sl_pct = st.slider("Stop Loss (%)", 1.0, 10.0, 2.5, 0.5, key="at_sl_pct")
            st.caption(f"SL: {at_sl_pct}%")

        if st.button("🚀 Run Auto Trade Bot", key="auto_bot"):
            if st.session_state.get("circuit_breaker_triggered", False):
                st.error("🚨 Circuit Breaker Active! Trading Blocked.")
            else:
                # Step 1: Check existing for Target/SL
                st.markdown("**Step 1: Checking Holdings...**")
                for sym, pos in list(st.session_state.paper_portfolio.items()):
                    try:
                        td = fetch_technical_data(sym)
                        if not td: continue
                        cp = td["current_price"]
                        chg = ((cp - pos["avg_price"]) / pos["avg_price"]) * 100
                        charges = calculate_charges(pos["avg_price"], cp, pos["qty"])

                        if chg >= at_target_pct:
                            st.session_state.paper_cash += cp * pos["qty"]
                            st.session_state.paper_trade_history.append({
                                "Date": str(datetime.date.today()),
                                "Stock": sym.replace(".NS",""),
                                "Qty": pos["qty"],
                                "Buy ₹": round(pos["avg_price"],2),
                                "Sell ₹": cp,
                                "Gross P&L": charges["gross_pnl"],
                                "Charges": charges["total_charges"],
                                "Net P&L": charges["net_pnl"],
                                "Net %": charges["net_pnl_pct"]
                            })
                            del st.session_state.paper_portfolio[sym]
                            st.success(f"🎯 TARGET: SOLD {sym.replace('.NS','')} @ ₹{cp} | Net P&L: ₹{charges['net_pnl']}")

                        elif chg <= -at_sl_pct:
                            st.session_state.paper_cash += cp * pos["qty"]
                            st.session_state.paper_trade_history.append({
                                "Date": str(datetime.date.today()),
                                "Stock": sym.replace(".NS",""),
                                "Qty": pos["qty"],
                                "Buy ₹": round(pos["avg_price"],2),
                                "Sell ₹": cp,
                                "Gross P&L": charges["gross_pnl"],
                                "Charges": charges["total_charges"],
                                "Net P&L": charges["net_pnl"],
                                "Net %": charges["net_pnl_pct"]
                            })
                            del st.session_state.paper_portfolio[sym]
                            st.error(f"🛑 STOP LOSS: SOLD {sym.replace('.NS','')} @ ₹{cp} | Net P&L: ₹{charges['net_pnl']}")
                    except:
                        pass

                # Step 2: New buys
                st.markdown("**Step 2: Scanning for Buy...**")
                slots = at_max - len(st.session_state.paper_portfolio)
                if slots <= 0:
                    st.warning(f"Portfolio Full ({at_max}/{at_max})")
                else:
                    candidates = []
                    with st.spinner("Scanning..."):
                        for sym in STOCK_UNIVERSE:
                            if sym in st.session_state.paper_portfolio: continue
                            try:
                                td = fetch_technical_data(sym)
                                if not td: continue
                                score = 50
                                if td["trend"] == "Bullish": score += 20
                                if 45 <= td["rsi"] <= 65: score += 20
                                elif td["rsi"] < 30: score += 5
                                if td["current_price"] > td["ma50"]: score += 10
                                if score >= at_score:
                                    candidates.append({
                                        "sym": sym,
                                        "score": score,
                                        "price": td["current_price"],
                                        "rsi": td["rsi"]
                                    })
                            except:
                                pass

                    candidates.sort(key=lambda x: x["score"], reverse=True)
                    bought = 0
                    for c in candidates[:slots]:
                        qty = int(at_cap / c["price"])
                        if qty < 1: continue
                        cost = qty * c["price"]
                        stamp = round(cost * 0.00015, 2)
                        total_cost = round(cost + stamp, 2)
                        if total_cost > st.session_state.paper_cash: continue
                        st.session_state.paper_cash -= total_cost
                        st.session_state.paper_portfolio[c["sym"]] = {
                            "qty": qty, "avg_price": c["price"]
                        }
                        st.success(f"✅ BOUGHT {qty}x {c['sym'].replace('.NS','')} @ ₹{c['price']} | Score: {c['score']}/100")
                        bought += 1

                    if bought == 0 and len(candidates) == 0:
                        st.info("કોઈ qualifying stock નથી.")

                save_data()
                st.session_state.last_auto_trade_run = str(datetime.datetime.now())

                bot1, bot2 = st.columns(2)
                bot1.metric("Open Positions", len(st.session_state.paper_portfolio))
                bot2.metric("Available Cash", f"₹{st.session_state.paper_cash:,.2f}")

        if "last_auto_trade_run" in st.session_state:
            st.caption(f"📅 Last Run: {st.session_state.last_auto_trade_run}")

        st.divider()
        st.markdown("#### 🔗 Upstox Connection")
        u1, u2 = st.columns(2)
        with u1:
            if st.button("🏦 Check Account", key="upstox_check"):
                try:
                    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
                    headers = {
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}"
                    }
                    resp = requests.get(
                        "https://api.upstox.com/v2/user/profile",
                        headers=headers
                    )
                    if resp.status_code == 200:
                        st.success("✅ Connected!")
                        st.json(resp.json())
                    else:
                        st.error("❌ Token Expired - Refresh કરો")
                except Exception as e:
                    st.error(f"Error: {e}")
        with u2:
            if st.button("📂 My Holdings", key="upstox_hold"):
                try:
                    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
                    headers = {
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}"
                    }
                    resp = requests.get(
                        "https://api.upstox.com/v2/portfolio/long-term-holdings",
                        headers=headers
                    )
                    st.json(resp.json())
                except Exception as e:
                    st.error(f"Error: {e}")
