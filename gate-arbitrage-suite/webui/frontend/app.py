"""
Streamlit Frontend for Gate.io Arbitrage Suite
User-friendly interface for managing arbitrage strategies
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import yaml
import time
from typing import Dict, List, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
st.set_page_config(
    page_title="Gate.io Arbitrage Suite",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "password" not in st.session_state:
    st.session_state.password = ""

# Authentication
def authenticate(username: str, password: str) -> bool:
    """Authenticate with the backend API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            auth=(username, password)
        )
        return response.status_code == 200
    except:
        return False

# API Helper Functions
def api_request(endpoint: str, method: str = "GET", data: Dict = None) -> Dict:
    """Make authenticated API request"""
    try:
        auth = (st.session_state.username, st.session_state.password)
        
        if method == "GET":
            response = requests.get(f"{API_BASE_URL}{endpoint}", auth=auth)
        elif method == "POST":
            response = requests.post(f"{API_BASE_URL}{endpoint}", json=data, auth=auth)
        elif method == "PUT":
            response = requests.put(f"{API_BASE_URL}{endpoint}", json=data, auth=auth)
        elif method == "DELETE":
            response = requests.delete(f"{API_BASE_URL}{endpoint}", auth=auth)
            
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
        return None

# Login Page
def login_page():
    """Display login page"""
    st.title("🔐 Gate.io Arbitrage Suite Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login", use_container_width=True):
                if authenticate(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.password = password
                    st.rerun()
                else:
                    st.error("Invalid credentials")

# Main Dashboard
def dashboard_page():
    """Display main dashboard"""
    st.title("📊 Gate.io Arbitrage Suite Dashboard")
    
    # Get bot status
    status = api_request("/bot/status")
    
    # Status cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Bot Status",
            "🟢 Running" if status and status.get("running") else "🔴 Stopped",
            delta=None
        )
        
    with col2:
        pnl = status.get("total_pnl", 0) if status else 0
        st.metric(
            "Total PnL",
            f"${pnl:,.2f}",
            delta=f"{pnl/100:.2f}%" if pnl != 0 else None
        )
        
    with col3:
        positions = status.get("active_positions", 0) if status else 0
        st.metric(
            "Active Positions",
            positions,
            delta=None
        )
        
    with col4:
        controllers = len(status.get("controllers", [])) if status else 0
        st.metric(
            "Active Controllers",
            controllers,
            delta=None
        )
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 PnL History")
        # Generate sample data (in production, fetch from API)
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        pnl_data = pd.DataFrame({
            'Date': dates,
            'PnL': [i * 10 + (i % 3) * 5 for i in range(30)]
        })
        
        fig = px.line(pnl_data, x='Date', y='PnL', title='30-Day PnL Trend')
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
    with col2:
        st.subheader("🎯 Strategy Performance")
        # Sample strategy performance data
        strategies = ['Spot-Perp', 'Triangular', 'Spot-Spot', 'Stat Arb']
        performance = [45, 30, 15, 10]
        
        fig = px.pie(values=performance, names=strategies, title='PnL by Strategy')
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent Trades Table
    st.subheader("📋 Recent Trades")
    trades_data = {
        'Time': [datetime.now() - timedelta(minutes=i*10) for i in range(5)],
        'Strategy': ['Spot-Perp', 'Triangular', 'Spot-Spot', 'Stat Arb', 'Spot-Perp'],
        'Symbol': ['BTC-USDT', 'ETH-BTC-USDT', 'BTC-USDC', 'ETH-BTC', 'ETH-USDT'],
        'Side': ['Buy/Sell', 'Arb', 'Buy/Sell', 'Pair', 'Buy/Sell'],
        'PnL': [12.5, -3.2, 8.7, 15.3, 6.9]
    }
    trades_df = pd.DataFrame(trades_data)
    st.dataframe(trades_df, use_container_width=True)
    
    # Control Buttons
    st.subheader("🎮 Bot Control")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Start Bot", use_container_width=True):
            result = api_request("/bot/start", method="POST", data={"command": "launcher"})
            if result:
                st.success("Bot started successfully")
                st.rerun()
                
    with col2:
        if st.button("⏹️ Stop Bot", use_container_width=True):
            result = api_request("/bot/stop", method="POST")
            if result:
                st.success("Bot stopped successfully")
                st.rerun()
                
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

