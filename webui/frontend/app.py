import base64
import os
from pathlib import Path

import requests
import streamlit as st
import yaml

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
USER = os.environ.get("WEBUI_USERNAME", "")
PASS = os.environ.get("WEBUI_PASSWORD", "")

def auth_header() -> dict:
    if USER and PASS:
        token = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return {}

st.set_page_config(page_title="Gate Arb Admin", layout="wide")
st.title("Gate Arbitrage Suite - Web Admin")

tabs = st.tabs(["Status", "Fee Overrides", "Controller Templates", "Start/Stop", "Logs"])

with tabs[0]:
    if st.button("Refresh Status"):
        r = requests.get(f"{BACKEND_BASE_URL}/status", headers=auth_header(), timeout=5)
        st.json(r.json())

with tabs[1]:
    st.subheader("Global Fee Overrides")
    if st.button("Load"):
        r = requests.get(f"{BACKEND_BASE_URL}/fee-overrides", headers=auth_header(), timeout=5)
        st.session_state["fee"] = r.json()
    fee = st.session_state.get("fee", {"rebate_ratio": 0.75, "connectors": {}})
    st.code(yaml.safe_dump(fee, sort_keys=False, allow_unicode=True))
    new_text = st.text_area("Edit YAML", value=yaml.safe_dump(fee, sort_keys=False, allow_unicode=True), height=300)
    if st.button("Save"):
        try:
            payload = yaml.safe_load(new_text) or {}
            r = requests.post(f"{BACKEND_BASE_URL}/fee-overrides", json=payload, headers=auth_header(), timeout=5)
            st.success("Saved fee overrides.")
        except Exception as e:
            st.error(f"Invalid YAML: {e}")

with tabs[2]:
    st.subheader("Controller Templates")
    r = requests.get(f"{BACKEND_BASE_URL}/templates", headers=auth_header(), timeout=5)
    templates = r.json().get("templates", [])
    st.write("Available templates:")
    st.write(templates)
    if templates:
        choice = st.selectbox("Choose template to load", templates)
        if st.button("Load Template"):
            path = Path(choice)
            content = Path("/workspace") / path
            try:
                txt = content.read_text(encoding="utf-8")
                st.session_state["controller_yaml"] = txt
                st.code(txt, language="yaml")
            except Exception as e:
                st.error(f"Failed: {e}")
    st.markdown("Save edited config:")
    rel_path = st.text_input("Relative Path", value="conf/controllers/arbitrage/custom_controller.yml")
    yaml_text = st.text_area("YAML Content", value=st.session_state.get("controller_yaml", ""), height=300)
    if st.button("Save Controller Config"):
        try:
            cfg = yaml.safe_load(yaml_text) or {}
            r = requests.post(f"{BACKEND_BASE_URL}/controllers/save",
                              json={"relative_path": rel_path, "config": cfg},
                              headers=auth_header(), timeout=5)
            st.success(f"Saved: {rel_path}")
        except Exception as e:
            st.error(f"Invalid YAML: {e}")

with tabs[3]:
    st.subheader("Start/Stop Bot")
    script = st.text_input("Script", value="v2_with_controllers.py")
    conf = st.text_input("Conf", value="conf/examples/conf_v2_with_controllers.yml")
    if st.button("Start"):
        r = requests.post(f"{BACKEND_BASE_URL}/start",
                          json={"script": script, "conf": conf},
                          headers=auth_header(), timeout=10)
        st.json(r.json())
    if st.button("Stop"):
        r = requests.post(f"{BACKEND_BASE_URL}/stop", headers=auth_header(), timeout=5)
        st.json(r.json())

with tabs[4]:
    st.subheader("Live Logs")
    lines = st.number_input("Tail Lines", min_value=50, max_value=5000, value=200, step=50)
    if st.button("Tail"):
        r = requests.get(f"{BACKEND_BASE_URL}/logs", params={"lines": lines}, headers=auth_header(), timeout=5)
        st.text(r.json().get("log", ""))