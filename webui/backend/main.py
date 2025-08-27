from __future__ import annotations

import base64
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import uvicorn
import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

BACKEND_ROOT = Path("/workspace")  # mounted HB root
CONF_CONTROLLERS_DIR = BACKEND_ROOT / "conf" / "controllers"
EXAMPLES_DIR = BACKEND_ROOT / "conf" / "examples"
LOG_PATH = Path(os.environ.get("HUMMINGBOT_LOG_PATH", "/workspace/logs/hummingbot.log"))
HB_API_BASE = os.environ.get("HUMMINGBOT_API_BASE", "").strip()
HB_CLI_BIN = os.environ.get("HUMMINGBOT_CLI_BIN", "").strip()

USERNAME = os.environ.get("WEBUI_USERNAME", "").strip()
PASSWORD = os.environ.get("WEBUI_PASSWORD", "").strip()

app = FastAPI(title="Gate Arb Web Admin")

def basic_auth(request: Request):
    if not USERNAME or not PASSWORD:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    try:
        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
        user, pwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not (user == USERNAME and pwd == PASSWORD):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

@app.get("/status")
def status(_: Any = Depends(basic_auth)):
    return {"ok": True, "hb_api": bool(HB_API_BASE), "log_path": str(LOG_PATH)}

@app.get("/templates")
def list_controller_templates(_: Any = Depends(basic_auth)):
    templates: List[str] = []
    for p in (CONF_CONTROLLERS_DIR / "arbitrage").glob("*.yml"):
        templates.append(str(p.relative_to(BACKEND_ROOT)))
    return {"templates": templates}

@app.get("/fee-overrides")
def get_fee_overrides(_: Any = Depends(basic_auth)):
    path = EXAMPLES_DIR / "conf_fee_overrides.yml"
    if not path.exists():
        raise HTTPException(404, "Fee overrides not found")
    return yaml.safe_load(path.read_text(encoding="utf-8"))

@app.post("/fee-overrides")
def update_fee_overrides(payload: Dict[str, Any], _: Any = Depends(basic_auth)):
    path = EXAMPLES_DIR / "conf_fee_overrides.yml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True}

@app.post("/controllers/save")
def save_controller_config(payload: Dict[str, Any], _: Any = Depends(basic_auth)):
    """
    payload:
      relative_path: conf/controllers/arbitrage/gate_spot_perp_controller.yml
      config: <yaml dict>
    """
    rel = payload.get("relative_path")
    cfg = payload.get("config")
    if not rel or not isinstance(cfg, dict):
        raise HTTPException(400, "Invalid payload")
    out = BACKEND_ROOT / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True, "saved": rel}

@app.post("/start")
def start_bot(payload: Dict[str, Any], _: Any = Depends(basic_auth)):
    """
    payload:
      script: v2_with_controllers.py or scripts/gate_arb_launcher_v2.py
      conf: conf/examples/conf_v2_with_controllers.yml
    """
    script = payload.get("script", "v2_with_controllers.py")
    conf = payload.get("conf", "conf/examples/conf_v2_with_controllers.yml")
    if HB_CLI_BIN:
        cmd = [HB_CLI_BIN, "start", "--script", script, "--conf", conf]
    else:
        # Fallback: attempt to run via python -m (works for wrapper)
        cmd = ["python", "-m", script.replace(".py", ""), "--conf", conf] if script.endswith(".py") else ["python", "-m", script, "--conf", conf]
    try:
        subprocess.Popen(cmd, cwd=BACKEND_ROOT)
    except Exception as e:
        raise HTTPException(500, f"Failed to start bot: {e}")
    return {"ok": True, "cmd": " ".join(cmd)}

@app.post("/stop")
def stop_bot(_: Any = Depends(basic_auth)):
    # If using HB dashboard API, call stop endpoint; else advise manual stop
    if HB_API_BASE:
        try:
            requests.post(f"{HB_API_BASE}/stop", timeout=2)
        except Exception:
            pass
    return {"ok": True}

@app.get("/logs")
def tail_logs(lines: int = 200, _: Any = Depends(basic_auth)):
    if not LOG_PATH.exists():
        return {"log": "[No logs found]"}
    content = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-lines:]
    return {"log": "\n".join(content)}