from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

try:
    # Hummingbot 2.x ScriptStrategyBase (import path may vary by version)
    from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
except Exception:
    class ScriptStrategyBase:  # shim for documentation/demo only
        def __init__(self, *args, **kwargs):
            pass
        def log(self, *args, **kwargs):
            print(*args)

class GateArbLegacy(ScriptStrategyBase):
    """
    Minimal legacy demo for compatibility. Not used in production.
    """
    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__()
        self.config = config or {}

    def on_tick(self):
        # Example: read simple spread targets from config and log status
        self.log("GateArbLegacy running. This is a demo; use v2 controllers for real trading.")

def main():
    bot = GateArbLegacy()
    # HB will call on_tick internally. Here for completeness only.

if __name__ == "__main__":
    main()