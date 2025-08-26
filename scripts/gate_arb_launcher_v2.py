from __future__ import annotations

import importlib
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Minimal shim to run without HB if needed.
# In production, prefer Hummingbot's official v2_with_controllers.py loader.
# This wrapper attempts to import it; if missing, uses a lightweight dispatcher.

def load_yaml(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def try_import_official_loader() -> Optional[Any]:
    try:
        return importlib.import_module("v2_with_controllers")
    except Exception:
        return None

def build_controller(module_path: str, class_name: str, config_path: str):
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls.from_yaml(config_path)

def lightweight_dispatcher(conf_path: str) -> None:
    conf = load_yaml(conf_path)
    controllers_cfgs = conf.get("controllers", [])
    interval = Decimal(str(conf.get("tick_interval_seconds", 1)))
    if not controllers_cfgs:
        print("No controllers specified in config.")
        return

    controllers = []
    for c in controllers_cfgs:
        module_path = c["module"]
        class_name = c["class"]
        config_path = c["config_path"]
        controller = build_controller(module_path, class_name, config_path)
        controller.initialize()
        controllers.append(controller)

    print("Lightweight dispatcher started. Emitting actions (dry-run)...")
    try:
        while True:
            for controller in controllers:
                actions = controller.on_tick()
                if actions:
                    # In real HB loader, these actions would be sent to executors.
                    for a in actions:
                        print(f"[ACTION] {a}")
            time.sleep(float(interval))
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        for controller in controllers:
            controller.shutdown()

def main():
    # Hummingbot passes --conf <file>. We accept env or arg as well.
    conf_path = None
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--conf" and i + 1 < len(argv):
            conf_path = argv[i + 1]
            break
    if conf_path is None:
        # Default example path
        conf_path = "conf/examples/conf_v2_with_controllers.yml"

    # Try official loader
    official = try_import_official_loader()
    if official is not None:
        # Defer to official loader by re-exec
        os.execvp(sys.executable, [sys.executable, "-m", "v2_with_controllers", "--conf", conf_path])

    # Fallback lightweight dispatcher
    lightweight_dispatcher(conf_path)

if __name__ == "__main__":
    main()