import json
import pytest
from state_store import StateStore


def test_load_empty_state(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.data == {}


def test_load_existing_state(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"cloudflare/vinext": {"last_tag_name": "v1.0"}}))
    store = StateStore(str(p))
    assert store.data["cloudflare/vinext"]["last_tag_name"] == "v1.0"


def test_get_repo_state_missing(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get("cloudflare/vinext") is None


def test_update_and_save(tmp_path):
    p = tmp_path / "state.json"
    store = StateStore(str(p))
    store.update("cloudflare/vinext", {
        "last_tag_name": "v2.0",
        "last_commit_sha": "abc123",
        "etag": '"etag-value"',
    })
    assert store.get("cloudflare/vinext")["last_tag_name"] == "v2.0"
    # Verify persisted to disk
    reloaded = json.loads(p.read_text())
    assert reloaded["cloudflare/vinext"]["last_tag_name"] == "v2.0"


def test_is_first_run_for_repo(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.is_first_run("cloudflare/vinext") is True
    store.update("cloudflare/vinext", {"last_tag_name": "v1.0"})
    assert store.is_first_run("cloudflare/vinext") is False


def test_get_etag(tmp_path):
    store = StateStore(str(tmp_path / "state.json"))
    assert store.get_etag("cloudflare/vinext") is None
    store.update("cloudflare/vinext", {"etag": '"abc"'})
    assert store.get_etag("cloudflare/vinext") == '"abc"'
