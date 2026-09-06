import json

import flow.config as config_mod
from flow.config import Config


def test_defaults():
    cfg = Config()
    assert cfg.model_size == "small.en"
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


def test_load_upgrades_the_retired_multilingual_model(tmp_path, monkeypatch):
    """First-run configs pinned v3 without the user choosing it."""
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"parakeet_model": "mlx-community/parakeet-tdt-0.6b-v3"}))
    monkeypatch.setattr(config_mod, "CONFIG_PATH", p)
    cfg = Config.load()
    assert cfg.parakeet_model == Config.parakeet_model
    assert json.loads(p.read_text())["parakeet_model"] == Config.parakeet_model


def test_load_keeps_v3_for_a_non_latin_language(tmp_path, monkeypatch):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"parakeet_model": "mlx-community/parakeet-tdt-0.6b-v3", "language": "ru"}))
    monkeypatch.setattr(config_mod, "CONFIG_PATH", p)
    assert Config.load().parakeet_model.endswith("-v3")
