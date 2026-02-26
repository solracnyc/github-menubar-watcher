"""GitHub API client with ETag caching and rate limit handling."""

import requests


_BASE_URL = "https://api.github.com"
_TIMEOUT = 30  # seconds


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error {status_code}: {message}")


class RateLimitError(GitHubAPIError):
    def __init__(self, reset_timestamp: int | None = None, retry_after: int | None = None):
        self.reset_timestamp = reset_timestamp
        self.retry_after = retry_after
        super().__init__(429, "Rate limited")


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token

    def _build_headers(self, etag: str | None = None) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _check_rate_limit(self, resp: requests.Response) -> None:
        if resp.status_code in (403, 429):
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if resp.status_code == 429 or (remaining is not None and int(remaining) == 0):
                reset_ts = resp.headers.get("X-RateLimit-Reset")
                retry_after = resp.headers.get("Retry-After")
                raise RateLimitError(
                    reset_timestamp=int(reset_ts) if reset_ts else None,
                    retry_after=int(retry_after) if retry_after else None,
                )

    def _check_error(self, resp: requests.Response) -> None:
        if resp.status_code >= 400:
            msg = "Unknown error"
            if resp.content:
                try:
                    msg = resp.json().get("message", "Unknown error")
                except (ValueError, KeyError):
                    msg = resp.text[:200] or "Unknown error"
            raise GitHubAPIError(resp.status_code, msg)

    def fetch_latest_tag(
        self, owner: str, repo: str, etag: str | None = None
    ) -> dict | None:
        url = f"{_BASE_URL}/repos/{owner}/{repo}/tags"
        resp = requests.get(
            url, headers=self._build_headers(etag), params={"per_page": 1}, timeout=_TIMEOUT,
        )

        if resp.status_code == 304:
            return None

        self._check_rate_limit(resp)
        self._check_error(resp)

        tags = resp.json()
        if not tags:
            return None

        return {
            "tag_name": tags[0]["name"],
            "commit_sha": tags[0]["commit"]["sha"],
            "etag": resp.headers.get("ETag"),
        }

    def fetch_latest_release(
        self, owner: str, repo: str, etag: str | None = None
    ) -> dict | None:
        url = f"{_BASE_URL}/repos/{owner}/{repo}/releases/latest"
        resp = requests.get(url, headers=self._build_headers(etag), timeout=_TIMEOUT)

        if resp.status_code == 304:
            return None

        self._check_rate_limit(resp)
        self._check_error(resp)

        data = resp.json()
        return {
            "release_id": data["id"],
            "tag_name": data["tag_name"],
            "release_name": data.get("name", ""),
            "etag": resp.headers.get("ETag"),
        }
