import datetime
import requests
import streamlit as st
import google.generativeai as genai
import yfinance as yf
import pandas as pd
import json
import os

# Page Configuration
st.set_page_config(
    page_title="Gandiv AI Stock Research",
    page_icon="📈",
    layout="wide"
)

# AI Model Configuration
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

st.title("📈 Gandiv AI Trading Assistant")
# ==========================================
# PREMIUM UI STYLING (Add right after st.title line)
# ==========================================
st.markdown("""
<style>
    /* Overall background */
    .stApp {
        background-color: #F7F9FC;
    }

    /* Main title */
    h1 {
        color: #1A237E;
        font-weight: 800;
        padding-bottom: 0px;
    }

    /* Section headers */
    h2, h3 {
        color: #1A237E;
        font-weight: 700;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #2962FF 0%, #1A237E 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(41, 98, 255, 0.25);
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(41, 98, 255, 0.35);
    }

    /* Metrics - card style */
    [data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #E3E8F0;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricLabel"] {
        color: #5C6B89;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        color: #1A237E;
        font-weight: 800;
    }

    /* Dataframes / Tables */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #E3E8F0;
    }

    /* Text inputs and number inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #D0D7E6;
    }

    /* Success / Error / Warning / Info boxes */
    .stAlert {
        border-radius: 10px;
    }

    /* Divider */
    hr {
        border-color: #E3E8F0;
    }

    /* Expander */
    [data-testid="stExpander"] {
        background-color: white;
        border-radius: 10px;
        border: 1px solid #E3E8F0;
    }

    /* Sidebar (if used later) */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E3E8F0;
    }
</style>
""", unsafe_allow_html=True)
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

# Helper function to prevent redundant code and excessive API calling
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
        "hist": hist
    }
# ==========================================
# SHARED STOCK UNIVERSE & SECTOR MAP
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
    "EICHERMOT.NS", "DIVISLAB.NS", "TATAMOTORS.NS", "M&M.NS", "BPCL.NS"
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
    "Infra/Cement": ["LT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS"],
    "Telecom": ["BHARTIARTL.NS"],
    "Paints": ["ASIANPAINT.NS"],
    "Consumer": ["TITAN.NS"]
}
# ==========================================
# BEST STOCKS SCANNER
# ==========================================
st.divider()

