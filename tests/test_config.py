import json

import flow.config as config_mod
from flow.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.model_size == "base.en"
    assert cfg.formatter == "none"


def test_load_ignores_unknown_keys(tmp_path, monkeypatch):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"model_size": "small.en", "bogus_key": 1}))
    monkeypatch.setattr(config_mod, "CONFIG_PATH", p)
    cfg = Config.load()
    assert cfg.model_size == "small.en"


def test_load_creates_default_file(tmp_path, monkeypatch):
    p = tmp_path / "cfg.json"
    monkeypatch.setattr(config_mod, "CONFIG_PATH", p)
    Config.load()
    assert p.exists()
