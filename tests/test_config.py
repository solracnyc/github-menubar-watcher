import json
import os
import pytest
from config_loader import load_config, ConfigError


def test_load_valid_config(tmp_path):
    cfg = {
        "check_interval_minutes": 60,
        "repos": [
            {"owner": "cloudflare", "repo": "vinext", "watch": "tags", "label": "Vinext"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["check_interval_minutes"] == 60
    assert len(result["repos"]) == 1
    assert result["repos"][0]["owner"] == "cloudflare"


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "nonexistent.json"))


def test_load_config_invalid_json(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("not json{{{")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(str(p))


def test_load_config_missing_repos(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"check_interval_minutes": 60}))
    with pytest.raises(ConfigError, match="repos"):
        load_config(str(p))


def test_load_config_invalid_watch_type(tmp_path):
    cfg = {
        "check_interval_minutes": 60,
        "repos": [
            {"owner": "x", "repo": "y", "watch": "commits", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="watch"):
        load_config(str(p))


def test_load_config_defaults_interval(tmp_path):
    cfg = {
        "repos": [
            {"owner": "x", "repo": "y", "watch": "tags", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    result = load_config(str(p))
    assert result["check_interval_minutes"] == 60


def test_load_config_rejects_string_interval(tmp_path):
    cfg = {
        "check_interval_minutes": "sixty",
        "repos": [
            {"owner": "x", "repo": "y", "watch": "tags", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="check_interval_minutes must be a number"):
        load_config(str(p))


def test_load_config_rejects_zero_interval(tmp_path):
    cfg = {
        "check_interval_minutes": 0,
        "repos": [
            {"owner": "x", "repo": "y", "watch": "tags", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="check_interval_minutes must be a number"):
        load_config(str(p))


def test_load_config_rejects_negative_interval(tmp_path):
    cfg = {
        "check_interval_minutes": -5,
        "repos": [
            {"owner": "x", "repo": "y", "watch": "tags", "label": "Z"}
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ConfigError, match="check_interval_minutes must be a number"):
        load_config(str(p))