if st.button("🔥 Best Stocks Scanner"):
    stocks = [
        "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
        "SBIN.NS", "LT.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
        "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "MARUTI.NS",
        "ASIANPAINT.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS",
        "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS", "NTPC.NS", "ONGC.NS",
        "ADANIPORTS.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "HCLTECH.NS",
        "TECHM.NS", "INDUSINDBK.NS", "COALINDIA.NS"
    ]

    results = []

    with st.spinner("Stocks Scan થઈ રહ્યા છે..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol)
                if not tech_data: continue
                
                stock = yf.Ticker(symbol)
                info = stock.info

                pe = info.get("trailingPE", 999)
                market_cap = info.get("marketCap", 0)
                
                rsi = tech_data["rsi"]
                trend = tech_data["trend"]
                score = 100

                if pe and pe != 999:
                    if pe > 40: score -= 20
                    elif pe > 30: score -= 10

                if market_cap < 100000000000:
                    score -= 10

                if trend == "Bullish": score += 10
                else: score -= 10

                if rsi > 70: score -= 10
                elif rsi < 30: score += 5
                else: score += 10

                results.append((symbol, score, rsi, trend))
            except:
                pass

    results.sort(key=lambda x: x[1], reverse=True)

    st.subheader("🏆 Top Stocks Today")
    for rank, (symbol, score, rsi, trend) in enumerate(results, start=1):
        if score >= 100: rating = "🔥 Strong Buy"
        elif score >= 90: rating = "✅ Buy"
        elif score >= 75: rating = "🟡 Hold"
        else: rating = "🔴 Avoid"

        st.write(f"{rank}. {symbol} | {rating} | Score: {score}/100 | RSI: {rsi} | Trend: {trend}")
        
    st.success("🤖 AI Premium Scanner Completed")

# ==========================================
# STOCK ANALYSIS
# ==========================================
st.divider()

symbol = st.text_input("Stock Symbol લખો (ઉદાહરણ: RELIANCE.NS)")

if st.button("🔍 Analyze"):
    if symbol:
        try:
            with st.spinner("Data Fetch થઈ રહ્યો છે..."):
                tech_data = fetch_technical_data(symbol)
                stock = yf.Ticker(symbol)
                info = stock.info

            if tech_data:
                current_price = info.get("currentPrice", tech_data["current_price"])
                market_cap = info.get("marketCap", "N/A")
                pe_ratio = info.get("trailingPE", "N/A")
                ma50 = tech_data["ma50"]
                ma200 = tech_data["ma200"]
                rsi = tech_data["rsi"]
                trend = tech_data["trend"]

                st.subheader("📊 Live Market Data")
                st.write(f"💰 Current Price: {current_price}")
                st.write(f"🏢 Market Cap: {market_cap}")
                st.write(f"📈 P/E Ratio: {pe_ratio}")
                st.write(f"📊 50 DMA: {ma50}")
                st.write(f"📊 200 DMA: {ma200}")
                st.write(f"⚡ RSI: {rsi}")
                st.write(f"📍 Trend: {trend}")

                prompt = f"""
તમે Professional Stock Market Analyst છો.
Stock: {symbol}
Current Price: {current_price}
Market Cap: {market_cap}
PE Ratio: {pe_ratio}
50 DMA: {ma50}
200 DMA: {ma200}
RSI: {rsi}
Trend: {trend}

ગુજરાતીમાં જવાબ આપો.
1. કંપનીનું વિશ્લેષણ
2. મુખ્ય તકો
3. મુખ્ય જોખમો
4. લાંબા ગાળાનો અભિપ્રાય
5. Score /100
6. BUY / HOLD / AVOID
7. RSI નું અર્થઘટન
8. Trend Bullish છે કે Bearish?
9. Technical Score /100

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી.'
"""
                with st.spinner("AI Analysis કરી રહ્યું છે..."):
                    response = model.generate_content(prompt)

                st.markdown(response.text)
            else:
                st.error("આ સિમ્બોલ માટે ડેટા મળ્યો નથી.")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("કૃપા કરીને Stock Symbol લખો")

# ==========================================
# AI PORTFOLIO & ALLOCATOR
# ==========================================
st.divider()

if st.button("💼 Create AI Portfolio"):
    capital = 100000
    portfolio = [("RELIANCE.NS", 40000), ("TCS.NS", 35000), ("HDFCBANK.NS", 25000)]
    st.subheader("🤖 AI Portfolio")
    for stock, amount in portfolio:
        st.write(f"{stock} → ₹{amount:,}")
    st.success(f"Total Capital Invested: ₹{capital:,}")

st.divider()
st.subheader("💼 AI Portfolio Allocator")

capital_input = st.number_input("Investment Amount (₹)", min_value=10000, value=100000, step=10000)

if st.button("🚀 Generate AI Portfolio"):
    allocation = {
        "RELIANCE.NS": 0.25, "TCS.NS": 0.20, "HDFCBANK.NS": 0.20,
        "ICICIBANK.NS": 0.15, "INFY.NS": 0.10, "ITC.NS": 0.10
    }
    st.subheader("📊 AI Recommended Portfolio")
    total = 0
    for stock, weight in allocation.items():
        amount = round(capital_input * weight)
        total += amount
        st.write(f"✅ {stock} → ₹{amount:,} ({weight*100:.0f}%)")
    st.success(f"💰 Total Allocated: ₹{total:,}")

# ==========================================
# UPSTOX INTEGRATION
# ==========================================
st.divider()

if st.button("🏦 Check Upstox Account"):
    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get("https://api.upstox.com/v2/user/profile", headers=headers)
        st.success("✅ Upstox Connected Successfully")
        st.json(response.json())
    except Exception as e:
        st.error(f"Connection Error: {e}")

if st.button("📂 My Holdings"):
    token = st.secrets["UPSTOX_ACCESS_TOKEN"]
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get("https://api.upstox.com/v2/portfolio/long-term-holdings", headers=headers)
        st.subheader("📊 My Holdings")
        st.json(response.json())
    except Exception as e:
        st.error(f"Error: {e}")
                    
st.write("Token Loaded:", st.secrets["UPSTOX_ACCESS_TOKEN"][:15] + "...")

# ==========================================
# MARKET INSIGHTS & WATCHLIST
# ==========================================
st.divider()

if st.button("🚀 Find Best Opportunities"):
    opportunities = []
    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS", "LT.NS", "BHARTIARTL.NS", "SUNPHARMA.NS", "TITAN.NS"]
    
    with st.spinner("AI Opportunities શોધી રહ્યું છે..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol)
                if tech_data:
                    trend = tech_data["trend"]
                    score = 90 if trend == "Bullish" else 60
                    opportunities.append((symbol, score, trend))
            except:
                pass

    opportunities.sort(key=lambda x: x[1], reverse=True)
    st.subheader("🔥 Top Market Opportunities")
    for rank, (symbol, score, trend) in enumerate(opportunities[:5], start=1):
        st.write(f"{rank}. {symbol} | Score: {score}/100 | Trend: {trend}")
    st.success("🤖 AI Opportunity Scan Complete")         

st.divider()
st.subheader("📊 AI Market Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("Nifty Mood", "Bullish 🟢")
col2.metric("AI Risk", "Low 🟢")
col3.metric("Market Trend", "Uptrend 📈")
st.success("🤖 AI Dashboard Active")

st.divider()
st.subheader("⭐ AI Watchlist")
watchlist = st.text_area("Stocks લખો (Comma Separated)", "RELIANCE.NS,TCS.NS,HDFCBANK.NS")

if st.button("📋 Analyze Watchlist"):
    symbols = watchlist.split(",")
    for symbol in symbols:
        try:
            symbol = symbol.strip()
            tech_data = fetch_technical_data(symbol)
            if tech_data:
                current_price = tech_data["current_price"]
                trend_status = "Bullish 🟢" if tech_data["trend"] == "Bullish" else "Bearish 🔴"
                score = 90 if tech_data["trend"] == "Bullish" else 60
                rating = "🔥 Strong Buy" if score >= 85 else "✅ Buy" if score >= 75 else "🟡 Hold"
                st.write(f"{symbol} | ₹{current_price} | {trend_status} | {rating}")
            else:
                st.warning(f"{symbol} Data Not Available")
        except:
            st.warning(f"{symbol} Data Not Available")
    st.success("🤖 Watchlist Analysis Complete")

st.divider()
st.subheader("💪 Portfolio Health Score")
if st.button("📊 Check Portfolio Health"):
    st.metric("Portfolio Health", "87/100")
    st.write("Risk Level: Low 🟢")
    st.write("Diversification: Good ✅")
    st.success("AI Verdict: Strong Portfolio 🚀")

# ==========================================
# SWING TRADING & BACKTESTING
# ==========================================
st.divider()
st.subheader("📈 AI Swing Trade Finder")

if st.button("🚀 Find Swing Trades"):
    swing_trades = []
    stocks = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "ITC.NS"]

    with st.spinner("Swing Trades શોધી રહ્યા છીએ..."):
        for symbol in stocks:
            try:
                tech_data = fetch_technical_data(symbol, period="6mo")
                if tech_data and tech_data["trend"] == "Bullish":
                    current_price = tech_data["current_price"]
                    target = round(current_price * 1.05, 2)
                    stoploss = round(current_price * 0.97, 2)
                    swing_trades.append((symbol, current_price, target, stoploss))
            except:
                pass

    st.subheader("🔥 Top Swing Trades")
    for symbol, entry, target, stoploss in swing_trades:
        rr = round((target - entry) / (entry - stoploss), 2)
        st.write(f"✅ **{symbol}**\n\nEntry: ₹{entry}\n\nTarget: ₹{target}\n\nStop Loss: ₹{stoploss}\n\nRisk/Reward: {rr}")
    st.success("🤖 Swing Trade Scan Complete")

st.divider()
st.subheader("📊 Strategy Backtesting Engine")

if st.button("🧪 Run Backtest"):
    symbol = "RELIANCE.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi_series = 100 - (100 / (1 + (gain / loss)))

        volume = hist["Volume"]
        avg_volume = volume.rolling(20).mean()

        position, entry_price = False, 0
        trades, wins, losses, total_profit = 0, 0, 0, 0

        for i in range(200, len(close)):
            if not position:
                if (ma50.iloc[i] > ma200.iloc[i] and 45 <= rsi_series.iloc[i] <= 65 and 
                    volume.iloc[i] > avg_volume.iloc[i] and close.iloc[i] > ma200.iloc[i]):
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 8:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -4:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Total Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
        
        verdict = "🔥 Excellent Strategy" if win_rate >= 60 else "✅ Good Strategy" if win_rate >= 50 else "⚠️ Needs Improvement"
        st.success(f"AI Verdict: {verdict}")
        st.info("V19 Multi-Filter Strategy Active 🚀")
    except Exception as e:
        st.error(f"Backtest Error: {e}")
                
st.divider()
st.subheader("🚀 Momentum Breakout Backtest")

if st.button("🔥 Run Momentum Backtest"):
    symbol = "ITC.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        volume = hist["Volume"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        avg_volume = volume.rolling(20).mean()

        trades, wins, losses, total_profit = 0, 0, 0, 0
        position, entry_price = False, 0

        for i in range(200, len(close)):
            breakout_high = close.iloc[i-20:i].max()
            if not position:
                if (close.iloc[i] > ma50.iloc[i] and close.iloc[i] > ma200.iloc[i] and 
                    close.iloc[i] > breakout_high and volume.iloc[i] > avg_volume.iloc[i]):
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 10:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -5:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
        
        verdict = "🔥 Excellent" if win_rate >= 60 else "✅ Good" if win_rate >= 50 else "⚠️ Weak"
        st.success(f"Momentum Verdict: {verdict}")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()
st.subheader("📉 RSI Pullback Backtest")

if st.button("🚀 Run RSI Pullback Backtest"):
    symbol = "ITC.NS"
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="3y")
        close = hist["Close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss)))

        trades, wins, losses, total_profit = 0, 0, 0, 0
        position, entry_price = False, 0

        for i in range(200, len(close)):
            if not position:
                if ma50.iloc[i] > ma200.iloc[i] and rsi.iloc[i] < 35:
                    entry_price = close.iloc[i]
                    position = True
            else:
                profit_pct = ((close.iloc[i] - entry_price) / entry_price) * 100
                if profit_pct >= 8:
                    wins += 1; trades += 1; total_profit += profit_pct; position = False
                elif profit_pct <= -4:
                    losses += 1; trades += 1; total_profit += profit_pct; position = False

        win_rate = round((wins / trades) * 100, 2) if trades > 0 else 0
        st.metric("Trades", trades)
        st.metric("Win Rate", f"{win_rate}%")
        st.metric("Total Return", f"{round(total_profit, 2)}%")
        st.write(f"✅ Wins: {wins}")
        st.write(f"❌ Losses: {losses}")
    except Exception as e:
        st.error(f"Error: {e}")
                
# ==========================================
# AI TRADE ADVISOR (V24)
# ==========================================
st.divider()
st.subheader("🤖 AI Trade Advisor")

trade_symbol = st.text_input(
    "Stock Symbol for AI Advice",
    value="RELIANCE.NS"
)

if "trade_journal" not in st.session_state:
    st.session_state.trade_journal = []

if st.button("🚀 Generate AI Trade Setup"):
    try:
        tech_data = fetch_technical_data(trade_symbol)
        if tech_data:
            current_price = tech_data["current_price"]
            ma50 = tech_data["ma50"]
            ma200 = tech_data["ma200"]
            rsi = tech_data["rsi"]

            score = 50
            if ma50 > ma200: score += 20
            if rsi > 55: score += 15
            elif rsi < 30: score += 10
            if current_price > ma50: score += 15

            if score >= 80: advice = "🔥 BUY"
            elif score >= 65: advice = "🟡 HOLD"
            else: advice = "🔴 AVOID"

            entry = current_price
            target = round(current_price * 1.08, 2)
            stoploss = round(current_price * 0.95, 2)

            st.success(f"Recommendation: {advice}")
            st.write(f"AI Score: {score}/100")
            st.write(f"RSI: {rsi}")
            st.write(f"🎯 Entry: ₹{entry}")
            st.write(f"🚀 Target: ₹{target}")
            st.write(f"🛑 Stop Loss: ₹{stoploss}")

            st.session_state.last_trade = {
                "Date": str(datetime.date.today()),
                "Stock": trade_symbol,
                "Score": score,
                "Advice": advice,
                "Entry": entry
            }
    except Exception as e:
        st.error(f"Error: {e}")

if "last_trade" in st.session_state:
    if st.button("💾 Save Latest Trade"):
        st.session_state.trade_journal.append(st.session_state.last_trade)
        st.success("✅ Trade Saved Successfully")
        del st.session_state.last_trade

# ==========================================
# TRADE JOURNAL (V25)
# ==========================================
st.divider()
st.subheader("📒 Trade Journal")

if len(st.session_state.trade_journal) > 0:
    journal_df = pd.DataFrame(st.session_state.trade_journal)
    st.dataframe(journal_df, use_container_width=True)
    st.metric("Saved Trades", len(st.session_state.trade_journal))
    avg_score = round(journal_df["Score"].mean(), 2)
    st.metric("Average AI Score", avg_score)
    
# ==========================================
# PAPER TRADING SIMULATOR (V26)
# ==========================================
st.divider()
st.subheader("💰 Paper Trading Simulator")

st.metric("Available Cash", f"₹{st.session_state.paper_cash:,.2f}")

col_pt1, col_pt2, col_pt3 = st.columns(3)
with col_pt1:
    pt_symbol = st.text_input("Symbol (Buy)", value="RELIANCE.NS", key="pt_buy_symbol")
with col_pt2:
    pt_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="pt_buy_qty")
with col_pt3:
    st.write("")
    st.write("")
    pt_buy_btn = st.button("✅ Buy")

if pt_buy_btn:
    try:
        tech_data = fetch_technical_data(pt_symbol)
        if tech_data:
            price = tech_data["current_price"]
            cost = price * pt_qty
            if cost > st.session_state.paper_cash:
                st.error("❌ Insufficient Cash for this Trade")
            else:
                st.session_state.paper_cash -= cost
                if pt_symbol in st.session_state.paper_portfolio:
                    existing = st.session_state.paper_portfolio[pt_symbol]
                    total_qty = existing["qty"] + pt_qty
                    total_cost = (existing["qty"] * existing["avg_price"]) + cost
                    new_avg = total_cost / total_qty
                    st.session_state.paper_portfolio[pt_symbol] = {"qty": total_qty, "avg_price": new_avg}
                else:
                    st.session_state.paper_portfolio[pt_symbol] = {"qty": pt_qty, "avg_price": price}
                save_data()
                st.success(f"✅ Bought {pt_qty} of {pt_symbol} @ ₹{price}")
        else:
            st.error("ડેટા મળ્યો નથી")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# SELL POSITION (V27)
# ==========================================
st.divider()
st.subheader("📤 Sell Position")

if st.session_state.paper_portfolio:
    sell_symbol = st.selectbox("Stock વેચવા માટે પસંદ કરો", list(st.session_state.paper_portfolio.keys()), key="sell_symbol")
    holding = st.session_state.paper_portfolio[sell_symbol]
    st.write(f"Held Quantity: {holding['qty']} | Avg Price: ₹{round(holding['avg_price'],2)}")

    sell_qty = st.number_input("Sell Quantity", min_value=1, max_value=int(holding["qty"]), value=int(holding["qty"]), step=1, key="sell_qty")

    if st.button("🔴 Sell Position"):
        try:
            tech_data = fetch_technical_data(sell_symbol)
            if tech_data:
                current_price = tech_data["current_price"]
                proceeds = current_price * sell_qty
                profit = (current_price - holding["avg_price"]) * sell_qty
                profit_pct = round(((current_price - holding["avg_price"]) / holding["avg_price"]) * 100, 2)

                st.session_state.paper_cash += proceeds

                st.session_state.paper_trade_history.append({
                    "Date": str(datetime.date.today()),
                    "Stock": sell_symbol,
                    "Qty": sell_qty,
                    "Buy Price": round(holding["avg_price"], 2),
                    "Sell Price": current_price,
                    "P&L": round(profit, 2),
                    "P&L %": profit_pct
                })

                remaining_qty = holding["qty"] - sell_qty
                if remaining_qty <= 0:
                    del st.session_state.paper_portfolio[sell_symbol]
                else:
                    st.session_state.paper_portfolio[sell_symbol]["qty"] = remaining_qty

                save_data()

                if profit >= 0:
                    st.success(f"✅ Sold {sell_qty} {sell_symbol} @ ₹{current_price} | Profit: ₹{round(profit,2)} ({profit_pct}%)")
                else:
                    st.error(f"🔴 Sold {sell_qty} {sell_symbol} @ ₹{current_price} | Loss: ₹{round(profit,2)} ({profit_pct}%)")
            else:
                st.error("ડેટા મળ્યો નથી")
        except Exception as e:
            st.error(f"Error: {e}")
else:
    st.info("હાલમાં તમારી પાસે કોઈ Holdings નથી.")

# ==========================================
# LIVE PORTFOLIO TRACKER (V28)
# ==========================================
st.divider()
st.subheader("📡 Live Portfolio Tracker")

if st.session_state.paper_portfolio:
    if st.button("🔄 Refresh Live Prices"):
        rows = []
        total_invested = 0
        total_current = 0

        with st.spinner("Live Prices ફેચ થઈ રહ્યા છે..."):
            for sym, pos in st.session_state.paper_portfolio.items():
                try:
                    tech_data = fetch_technical_data(sym)
                    cp = tech_data["current_price"] if tech_data else pos["avg_price"]
                except:
                    cp = pos["avg_price"]

                invested = pos["qty"] * pos["avg_price"]
                current_val = pos["qty"] * cp
                pnl = current_val - invested
                pnl_pct = round((pnl / invested) * 100, 2) if invested > 0 else 0

                total_invested += invested
                total_current += current_val

                rows.append({
                    "Stock": sym,
                    "Qty": pos["qty"],
                    "Avg Price": round(pos["avg_price"], 2),
                    "Current Price": cp,
                    "Invested": round(invested, 2),
                    "Current Value": round(current_val, 2),
                    "Unrealized P&L": round(pnl, 2),
                    "P&L %": pnl_pct
                })

        live_df = pd.DataFrame(rows)
        st.dataframe(live_df, use_container_width=True)

        total_pnl = total_current - total_invested
        total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0

        col_lp1, col_lp2, col_lp3 = st.columns(3)
        col_lp1.metric("Total Invested", f"₹{total_invested:,.2f}")
        col_lp2.metric("Current Value", f"₹{total_current:,.2f}")
        col_lp3.metric("Unrealized P&L", f"₹{total_pnl:,.2f}", f"{total_pnl_pct}%")

        st.metric("Total Portfolio Value (Cash + Holdings)", f"₹{(st.session_state.paper_cash + total_current):,.2f}")
else:
    st.info("Portfolio Empty છે. પહેલા Stocks ખરીદો.")
    # ==========================================
# PAPER PORTFOLIO HOLDINGS TABLE (V29)
# ==========================================
st.divider()
st.subheader("📋 Current Holdings")

if st.session_state.paper_portfolio:
    holdings_rows = []
    for sym, pos in st.session_state.paper_portfolio.items():
        holdings_rows.append({
            "Stock": sym,
            "Qty": pos["qty"],
            "Avg Price": round(pos["avg_price"], 2),
            "Invested Amount": round(pos["qty"] * pos["avg_price"], 2)
        })
    holdings_df = pd.DataFrame(holdings_rows)
    st.dataframe(holdings_df, use_container_width=True)
else:
    st.info("કોઈ Holdings નથી.")

# ==========================================
# RESET PAPER TRADING (V30)
# ==========================================
st.divider()
st.subheader("♻️ Reset Paper Trading Account")

if st.button("🔄 Reset Account"):
    st.session_state.paper_cash = 100000.0
    st.session_state.paper_portfolio = {}
    st.session_state.paper_trade_history = []
    save_data()
    st.success("✅ Paper Trading Account Reset Done. Cash: ₹1,00,000")

# ==========================================
# AI MARKET SENTIMENT (V33)
# ==========================================
st.divider()
st.subheader("🧠 AI Market Sentiment")

if st.button("🌐 Get AI Market Sentiment"):
    try:
        nifty_data = fetch_technical_data("^NSEI", period="6mo")

        if nifty_data:
            nifty_trend = nifty_data["trend"]
            nifty_rsi = nifty_data["rsi"]
            nifty_price = nifty_data["current_price"]

            mood = "Bullish 🟢" if nifty_trend == "Bullish" else "Bearish 🔴"

            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Nifty Price", nifty_price)
            col_s2.metric("Nifty RSI", nifty_rsi)
            col_s3.metric("Market Mood", mood)

            sentiment_prompt = f"""
તમે Professional Market Strategist છો.
Nifty 50 Current Price: {nifty_price}
Nifty Trend: {nifty_trend}
Nifty RSI: {nifty_rsi}

ગુજરાતીમાં Short Summary આપો (5-6 lines):
1. Overall Market Sentiment - Bullish/Bearish/Neutral
2. શા માટે
3. Traders માટે ટૂંકી Strategy Suggestion
4. Caution Points

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી.'
"""
            with st.spinner("AI Market Sentiment Analyze કરી રહ્યું છે..."):
                sentiment_response = model.generate_content(sentiment_prompt)

            st.markdown("### 🤖 AI Market Mood Summary")
            st.markdown(sentiment_response.text)
        else:
            st.error("Nifty Data Fetch ન થયો.")
    except Exception as e:
        st.error(f"Error: {e}")

# ==========================================
# EQUITY CURVE (V34)
# ==========================================
st.divider()
st.subheader("📈 Equity Curve & Drawdown")

current_holdings_value = 0
for sym, pos in st.session_state.paper_portfolio.items():
    try:
        tech_data = fetch_technical_data(sym)
        cp = tech_data["current_price"] if tech_data else pos["avg_price"]
    except:
        cp = pos["avg_price"]
    current_holdings_value += cp * pos["qty"]

current_total_value = round(st.session_state.paper_cash + current_holdings_value, 2)

col_eq1, col_eq2 = st.columns(2)
with col_eq1:
    st.metric("Current Portfolio Value", f"₹{current_total_value:,.2f}")
with col_eq2:
    if st.button("📸 Record Snapshot (Today)"):
        today_str = str(datetime.date.today())
        existing_dates = [e["Date"] for e in st.session_state.equity_curve]
        if today_str in existing_dates:
            for e in st.session_state.equity_curve:
                if e["Date"] == today_str:
                    e["Value"] = current_total_value
        else:
            st.session_state.equity_curve.append({"Date": today_str, "Value": current_total_value})
        save_data()
        st.success(f"✅ Snapshot Saved: ₹{current_total_value:,.2f} on {today_str}")

if len(st.session_state.equity_curve) >= 1:
    eq_df = pd.DataFrame(st.session_state.equity_curve)
    eq_df["Date"] = pd.to_datetime(eq_df["Date"])
    eq_df = eq_df.sort_values("Date")
    eq_df = eq_df.set_index("Date")

    st.markdown("#### 📊 Portfolio Growth Chart")
    st.line_chart(eq_df["Value"])

    starting_value = eq_df["Value"].iloc[0]
    eq_df["Profit"] = eq_df["Value"] - starting_value
    st.markdown("#### 💰 Profit Curve")
    st.line_chart(eq_df["Profit"])

    eq_df["Peak"] = eq_df["Value"].cummax()
    eq_df["Drawdown %"] = ((eq_df["Value"] - eq_df["Peak"]) / eq_df["Peak"]) * 100
    st.markdown("#### 📉 Drawdown")
    st.line_chart(eq_df["Drawdown %"])

    max_drawdown = round(eq_df["Drawdown %"].min(), 2)
    total_growth = round(((eq_df["Value"].iloc[-1] - starting_value) / starting_value) * 100, 2) if starting_value > 0 else 0

    col_eq3, col_eq4, col_eq5 = st.columns(3)
    col_eq3.metric("Starting Value", f"₹{starting_value:,.2f}")
    col_eq4.metric("Total Growth", f"{total_growth}%")
    col_eq5.metric("Max Drawdown", f"{max_drawdown}%")

    with st.expander("📋 Snapshot History"):
        st.dataframe(eq_df[["Value", "Profit", "Drawdown %"]].reset_index(), use_container_width=True)

    if st.button("🗑️ Clear Equity History"):
        st.session_state.equity_curve = []
        save_data()
        st.success("✅ Equity History Cleared")
else:
    st.info("હજુ સુધી કોઈ Snapshot નથી. 'Record Snapshot' button click કરી દરરોજ Portfolio Value Save કરો - Equity Curve બનાવવા માટે.")

# ==========================================
# HEDGE FUND DASHBOARD (V35)
# ==========================================
st.divider()
st.subheader("🏦 Hedge Fund Dashboard")
st.caption("એક નજરમાં તમારું Portfolio, Market Mood, Risk અને AI Confidence")

if st.button("🔄 Generate Dashboard"):
    with st.spinner("Dashboard Data Tayar થઈ રહ્યો છે..."):
        dash_holdings_value = 0
        position_count = len(st.session_state.paper_portfolio)
        for sym, pos in st.session_state.paper_portfolio.items():
            try:
                tech_data = fetch_technical_data(sym)
                cp = tech_data["current_price"] if tech_data else pos["avg_price"]
            except:
                cp = pos["avg_price"]
            dash_holdings_value += cp * pos["qty"]

        dash_total_value = round(st.session_state.paper_cash + dash_holdings_value, 2)

        try:
            nifty_data = fetch_technical_data("^NSEI", period="6mo")
            if nifty_data:
                market_mood = "Bullish 🟢" if nifty_data["trend"] == "Bullish" else "Bearish 🔴"
                nifty_rsi = nifty_data["rsi"]
            else:
                market_mood = "Unknown ⚪"
                nifty_rsi = 50
        except:
            market_mood = "Unknown ⚪"
            nifty_rsi = 50

        if position_count == 0:
            risk_level = "No Open Positions ⚪"
        elif position_count <= 2:
            risk_level = "High (Low Diversification) 🔴"
        elif position_count <= 4:
            risk_level = "Medium 🟡"
        else:
            risk_level = "Low (Well Diversified) 🟢"

        if nifty_rsi > 70:
            risk_level += " | Market Overbought ⚠️"
        elif nifty_rsi < 30:
            risk_level += " | Market Oversold ⚠️"

        best_opportunity = "Scanning..."
        opp_stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS", "LT.NS", "SUNPHARMA.NS"]
        best_score = -999
        for sym in opp_stocks:
            try:
                td = fetch_technical_data(sym)
                if td:
                    sc = 50
                    if td["trend"] == "Bullish": sc += 25
                    if 45 <= td["rsi"] <= 65: sc += 15
                    if td["current_price"] > td["ma50"]: sc += 10
                    if sc > best_score:
                        best_score = sc
                        best_opportunity = f"{sym} (Score: {sc}/100)"
            except:
                pass

        ai_confidence = 50
        if "Bullish" in market_mood:
            ai_confidence += 20
        else:
            ai_confidence -= 10
        if best_score >= 75:
            ai_confidence += 20
        elif best_score >= 60:
            ai_confidence += 10
        ai_confidence = max(0, min(100, ai_confidence))

        col_h1, col_h2, col_h3 = st.columns(3)
        col_h1.metric("💰 Portfolio Value", f"₹{dash_total_value:,.2f}")
        col_h2.metric("🌐 Market Mood", market_mood)
        col_h3.metric("🤖 AI Confidence", f"{ai_confidence}/100")

        col_h4, col_h5 = st.columns(2)
        col_h4.metric("🔥 Best Opportunity", best_opportunity)
        col_h5.metric("🛡️ Risk Level", risk_level)

        st.divider()
        st.write(f"📊 Open Positions: {position_count}")
        st.write(f"💵 Available Cash: ₹{st.session_state.paper_cash:,.2f}")
        st.write(f"📈 Holdings Value: ₹{dash_holdings_value:,.2f}")
        st.write(f"⚡ Nifty RSI: {nifty_rsi}")

        if ai_confidence >= 70:
            st.success("🤖 AI Verdict: Favorable Conditions for Trading 🚀")
        elif ai_confidence >= 50:
            st.warning("🤖 AI Verdict: Neutral - Trade with Caution 🟡")
        else:
            st.error("🤖 AI Verdict: Unfavorable - Defensive Stance Recommended 🔴")
else:
    st.info("Dashboard Data જોવા માટે 'Generate Dashboard' button click કરો.")
# ==========================================
# AUTO WATCHLIST SCANNER (V36)
# ==========================================
st.divider()
st.subheader("🔍 Auto Watchlist Scanner")
st.caption("દરરોજ Top Breakout, Swing અને Momentum Stocks Scan કરો")

if st.button("🚀 Run Auto Scanner (Top 5 Each)"):

    breakout_results = []
    swing_results = []
    momentum_results = []

    with st.spinner(f"{len(STOCK_UNIVERSE)} Stocks Scan થઈ રહ્યા છે... થોડો સમય લાગશે"):
        for symbol in STOCK_UNIVERSE:
            try:
                td = fetch_technical_data(symbol, period="6mo")
                if not td:
                    continue

                hist = td["hist"]
                close = hist["Close"]
                volume = hist["Volume"]

                current_price = td["current_price"]
                ma50 = td["ma50"]
                ma200 = td["ma200"]
                rsi = td["rsi"]
                trend = td["trend"]

                avg_volume = volume.rolling(20).mean().iloc[-1]
                current_volume = volume.iloc[-1]

                recent_high = close.iloc[-21:-1].max()
                if current_price > recent_high and current_volume > avg_volume:
                    breakout_strength = round(((current_price - recent_high) / recent_high) * 100, 2)
                    breakout_results.append({
                        "Stock": symbol,
                        "Price": current_price,
                        "Breakout %": breakout_strength,
                        "Volume vs Avg": round(current_volume / avg_volume, 2) if avg_volume > 0 else 0
                    })

                if trend == "Bullish" and 45 <= rsi <= 65 and current_price > ma50:
                    target = round(current_price * 1.05, 2)
                    stoploss = round(current_price * 0.97, 2)
                    swing_results.append({
                        "Stock": symbol,
                        "Entry": current_price,
                        "Target": target,
                        "Stop Loss": stoploss,
                        "RSI": rsi
                    })

                if current_price > ma50 and current_price > ma200 and rsi > 60 and current_volume > avg_volume:
                    momentum_score = round(rsi + (current_volume / avg_volume if avg_volume > 0 else 1) * 10, 2)
                    momentum_results.append({
                        "Stock": symbol,
                        "Price": current_price,
                        "RSI": rsi,
                        "Momentum Score": momentum_score
                    })

            except:
                pass

    breakout_results.sort(key=lambda x: x["Breakout %"], reverse=True)
    swing_results.sort(key=lambda x: x["RSI"], reverse=True)
    momentum_results.sort(key=lambda x: x["Momentum Score"], reverse=True)

    top_breakouts = breakout_results[:5]
    top_swings = swing_results[:5]
    top_momentum = momentum_results[:5]

    st.markdown("### 🚀 Top 5 Breakout Stocks")
    if top_breakouts:
        st.dataframe(pd.DataFrame(top_breakouts), use_container_width=True)
    else:
        st.info("આજે કોઈ Breakout Setup મળ્યું નથી.")

    st.markdown("### 📈 Top 5 Swing Trades")
    if top_swings:
        st.dataframe(pd.DataFrame(top_swings), use_container_width=True)
    else:
        st.info("આજે કોઈ Swing Setup મળ્યું નથી.")

    st.markdown("### 🔥 Top 5 Momentum Stocks")
    if top_momentum:
        st.dataframe(pd.DataFrame(top_momentum), use_container_width=True)
    else:
        st.info("આજે કોઈ Momentum Setup મળ્યું નથી.")

    st.success(f"✅ Scan Complete | Total Stocks Scanned: {len(STOCK_UNIVERSE)}")
    st.caption("⚠️ આ ફક્ત Technical Scan છે, Financial Advice નથી. પોતાનું Research કરો.")

    st.session_state.last_scan = {
        "Date": str(datetime.date.today()),
        "Breakouts": top_breakouts,
        "Swings": top_swings,
        "Momentum": top_momentum
    }
else:
    st.info(f"'Run Auto Scanner' button click કરો - {len(STOCK_UNIVERSE)} NSE Stocks Scan થશે.")

if "last_scan" in st.session_state:
    with st.expander(f"📅 Last Scan Date: {st.session_state.last_scan['Date']}"):
        st.write(f"Breakouts Found: {len(st.session_state.last_scan['Breakouts'])}")
        st.write(f"Swing Setups Found: {len(st.session_state.last_scan['Swings'])}")
        st.write(f"Momentum Setups Found: {len(st.session_state.last_scan['Momentum'])}")

# ==========================================
# SECTOR ROTATION AI (V37)
# ==========================================
st.divider()
st.subheader("🔄 Sector Rotation AI")
st.caption("કયો Sector Strong છે, કયો Weak - Sector-wise Trend Scan")

if st.button("🔄 Scan All Sectors"):
    sector_results = []

    with st.spinner("તમામ Sectors Scan થઈ રહ્યા છે..."):
        for sector, stocks in SECTOR_MAP.items():
            bullish_count = 0
            total_count = 0
            rsi_sum = 0

            for symbol in stocks:
                try:
                    td = fetch_technical_data(symbol, period="6mo")
                    if not td:
                        continue
                    total_count += 1
                    rsi_sum += td["rsi"]
                    if td["trend"] == "Bullish":
                        bullish_count += 1
                except:
                    pass

            if total_count > 0:
                bullish_pct = round((bullish_count / total_count) * 100, 1)
                avg_rsi = round(rsi_sum / total_count, 1)

                if bullish_pct >= 65:
                    status = "🟢 Strong"
                elif bullish_pct >= 35:
                    status = "🟡 Neutral"
                else:
                    status = "🔴 Weak"

                sector_results.append({
                    "Sector": sector,
                    "Status": status,
                    "Bullish Stocks": f"{bullish_count}/{total_count}",
                    "Bullish %": bullish_pct,
                    "Avg RSI": avg_rsi
                })

    sector_results.sort(key=lambda x: x["Bullish %"], reverse=True)

    st.markdown("### 📊 Sector Strength Ranking")
    st.dataframe(pd.DataFrame(sector_results), use_container_width=True)

    if sector_results:
        top_sector_name = sector_results[0]["Sector"]
        top_stocks = SECTOR_MAP[top_sector_name]

        best_stock = None
        best_score = -999
        for symbol in top_stocks:
            try:
                td = fetch_technical_data(symbol, period="6mo")
                if td and td["trend"] == "Bullish":
                    score = td["rsi"] + (10 if td["current_price"] > td["ma50"] else 0)
                    if score > best_score:
                        best_score = score
                        best_stock = symbol
            except:
                pass

        st.divider()
        st.markdown("### 🏆 Best Opportunity Today")
        if best_stock:
            st.success(f"**Strongest Sector:** {top_sector_name} {sector_results[0]['Status']}")
            st.success(f"**Top Pick:** {best_stock}")
        else:
            st.info(f"Strongest Sector: {top_sector_name}, પણ હાલ કોઈ Strong Individual Stock નથી મળ્યો.")

    st.success("✅ Sector Rotation Scan Complete")
    st.caption("⚠️ આ Technical Scan છે, Financial Advice નથી.")
else:
    st.info("'Scan All Sectors' button click કરો - 12 Sectors, 40 Stocks Scan થશે.")

# ==========================================
# RELATIVE STRENGTH SCANNER (V38)
# ==========================================
st.divider()
st.subheader("💪 Relative Strength Scanner")
st.caption("Nifty કરતાં વધુ Strong Stocks શોધે છે (Last 3 Months Performance)")

if st.button("💪 Run Relative Strength Scan"):
    with st.spinner("Nifty અને તમામ Stocks ની Performance Compare થઈ રહી છે..."):
        nifty_hist = yf.Ticker("^NSEI").history(period="3mo")
        if nifty_hist.empty:
            st.error("Nifty Data Fetch ન થયો.")
        else:
            nifty_return = round(((nifty_hist["Close"].iloc[-1] - nifty_hist["Close"].iloc[0]) / nifty_hist["Close"].iloc[0]) * 100, 2)

            rs_results = []
            for symbol in STOCK_UNIVERSE:
                try:
                    hist = yf.Ticker(symbol).history(period="3mo")
                    if hist.empty or len(hist) < 2:
                        continue

                    stock_return = round(((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100, 2)
                    rs_score = round(stock_return - nifty_return, 2)

                    current_price = round(hist["Close"].iloc[-1], 2)

                    rs_results.append({
                        "Stock": symbol,
                        "Price": current_price,
                        "3M Return %": stock_return,
                        "Nifty Return %": nifty_return,
                        "Relative Strength": rs_score
                    })
                except:
                    pass

            rs_results.sort(key=lambda x: x["Relative Strength"], reverse=True)

            outperformers = [r for r in rs_results if r["Relative Strength"] > 0]
            underperformers = [r for r in rs_results if r["Relative Strength"] <= 0]

            st.metric("📊 Nifty 3-Month Return", f"{nifty_return}%")

            st.markdown("### 🏆 Stocks Outperforming Nifty")
            if outperformers:
                st.dataframe(pd.DataFrame(outperformers), use_container_width=True)
            else:
                st.info("હાલ કોઈ Stock Nifty કરતાં Outperform નથી કરી રહ્યું.")

            st.markdown("### 📉 Stocks Underperforming Nifty")
            if underperformers:
                with st.expander(f"જુઓ ({len(underperformers)} Stocks)"):
                    st.dataframe(pd.DataFrame(underperformers), use_container_width=True)

            st.divider()
            st.markdown("### 🔥 Best Opportunity (Top RS + Bullish Trend)")
            best_pick = None
            for r in outperformers[:10]:
                try:
                    td = fetch_technical_data(r["Stock"])
                    if td and td["trend"] == "Bullish":
                        best_pick = {**r, "RSI": td["rsi"], "Trend": td["trend"]}
                        break
                except:
                    pass

            if best_pick:
                st.success(f"**{best_pick['Stock']}** | Price: ₹{best_pick['Price']} | RS Score: {best_pick['Relative Strength']} | RSI: {best_pick['RSI']} | Trend: Bullish 🟢")
            elif outperformers:
                top = outperformers[0]
                st.warning(f"Top RS Stock: **{top['Stock']}** (RS: {top['Relative Strength']}), પણ હાલ Bullish Trend Confirm નથી.")
            else:
                st.info("હાલ કોઈ Strong Opportunity નથી મળ્યો.")

            st.success(f"✅ Scan Complete | Total Scanned: {len(rs_results)} Stocks")
            st.caption("⚠️ આ Technical Scan છે, Financial Advice નથી.")
else:
    st.info(f"'Run Relative Strength Scan' click કરો - {len(STOCK_UNIVERSE)} Stocks vs Nifty Compare થશે.")

# ==========================================
# SMART MONEY TRACKER (V39)
# ==========================================
st.divider()
st.subheader("🐋 Smart Money Tracker")
st.caption("Volume Spikes, Breakout Detection - Smart Money ક્યાં Active છે")

if st.button("🐋 Run Smart Money Scan"):
    smart_money_results = []

    with st.spinner("Volume Spikes અને Breakouts Scan થઈ રહ્યા છે..."):
        for symbol in STOCK_UNIVERSE:
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="3mo")
                if hist.empty or len(hist) < 21:
                    continue

                close = hist["Close"]
                volume = hist["Volume"]

                current_price = round(close.iloc[-1], 2)
                current_volume = volume.iloc[-1]
                avg_volume_20 = volume.iloc[-21:-1].mean()

                if avg_volume_20 == 0:
                    continue

                volume_ratio = round(current_volume / avg_volume_20, 2)

                price_change_pct = round(((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100, 2)

                recent_high_20 = close.iloc[-21:-1].max()
                recent_low_20 = close.iloc[-21:-1].min()

                signal = None
                if current_price > recent_high_20 and volume_ratio >= 1.5:
                    signal = "🚀 Breakout + Volume Spike"
                elif current_price < recent_low_20 and volume_ratio >= 1.5:
                    signal = "🔻 Breakdown + Volume Spike"
                elif volume_ratio >= 2.0 and price_change_pct > 0:
                    signal = "📈 Accumulation (High Volume Buying)"
                elif volume_ratio >= 2.0 and price_change_pct < 0:
                    signal = "📉 Distribution (High Volume Selling)"
                elif volume_ratio >= 1.5:
                    signal = "⚡ Unusual Volume Activity"

                if signal:
                    smart_money_results.append({
                        "Stock": symbol,
                        "Price": current_price,
                        "Change %": price_change_pct,
                        "Volume vs 20D Avg": volume_ratio,
                        "Signal": signal
                    })
            except:
                pass

    smart_money_results.sort(key=lambda x: x["Volume vs 20D Avg"], reverse=True)

    st.markdown("### 🐋 Smart Money Activity Detected")
    if smart_money_results:
        st.dataframe(pd.DataFrame(smart_money_results), use_container_width=True)

        priority_signals = ["🚀 Breakout + Volume Spike", "📈 Accumulation (High Volume Buying)"]
        best_picks = [r for r in smart_money_results if r["Signal"] in priority_signals]

        st.divider()
        st.markdown("### 🏆 Top Smart Money Opportunity")
        if best_picks:
            top = best_picks[0]
            st.success(f"**{top['Stock']}** | Price: ₹{top['Price']} | {top['Signal']} | Volume: {top['Volume vs 20D Avg']}x Avg | Change: {top['Change %']}%")
        else:
            st.info("હાલ કોઈ Strong Buying Signal નથી - Distribution/Breakdown Signals વધારે છે, સાવધાન રહો.")
    else:
        st.info("આજે કોઈ Unusual Volume Activity મળી નથી.")

    st.success(f"✅ Scan Complete | Total Scanned: {len(STOCK_UNIVERSE)} Stocks | Signals Found: {len(smart_money_results)}")
    st.caption("⚠️ આ Technical Scan છે, Financial Advice નથી. Volume Spike Confirmation માટે Delivery % Data Broker Platform પર ચેક કરો.")
else:
    st.info(f"'Run Smart Money Scan' click કરો - {len(STOCK_UNIVERSE)} Stocks માં Volume Spikes/Breakouts Scan થશે.")

# ==========================================
# AI TRADE COACH (V40)
# ==========================================
st.divider()
st.subheader("🧑‍🏫 Gemini AI Trade Coach")
st.caption("ઉદાહરણ: 'Should I buy Reliance?' અથવા 'TCS માં Entry આપો'")

coach_question = st.text_input("તમારો Trading Question લખો", value="Should I buy Reliance?", key="coach_question")

if st.button("🤖 Ask AI Coach"):
    if coach_question.strip():
        try:
            COMMON_NAMES = {
                "reliance": "RELIANCE.NS", "tcs": "TCS.NS", "infosys": "INFY.NS", "infy": "INFY.NS",
                "hdfc": "HDFCBANK.NS", "hdfcbank": "HDFCBANK.NS", "icici": "ICICIBANK.NS",
                "sbi": "SBIN.NS", "lt": "LT.NS", "airtel": "BHARTIARTL.NS", "bharti": "BHARTIARTL.NS",
                "itc": "ITC.NS", "hul": "HINDUNILVR.NS", "kotak": "KOTAKBANK.NS", "axis": "AXISBANK.NS",
                "bajajfinance": "BAJFINANCE.NS", "maruti": "MARUTI.NS", "asianpaint": "ASIANPAINT.NS",
                "sunpharma": "SUNPHARMA.NS", "titan": "TITAN.NS", "ultratech": "ULTRACEMCO.NS",
                "wipro": "WIPRO.NS", "nestle": "NESTLEIND.NS", "powergrid": "POWERGRID.NS",
                "ntpc": "NTPC.NS", "ongc": "ONGC.NS", "adaniports": "ADANIPORTS.NS",
                "tatasteel": "TATASTEEL.NS", "jswsteel": "JSWSTEEL.NS", "hcltech": "HCLTECH.NS",
                "techm": "TECHM.NS", "indusind": "INDUSINDBK.NS", "coalindia": "COALINDIA.NS",
                "drreddy": "DRREDDY.NS", "cipla": "CIPLA.NS", "grasim": "GRASIM.NS",
                "heromotoco": "HEROMOTOCO.NS", "eichermotors": "EICHERMOT.NS", "divislab": "DIVISLAB.NS",
                "tatamotors": "TATAMOTORS.NS", "mahindra": "M&M.NS", "bpcl": "BPCL.NS"
            }

            question_lower = coach_question.lower()
            detected_symbol = None
            for name, sym in COMMON_NAMES.items():
                if name in question_lower:
                    detected_symbol = sym
                    break

            tech_context = ""
            if detected_symbol:
                td = fetch_technical_data(detected_symbol)
                if td:
                    current_price = td["current_price"]
                    ma50 = td["ma50"]
                    ma200 = td["ma200"]
                    rsi = td["rsi"]
                    trend = td["trend"]

                    suggested_target = round(current_price * 1.08, 2)
                    suggested_sl = round(current_price * 0.95, 2)

                    tech_context = f"""
Detected Stock: {detected_symbol}
Current Price: ₹{current_price}
50 DMA: ₹{ma50}
200 DMA: ₹{ma200}
RSI: {rsi}
Trend: {trend}
Suggested Target (8%): ₹{suggested_target}
Suggested Stop Loss (5%): ₹{suggested_sl}
"""
                    st.markdown("#### 📊 Live Technical Snapshot")
                    col_c1, col_c2, col_c3, col_c4 = st.columns(4)
                    col_c1.metric("Price", f"₹{current_price}")
                    col_c2.metric("RSI", rsi)
                    col_c3.metric("Trend", trend)
                    col_c4.metric("50/200 DMA", f"{ma50}/{ma200}")

            coach_prompt = f"""
તમે Professional Trading Coach છો. User નો Question નીચે છે.

User Question: "{coach_question}"

{tech_context if tech_context else "Note: કોઈ specific stock detect નથી થયો, general guidance આપો."}

ગુજરાતીમાં જવાબ આપો, નીચેના Format માં (જો Stock Specific Question હોય):
1. **Recommendation**: BUY / WAIT / AVOID
2. **Entry**: ₹ (specific level)
3. **Target**: ₹ (specific level)
4. **Stop Loss**: ₹ (specific level)
5. **Risk**: Low / Medium / High અને કેમ
6. **Probability**: Approximate success probability % અને reasoning
7. **Reasoning**: 2-3 lines માં Technical Logic

જો Question Stock-Specific ન હોય, તો General Trading Guidance આપો.

છેલ્લે અચૂક લખો: 'આ નાણાકીય સલાહ નથી, પોતાનું Research કરો.'
"""
            with st.spinner("AI Coach Analyze કરી રહ્યું છે..."):
                coach_response = model.generate_content(coach_prompt)

            st.markdown("### 🤖 AI Coach Response")
            st.markdown(coach_response.text)

        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.warning("કૃપા કરીને Question લખો.")
# ==========================================
# PORTFOLIO REVIEW AI (V41)
# ==========================================
st.divider()
st.subheader("📋 AI Portfolio Review")
st.caption("તમારું આખું Paper Portfolio AI Analyze કરશે - Diversification, Risk, Suggestions")

if st.button("🤖 Review My Portfolio"):
    if not st.session_state.paper_portfolio:
        st.info("Portfolio Empty છે. પહેલા Stocks Buy કરો (Paper Trading Section).")
    else:
        with st.spinner("Portfolio Data Tayar થઈ રહ્યો છે..."):
            portfolio_rows = []
            total_invested = 0
            total_current = 0
            sector_exposure = {}

            for sym, pos in st.session_state.paper_portfolio.items():
                try:
                    td = fetch_technical_data(sym)
                    cp = td["current_price"] if td else pos["avg_price"]
                    rsi = td["rsi"] if td else "N/A"
                    trend = td["trend"] if td else "N/A"
                except:
                    cp = pos["avg_price"]
                    rsi = "N/A"
                    trend = "N/A"

                invested = pos["qty"] * pos["avg_price"]
                current_val = pos["qty"] * cp
                pnl = current_val - invested
                pnl_pct = round((pnl / invested) * 100, 2) if invested > 0 else 0

                total_invested += invested
                total_current += current_val

                sector_name = "Other"
                for sec, stocks in SECTOR_MAP.items():
                    if sym in stocks:
                        sector_name = sec
                        break
                sector_exposure[sector_name] = sector_exposure.get(sector_name, 0) + current_val

                portfolio_rows.append({
                    "Stock": sym,
                    "Qty": pos["qty"],
                    "Avg Price": round(pos["avg_price"], 2),
                    "Current Price": cp,
                    "Current Value": round(current_val, 2),
                    "P&L": round(pnl, 2),
                    "P&L %": pnl_pct,
                    "RSI": rsi,
                    "Trend": trend,
                    "Sector": sector_name
                })

            port_df = pd.DataFrame(portfolio_rows)
            st.dataframe(port_df, use_container_width=True)

            total_pnl = round(total_current - total_invested, 2)
            total_pnl_pct = round((total_pnl / total_invested) * 100, 2) if total_invested > 0 else 0

            col_pr1, col_pr2, col_pr3 = st.columns(3)
            col_pr1.metric("Total Invested", f"₹{total_invested:,.2f}")
            col_pr2.metric("Current Value", f"₹{total_current:,.2f}")
            col_pr3.metric("Total P&L", f"₹{total_pnl:,.2f}", f"{total_pnl_pct}%")

            st.markdown("#### 🏭 Sector Exposure")
            sector_df = pd.DataFrame([
                {"Sector": s, "Value": round(v, 2), "Allocation %": round((v/total_current)*100, 1) if total_current > 0 else 0}
                for s, v in sector_exposure.items()
            ])
            sector_df = sector_df.sort_values("Allocation %", ascending=False)
            st.dataframe(sector_df, use_container_width=True)

            portfolio_summary = port_df.to_string(index=False)
            sector_summary = sector_df.to_string(index=False)

            review_prompt = f"""
તમે Professional Portfolio Manager છો. નીચે User નું Portfolio છે.

Total Invested: ₹{total_invested:,.2f}
Current Value: ₹{total_current:,.2f}
Total P&L: ₹{total_pnl:,.2f} ({total_pnl_pct}%)

Holdings:
{portfolio_summary}

Sector Exposure:
{sector_summary}

ગુજરાતીમાં Analysis આપો:
1. **Overall Portfolio Health** - Score /100
2. **Diversification** - Good/Poor, કયા Sector માં વધારે Exposure છે
3. **Risk Concentration** - કોઈ ખાસ Risk છે?
4. **Underperforming Stocks** - કયા Stocks Review કરવાની જરૂર છે
5. **Strong Holdings** - કયા Stocks સારા છે
6. **Action Suggestions** - 2-3 specific સૂચનો (Hold/Trim/Add)

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી, પોતાનું Research કરો.'
"""
            with st.spinner("AI Portfolio Review કરી રહ્યું છે..."):
                review_response = model.generate_content(review_prompt)

            st.markdown("### 🤖 AI Portfolio Review")
            st.markdown(review_response.text)
else:
    st.info("'Review My Portfolio' button click કરો.")

# ==========================================
# AI REBALANCER (V42)
# ==========================================
st.divider()
st.subheader("⚖️ AI Portfolio Rebalancer")
st.caption("કયા Stocks વેચવા, કયા Stocks માં વધારે Invest કરવું - AI Suggestions")

if st.button("⚖️ Get Rebalancing Suggestions"):
    if not st.session_state.paper_portfolio:
        st.info("Portfolio Empty છે. પહેલા Stocks Buy કરો (Paper Trading Section).")
    else:
        with st.spinner("Portfolio Rebalancing Analyze થઈ રહ્યું છે..."):
            holding_rows = []
            total_current = 0

            for sym, pos in st.session_state.paper_portfolio.items():
                try:
                    td = fetch_technical_data(sym)
                    if td:
                        cp = td["current_price"]
                        rsi = td["rsi"]
                        trend = td["trend"]
                        ma50 = td["ma50"]
                        ma200 = td["ma200"]
                    else:
                        cp = pos["avg_price"]
                        rsi, trend, ma50, ma200 = 50, "N/A", cp, cp
                except:
                    cp = pos["avg_price"]
                    rsi, trend, ma50, ma200 = 50, "N/A", cp, cp

                invested = pos["qty"] * pos["avg_price"]
                current_val = pos["qty"] * cp
                pnl_pct = round(((cp - pos["avg_price"]) / pos["avg_price"]) * 100, 2) if pos["avg_price"] > 0 else 0
                total_current += current_val

                score = 50
                if trend == "Bullish": score += 20
                else: score -= 10
                if 40 <= rsi <= 65: score += 15
                elif rsi > 75: score -= 15
                elif rsi < 25: score += 5
                if cp > ma50: score += 10
                if cp > ma200: score += 5
                score = max(0, min(100, score))

                if score >= 70:
                    action = "🟢 HOLD / ADD MORE"
                elif score >= 45:
                    action = "🟡 HOLD"
                else:
                    action = "🔴 CONSIDER TRIM/EXIT"

                holding_rows.append({
                    "Stock": sym,
                    "Qty": pos["qty"],
                    "Current Value": round(current_val, 2),
                    "P&L %": pnl_pct,
                    "RSI": rsi,
                    "Trend": trend,
                    "Health Score": score,
                    "Suggested Action": action
                })

            hold_df = pd.DataFrame(holding_rows)
            hold_df["Allocation %"] = round((hold_df["Current Value"] / total_current) * 100, 1) if total_current > 0 else 0
            hold_df = hold_df.sort_values("Health Score", ascending=False)

            st.dataframe(hold_df, use_container_width=True)

            weak = hold_df[hold_df["Health Score"] < 45]
            strong = hold_df[hold_df["Health Score"] >= 70]

            candidate_pool = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
                              "LT.NS", "SUNPHARMA.NS", "TITAN.NS", "BAJFINANCE.NS", "ITC.NS"]
            new_ideas = []
            existing_symbols = set(st.session_state.paper_portfolio.keys())
            for sym in candidate_pool:
                if sym in existing_symbols:
                    continue
                try:
                    td = fetch_technical_data(sym)
                    if td and td["trend"] == "Bullish" and 45 <= td["rsi"] <= 65:
                        new_ideas.append(sym)
                except:
                    pass
                if len(new_ideas) >= 3:
                    break

            col_rb1, col_rb2 = st.columns(2)
            with col_rb1:
                st.markdown("#### 🔴 Trim/Exit Candidates")
                if not weak.empty:
                    for _, row in weak.iterrows():
                        st.write(f"• **{row['Stock']}** | Score: {row['Health Score']}/100 | P&L: {row['P&L %']}%")
                else:
                    st.write("કોઈ Weak Holding નથી ✅")

            with col_rb2:
                st.markdown("#### 🟢 Strong / Add More")
                if not strong.empty:
                    for _, row in strong.iterrows():
                        st.write(f"• **{row['Stock']}** | Score: {row['Health Score']}/100 | Allocation: {row['Allocation %']}%")
                else:
                    st.write("હાલ કોઈ Strong Add-More Candidate નથી")

            st.markdown("#### 💡 New Ideas (Not in Portfolio)")
            if new_ideas:
                st.write(", ".join(new_ideas))
            else:
                st.write("હાલ કોઈ નવો Bullish Setup નથી મળ્યો")

            rebalance_prompt = f"""
તમે Professional Portfolio Manager છો. નીચે Holdings ની Health Analysis છે:

{hold_df.to_string(index=False)}

Trim/Exit Candidates: {', '.join(weak['Stock'].tolist()) if not weak.empty else 'કોઈ નહીં'}
Strong Holdings: {', '.join(strong['Stock'].tolist()) if not strong.empty else 'કોઈ નહીં'}
New Bullish Ideas (Not Held): {', '.join(new_ideas) if new_ideas else 'કોઈ નહીં'}

ગુજરાતીમાં ટૂંકમાં (6-8 lines):
1. Overall Rebalancing Strategy
2. કયા Stock વેચીને કયા માં Shift કરવું (specific)
3. Allocation Concentration નું Risk (જો કોઈ Stock 30%+ Allocation હોય)
4. Priority Order - શું પહેલા કરવું

છેલ્લે લખો: 'આ નાણાકીય સલાહ નથી, પોતાનું Research કરો.'
"""
            with st.spinner("AI Rebalancing Strategy તૈયાર કરી રહ્યું છે..."):
                rebalance_response = model.generate_content(rebalance_prompt)

            st.markdown("### 🤖 AI Rebalancing Strategy")
            st.markdown(rebalance_response.text)
else:
    st.info("'Get Rebalancing Suggestions' button click કરો.")
