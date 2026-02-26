"""Load and validate config.json."""

import json
import os


class ConfigError(Exception):
    pass


_VALID_WATCH_TYPES = {"tags", "releases"}
_REQUIRED_REPO_KEYS = {"owner", "repo", "watch", "label"}


def load_config(path: str) -> dict:
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {e}") from e

    if "repos" not in data or not isinstance(data["repos"], list):
        raise ConfigError("Config must contain a 'repos' list")

    data.setdefault("check_interval_minutes", 60)

    for i, repo in enumerate(data["repos"]):
        missing = _REQUIRED_REPO_KEYS - set(repo.keys())
        if missing:
            raise ConfigError(f"Repo #{i} missing keys: {missing}")
        if repo["watch"] not in _VALID_WATCH_TYPES:
            raise ConfigError(
                f"Repo #{i} has invalid watch type '{repo['watch']}'. "
                f"Must be one of: {_VALID_WATCH_TYPES}"
            )

    return data
