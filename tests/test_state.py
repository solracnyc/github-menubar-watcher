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


def test_atomic_write_no_temp_files_left(tmp_path):
    """Atomic write should not leave .tmp files on success."""
    p = tmp_path / "state.json"
    store = StateStore(str(p))
    store.update("test/repo", {"version": "v1.0"})
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == []
    assert p.exists()


def test_state_survives_reload(tmp_path):
    """Data written atomically should be loadable."""
    p = tmp_path / "state.json"
    store = StateStore(str(p))
    store.update("test/repo", {"version": "v1.0", "etag": '"e"'})
    store2 = StateStore(str(p))
    assert store2.get("test/repo")["version"] == "v1.0"
    assert store2.get_etag("test/repo") == '"e"'


def test_corrupted_json_loads_as_empty(tmp_path):
    """Corrupted state.json should result in empty state, not a crash."""
    p = tmp_path / "state.json"
    p.write_text("{this is not valid json!!!")
    store = StateStore(str(p))
    assert store.data == {}
    assert store.corruption_warning is not None
    assert "JSONDecodeError" in store.corruption_warning


def test_corrupted_file_is_renamed(tmp_path):
    """Corrupted file should be renamed for forensics."""
    p = tmp_path / "state.json"
    p.write_text("corrupt data")
    store = StateStore(str(p))
    assert not p.exists(), "Original corrupt file should have been renamed"
    corrupt_files = list(tmp_path.glob("state.json.corrupt-*"))
    assert len(corrupt_files) == 1
    assert corrupt_files[0].read_text() == "corrupt data"
    assert store.data == {}


def test_no_corruption_warning_on_valid_state(tmp_path):
    """Valid state.json should not trigger corruption warning."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"test/repo": {"version": "v1.0"}}))
    store = StateStore(str(p))
    assert store.corruption_warning is None
    assert store.data["test/repo"]["version"] == "v1.0"
