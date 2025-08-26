#!/usr/bin/env python3
"""
Streamlit Frontend for Gate.io Arbitrage Web Admin UI
Provides user-friendly interface for managing arbitrage bots
"""

import streamlit as st
import requests
import json
import yaml
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import time

# Page configuration
st.set_page_config(
    page_title="Gate.io Arbitrage Admin",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration
API_BASE_URL = "http://localhost:8000"
REFRESH_INTERVAL = 5  # seconds

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None

# Helper functions
def make_api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated API request"""
    if not st.session_state.authenticated:
        return {"error": "Not authenticated"}
    
    url = f"{API_BASE_URL}{endpoint}"
    auth = (st.session_state.username, st.session_state.password)
    
    try:
        if method == "GET":
            response = requests.get(url, auth=auth)
        elif method == "POST":
            response = requests.post(url, auth=auth, json=data)
        elif method == "PUT":
            response = requests.put(url, auth=auth, json=data)
        elif method == "DELETE":
            response = requests.delete(url, auth=auth)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API Error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user with API"""
    auth = (username, password)
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", auth=auth)
        if response.status_code == 200:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.password = password
            return True
    except:
        pass
    return False

def format_currency(amount: float, currency: str = "USDT") -> str:
    """Format currency amount"""
    return f"{amount:,.6f} {currency}"

def format_percentage(value: float) -> str:
    """Format percentage value"""
    return f"{value:.2%}"

# Authentication
def show_login():
    """Show login form"""
    st.title("🤖 Gate.io Arbitrage Admin")
    st.markdown("### Please login to continue")
    
    with st.form("login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password", value="password123")
        submit = st.form_submit_button("Login")
        
        if submit:
            if authenticate_user(username, password):
                st.success("Login successful!")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")

# Main application
def show_main_app():
    """Show main application interface"""
    
    # Sidebar
    with st.sidebar:
        st.title("🤖 Gate.io Arbitrage")
        st.markdown(f"**User:** {st.session_state.username}")
        
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.experimental_rerun()
        
        st.markdown("---")
        
        # Navigation
        page = st.selectbox(
            "Navigation",
            [
                "Dashboard",
                "Bot Management", 
                "Controllers",
                "Credentials",
                "Fee Configuration",
                "Logs",
                "Settings"
            ]
        )
    
    # Main content
    if page == "Dashboard":
        show_dashboard()
    elif page == "Bot Management":
        show_bot_management()
    elif page == "Controllers":
        show_controllers()
    elif page == "Credentials":
        show_credentials()
    elif page == "Fee Configuration":
        show_fee_configuration()
    elif page == "Logs":
        show_logs()
    elif page == "Settings":
        show_settings()

def show_dashboard():
    """Show main dashboard"""
    st.title("📊 Dashboard")
    
    # Get system status
    status_data = make_api_request("/api/bots/status")
    
    if "error" in status_data:
        st.error(f"Error loading dashboard: {status_data['error']}")
        return
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        bot_count = len(status_data.get("bots", []))
        st.metric("Active Bots", bot_count)
    
    with col2:
        total_pnl = sum(bot.get("pnl", 0) for bot in status_data.get("bots", []))
        st.metric("Total PnL", format_currency(total_pnl))
    
    with col3:
        total_trades = sum(bot.get("trades", 0) for bot in status_data.get("bots", []))
        st.metric("Total Trades", total_trades)
    
    with col4:
        # Calculate uptime average
        uptimes = [bot.get("uptime", 0) for bot in status_data.get("bots", []) if bot.get("uptime")]
        avg_uptime = sum(uptimes) / len(uptimes) if uptimes else 0
        st.metric("Avg Uptime", f"{avg_uptime:.1f}h")
    
    # System health
    st.markdown("### System Health")
    health_data = status_data.get("system_health", {})
    
    col1, col2, col3 = st.columns(3)
    with col1:
        cpu_usage = health_data.get("cpu_usage", 0)
        st.metric("CPU Usage", format_percentage(cpu_usage))
    with col2:
        memory_usage = health_data.get("memory_usage", 0)
        st.metric("Memory Usage", format_percentage(memory_usage))
    with col3:
        disk_space = health_data.get("disk_space", 0)
        st.metric("Disk Usage", format_percentage(disk_space))
    
    # Balances
    st.markdown("### Account Balances")
    balances = status_data.get("balances", {})
    
    if balances:
        balance_df = pd.DataFrame([
            {"Currency": currency, "Balance": balance}
            for currency, balance in balances.items()
        ])
        st.dataframe(balance_df, use_container_width=True)
    else:
        st.info("No balance data available")
    
    # Running bots
    st.markdown("### Running Bots")
    bots = status_data.get("bots", [])
    
    if bots:
        bot_df = pd.DataFrame(bots)
        st.dataframe(bot_df, use_container_width=True)
    else:
        st.info("No bots currently running")
    
    # Auto-refresh
    if st.button("🔄 Refresh"):
        st.experimental_rerun()

def show_bot_management():
    """Show bot management interface"""
    st.title("🤖 Bot Management")
    
    # Bot controls
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Start Bot")
        with st.form("start_bot_form"):
            script_name = st.selectbox(
                "Script",
                ["gate_arb_launcher_v2.py", "gate_arb_legacy.py"]
            )
            config_name = st.text_input("Config Name (optional)", "conf_v2_with_controllers.yml")
            
            if st.form_submit_button("Start Bot"):
                data = {"config_name": config_name} if config_name else None
                result = make_api_request(f"/api/bots/start/{script_name}", "POST", data)
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(result["message"])
    
    with col2:
        st.markdown("### Stop Bot")
        with st.form("stop_bot_form"):
            bot_name = st.text_input("Bot Name/PID")
            
            if st.form_submit_button("Stop Bot"):
                result = make_api_request(f"/api/bots/stop/{bot_name}", "POST")
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(result["message"])
    
    # Bot status
    st.markdown("### Bot Status")
    status_data = make_api_request("/api/bots/status")
    
    if "error" not in status_data:
        bots = status_data.get("bots", [])
        if bots:
            st.dataframe(pd.DataFrame(bots), use_container_width=True)
        else:
            st.info("No bots currently running")

def show_controllers():
    """Show controller management interface"""
    st.title("⚙️ Controllers")
    
    # Get controllers
    controllers = make_api_request("/api/controllers")
    
    if "error" in controllers:
        st.error(f"Error loading controllers: {controllers['error']}")
        return
    
    # Controller list
    st.markdown("### Active Controllers")
    
    if controllers:
        controller_df = pd.DataFrame([
            {
                "Name": ctrl["name"],
                "Type": ctrl["type"],
                "Enabled": ctrl["enabled"]
            }
            for ctrl in controllers
        ])
        st.dataframe(controller_df, use_container_width=True)
    else:
        st.info("No controllers configured")
    
    # Create new controller
    st.markdown("### Create New Controller")
    
    # Get templates
    templates = make_api_request("/api/templates/controllers")
    
    if "error" not in templates:
        with st.form("create_controller_form"):
            controller_name = st.text_input("Controller Name")
            controller_type = st.selectbox(
                "Controller Type",
                list(templates.keys())
            )
            
            if controller_type:
                template = templates[controller_type]
                st.markdown("#### Configuration")
                
                # Create form fields based on template
                config = {}
                for key, value in template.items():
                    if key == "controller_type":
                        continue
                    elif isinstance(value, list):
                        config[key] = st.multiselect(
                            key.replace("_", " ").title(),
                            value,
                            default=value
                        )
                    elif isinstance(value, bool):
                        config[key] = st.checkbox(
                            key.replace("_", " ").title(),
                            value=value
                        )
                    elif isinstance(value, (int, float)):
                        config[key] = st.number_input(
                            key.replace("_", " ").title(),
                            value=value
                        )
                    elif isinstance(value, str):
                        config[key] = st.text_input(
                            key.replace("_", " ").title(),
                            value=value
                        )
                    else:
                        # For nested dicts, show as JSON editor
                        config[key] = st.text_area(
                            key.replace("_", " ").title(),
                            value=json.dumps(value, indent=2),
                            help="JSON format"
                        )
            
            if st.form_submit_button("Create Controller"):
                if controller_name:
                    data = {
                        "controller_name": controller_name,
                        "controller_type": template["controller_type"],
                        "config": config,
                        "enabled": True
                    }
                    
                    result = make_api_request("/api/controllers", "POST", data)
                    
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(result["message"])
                        st.experimental_rerun()
                else:
                    st.error("Please enter a controller name")

def show_credentials():
    """Show credentials management interface"""
    st.title("🔐 Exchange Credentials")
    
    # Current credentials
    credentials = make_api_request("/api/credentials")
    
    st.markdown("### Configured Exchanges")
    if "error" not in credentials and credentials:
        for exchange in credentials:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"✅ {exchange}")
            with col2:
                if st.button(f"Remove", key=f"remove_{exchange}"):
                    result = make_api_request(f"/api/credentials/{exchange}", "DELETE")
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(result["message"])
                        st.experimental_rerun()
    else:
        st.info("No exchanges configured")
    
    # Add new credentials
    st.markdown("### Add New Exchange")
    
    with st.form("add_credentials_form"):
        exchange = st.selectbox(
            "Exchange",
            ["gate_io", "gate_io_perpetual"]
        )
        api_key = st.text_input("API Key", type="password")
        secret_key = st.text_input("Secret Key", type="password")
        passphrase = st.text_input("Passphrase (if required)", type="password")
        testnet = st.checkbox("Use Testnet")
        
        if st.form_submit_button("Add Credentials"):
            if api_key and secret_key:
                data = {
                    "exchange": exchange,
                    "api_key": api_key,
                    "secret_key": secret_key,
                    "passphrase": passphrase if passphrase else None,
                    "testnet": testnet
                }
                
                result = make_api_request("/api/credentials", "POST", data)
                
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(result["message"])
                    st.experimental_rerun()
            else:
                st.error("Please enter both API key and secret key")

