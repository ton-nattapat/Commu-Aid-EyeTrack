from pathlib import Path

from commu_aid.config import load_config

ROOT = Path(__file__).resolve().parent.parent


def test_default_config_loads():
    cfg = load_config(ROOT / "config.yaml")
    assert cfg.dwell.dwell_time_s == 3.0
    assert len(cfg.needs) == 11
    assert cfg.needs[0].label == "Thirsty"
    assert cfg.needs[8].label == "Yes" and cfg.needs[9].label == "No"
    assert any(t.action == "alert" for t in cfg.needs)
    assert cfg.language.speak == "th"


def test_save_round_trip_keeps_thai(tmp_path):
    cfg = load_config(ROOT / "config.yaml")
    cfg.dwell.dwell_time_s = 4.2
    cfg.needs[0].thai = "ผมอยากดื่มน้ำครับ"
    out = tmp_path / "config.yaml"
    cfg.save(out)
    again = load_config(out)
    assert again.dwell.dwell_time_s == 4.2
    assert again.needs[0].thai == "ผมอยากดื่มน้ำครับ"
    assert again.calibration.on_startup is True


def test_dwell_time_is_clamped(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("dwell: {dwell_time_s: 9}\n", encoding="utf-8")
    assert load_config(p).dwell.dwell_time_s == 5.0