# Controllers Page
def controllers_page():
    """Display controllers management page"""
    st.title("⚙️ Controllers Management")
    
    tab1, tab2, tab3 = st.tabs(["Active Controllers", "Create New", "Templates"])
    
    with tab1:
        st.subheader("Active Controllers")
        controllers = api_request("/controllers/list")
        
        if controllers:
            for controller in controllers:
                with st.expander(f"📦 {controller['name']} ({controller['type']})"):
                    st.json(controller['config'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Edit {controller['name']}", key=f"edit_{controller['name']}"):
                            st.session_state.editing = controller['name']
                            
                    with col2:
                        if st.button(f"Delete {controller['name']}", key=f"delete_{controller['name']}"):
                            result = api_request(f"/controllers/delete/{controller['name']}", method="DELETE")
                            if result:
                                st.success(f"Deleted {controller['name']}")
                                st.rerun()
        else:
            st.info("No active controllers found")
            
    with tab2:
        st.subheader("Create New Controller")
        
        controller_type = st.selectbox(
            "Controller Type",
            ["gate_spot_perp_controller", "gate_triangular_controller", 
             "gate_spot_spot_controller", "gate_stat_arb_controller"]
        )
        
        # Dynamic form based on controller type
        if controller_type == "gate_spot_perp_controller":
            with st.form("create_spot_perp"):
                symbols = st.multiselect("Symbols", ["BTC-USDT", "ETH-USDT", "BNB-USDT", "SOL-USDT"])
                min_basis = st.number_input("Min Basis (bps)", value=30, min_value=0)
                position_size = st.slider("Position Size %", 1, 100, 10)
                max_positions = st.number_input("Max Positions", value=3, min_value=1)
                
                if st.form_submit_button("Create Controller"):
                    config = {
                        "controller_name": controller_type,
                        "config": {
                            "controller_name": controller_type,
                            "symbols": symbols,
                            "min_basis_bps": min_basis,
                            "position_size_pct": position_size / 100,
                            "max_open_positions": max_positions
                        }
                    }
                    result = api_request("/controllers/create", method="POST", data=config)
                    if result:
                        st.success("Controller created successfully")
                        st.rerun()
                        
    with tab3:
        st.subheader("Controller Templates")
        templates = api_request("/controllers/templates")
        
        if templates:
            for template in templates:
                with st.expander(f"📄 {template}"):
                    st.markdown(f"""
                    **{template}**
                    
                    Description of the controller strategy and parameters...
                    """)

# Monitoring Page
def monitoring_page():
    """Display monitoring and logs page"""
    st.title("📡 Monitoring")
    
    tab1, tab2, tab3 = st.tabs(["Live Logs", "Metrics", "Alerts"])
    
    with tab1:
        st.subheader("Live Logs")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh (5s)")
        
        # Get logs
        logs = api_request("/logs/tail?lines=50")
        
        if logs:
            # Display logs in a text area
            log_text = "\n".join(logs)
            st.text_area("Log Output", log_text, height=400)
            
        if auto_refresh:
            time.sleep(5)
            st.rerun()
            
    with tab2:
        st.subheader("Performance Metrics")
        
        metrics = api_request("/metrics/summary")
        
        if metrics:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("24h PnL", f"${metrics.get('total_pnl_24h', 0):,.2f}")
                st.metric("24h Trades", metrics.get('total_trades_24h', 0))
                st.metric("Win Rate", f"{metrics.get('win_rate', 0):.1f}%")
                
            with col2:
                st.metric("Active Strategies", metrics.get('active_strategies', 0))
                st.metric("24h Volume", f"${metrics.get('total_volume_24h', 0):,.2f}")
                
    with tab3:
        st.subheader("Alert Settings")
        
        with st.form("alert_settings"):
            st.checkbox("Enable Email Alerts")
            st.checkbox("Enable Telegram Alerts")
            st.number_input("PnL Alert Threshold ($)", value=100)
            st.number_input("Loss Alert Threshold ($)", value=-50)
            
            if st.form_submit_button("Save Settings"):
                st.success("Alert settings saved")

# Settings Page
def settings_page():
    """Display settings page"""
    st.title("⚙️ Settings")
    
    tab1, tab2, tab3 = st.tabs(["Exchange Credentials", "Fee Settings", "Risk Management"])
    
    with tab1:
        st.subheader("Exchange Credentials")
        
        with st.form("add_credentials"):
            exchange = st.selectbox("Exchange", ["gate_io", "gate_io_perpetual"])
            api_key = st.text_input("API Key")
            api_secret = st.text_input("API Secret", type="password")
            api_passphrase = st.text_input("API Passphrase (optional)")
            
            if st.form_submit_button("Add Credentials"):
                creds = {
                    "exchange": exchange,
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "api_passphrase": api_passphrase
                }
                result = api_request("/credentials/add", method="POST", data=creds)
                if result:
                    st.success("Credentials added successfully")
                    
    with tab2:
        st.subheader("Fee Settings")
        
        st.info("Configure your actual trading fees after rebates in conf/conf_fee_overrides.yml")
        
        with st.expander("Current Fee Configuration"):
            st.code("""
gate_io:
  default:
    maker_fee: 0.00025  # 0.025% with 75% rebate
    taker_fee: 0.0005   # 0.05% with 75% rebate

gate_io_perpetual:
  default:
    maker_fee: 0.00005  # 0.005% with 75% rebate
    taker_fee: 0.00015  # 0.015% with 75% rebate
            """)
            
    with tab3:
        st.subheader("Risk Management")
        
        with st.form("risk_settings"):
            st.number_input("Max Total Exposure ($)", value=50000)
            st.number_input("Daily Loss Limit ($)", value=1000)
            st.number_input("Max Positions Per Strategy", value=5)
            st.slider("Max Leverage", 1, 10, 1)
            
            if st.form_submit_button("Save Risk Settings"):
                st.success("Risk settings saved")

# Main App
def main():
    """Main application"""
    if not st.session_state.authenticated:
        login_page()
        return
        
    # Sidebar
    st.sidebar.title("🚀 Gate.io Arbitrage Suite")
    st.sidebar.markdown(f"👤 {st.session_state.username}")
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Controllers", "Monitoring", "Settings"]
    )
    
    # Logout button
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.password = ""
        st.rerun()
        
    # Display selected page
    if page == "Dashboard":
        dashboard_page()
    elif page == "Controllers":
        controllers_page()
    elif page == "Monitoring":
        monitoring_page()
    elif page == "Settings":
        settings_page()

if __name__ == "__main__":
    main()