def show_fee_configuration():
    """Show fee configuration interface"""
    st.title("💰 Fee Configuration")
    
    # Get current fee config
    fee_config = make_api_request("/api/fees")
    
    if "error" in fee_config:
        st.error(f"Error loading fee configuration: {fee_config['error']}")
        return
    
    st.markdown("### Current Fee Configuration")
    st.info("Update these values to match your actual post-rebate fees from Gate.io")
    
    # Fee overrides
    fee_overrides = fee_config.get("fee_overrides", {})
    
    updated_config = {"fee_overrides": {}}
    
    for exchange, fees in fee_overrides.items():
        st.markdown(f"#### {exchange.replace('_', ' ').title()}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            maker_fee = st.number_input(
                f"Maker Fee ({exchange})",
                value=float(fees.get("maker", 0.0005)),
                format="%.6f",
                step=0.000001,
                key=f"{exchange}_maker"
            )
        
        with col2:
            taker_fee = st.number_input(
                f"Taker Fee ({exchange})",
                value=float(fees.get("taker", 0.0005)),
                format="%.6f",
                step=0.000001,
                key=f"{exchange}_taker"
            )
        
        updated_config["fee_overrides"][exchange] = {
            "maker": maker_fee,
            "taker": taker_fee
        }
    
    # Rebate settings
    rebate_settings = fee_config.get("rebate_settings", {})
    
    st.markdown("#### Rebate Settings")
    default_rebate = st.slider(
        "Default Rebate Ratio",
        min_value=0.0,
        max_value=1.0,
        value=float(rebate_settings.get("default_rebate_ratio", 0.75)),
        step=0.01,
        format="%.2f"
    )
    
    updated_config["rebate_settings"] = {
        "default_rebate_ratio": default_rebate,
        "exchange_rebates": rebate_settings.get("exchange_rebates", {})
    }
    
    # Save configuration
    if st.button("Save Fee Configuration"):
        result = make_api_request("/api/fees", "PUT", updated_config)
        
        if "error" in result:
            st.error(result["error"])
        else:
            st.success(result["message"])

