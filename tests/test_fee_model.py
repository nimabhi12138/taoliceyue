from decimal import Decimal

from controllers.arbitrage.common import FeeOverrides

def test_fee_overrides_post_rebate():
    cfg = {
        "rebate_ratio": 0.75,
        "connectors": {
            "gate_io": {
                "spot": {
                    "maker_bps_post_rebate": 0.025,
                    "taker_bps_post_rebate": 0.05,
                }
            },
            "gate_io_perpetual": {
                "perpetual": {
                    "maker_bps_post_rebate": 0.005,
                    "taker_bps_post_rebate": 0.04,
                }
            },
        }
    }
    import yaml, tempfile, os
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        yaml.safe_dump(cfg, f)
        path = f.name

    fo = FeeOverrides.from_yaml(path)
    assert fo.eff_maker_bps("gate_io", "spot") == Decimal("0.0250")
    assert fo.eff_taker_bps("gate_io", "spot") == Decimal("0.0500")
    assert fo.eff_maker_bps("gate_io_perpetual", "perpetual") == Decimal("0.0050")
    assert fo.eff_taker_bps("gate_io_perpetual", "perpetual") == Decimal("0.0400")


def test_fee_overrides_raw_with_rebate():
    cfg = {
        "rebate_ratio": 0.75,
        "connectors": {
            "gate_io": {"spot": {"maker_bps": 10.0, "taker_bps": 20.0}}
        }
    }
    import yaml, tempfile
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        yaml.safe_dump(cfg, f)
        path = f.name

    fo = FeeOverrides.from_yaml(path)
    # 10 bps * 0.25 = 2.5 bps
    assert fo.eff_maker_bps("gate_io", "spot") == Decimal("2.5000")
    assert fo.eff_taker_bps("gate_io", "spot") == Decimal("5.0000")