def show_logs():
    """Show system logs"""
    st.title("📝 System Logs")
    
    # Log controls
    col1, col2 = st.columns([1, 3])
    
    with col1:
        lines = st.number_input("Number of lines", min_value=10, max_value=1000, value=100)
        auto_refresh = st.checkbox("Auto-refresh (5s)")
    
    with col2:
        if st.button("Refresh Logs"):
            st.experimental_rerun()
    
    # Get logs
    logs_data = make_api_request(f"/api/logs?lines={lines}")
    
    if "error" in logs_data:
        st.error(f"Error loading logs: {logs_data['error']}")
        return
    
    logs = logs_data.get("logs", [])
    
    if logs:
        # Display logs in a code block
        log_text = "\n".join(logs)
        st.code(log_text, language="text")
    else:
        st.info("No logs available")
    
    # Auto-refresh
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.experimental_rerun()

def show_settings():
    """Show application settings"""
    st.title("⚙️ Settings")
    
    st.markdown("### Application Settings")
    
    # API settings
    st.markdown("#### API Configuration")
    api_url = st.text_input("API Base URL", value=API_BASE_URL)
    
    # Display settings
    st.markdown("#### Display Settings")
    refresh_interval = st.slider("Auto-refresh interval (seconds)", 1, 30, REFRESH_INTERVAL)
    
    # Theme settings
    st.markdown("#### Theme Settings")
    st.info("Theme settings are controlled by Streamlit's built-in theme system")
    
    # Save settings (in a real app, these would be persisted)
    if st.button("Save Settings"):
        st.success("Settings saved!")

# Main application logic
def main():
    """Main application entry point"""
    if not st.session_state.authenticated:
        show_login()
    else:
        show_main_app()

if __name__ == "__main__":
    main()