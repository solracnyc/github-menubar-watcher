import pytest
from unittest.mock import patch, MagicMock
from github_client import GitHubClient, RateLimitError, GitHubAPIError


@pytest.fixture
def client():
    return GitHubClient(token=None)


@pytest.fixture
def authed_client():
    return GitHubClient(token="ghp_test123")


def _mock_response(status_code, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


class TestHeaders:
    def test_base_headers_no_token(self, client):
        h = client._build_headers()
        assert h["Accept"] == "application/vnd.github+json"
        assert h["X-GitHub-Api-Version"] == "2022-11-28"
        assert "Authorization" not in h

    def test_base_headers_with_token(self, authed_client):
        h = authed_client._build_headers()
        assert h["Authorization"] == "Bearer ghp_test123"

    def test_etag_header(self, client):
        h = client._build_headers(etag='"abc123"')
        assert h["If-None-Match"] == '"abc123"'


class TestFetchLatestTag:
    @patch("github_client.requests.get")
    def test_returns_tag_info(self, mock_get, client):
        mock_get.return_value = _mock_response(200, [
            {"name": "v2.3.1", "commit": {"sha": "deadbeef"}}
        ], {"ETag": '"new-etag"'})
        result = client.fetch_latest_tag("cloudflare", "vinext")
        assert result["tag_name"] == "v2.3.1"
        assert result["commit_sha"] == "deadbeef"
        assert result["etag"] == '"new-etag"'

    @patch("github_client.requests.get")
    def test_304_not_modified(self, mock_get, client):
        mock_get.return_value = _mock_response(304)
        result = client.fetch_latest_tag("cloudflare", "vinext", etag='"old"')
        assert result is None

    @patch("github_client.requests.get")
    def test_empty_tags(self, mock_get, client):
        mock_get.return_value = _mock_response(200, [], {"ETag": '"e"'})
        result = client.fetch_latest_tag("x", "y")
        assert result is None


class TestFetchLatestRelease:
    @patch("github_client.requests.get")
    def test_returns_release_info(self, mock_get, client):
        mock_get.return_value = _mock_response(200, {
            "id": 99999, "tag_name": "v1.5.0", "name": "Release 1.5.0"
        }, {"ETag": '"rel-etag"'})
        result = client.fetch_latest_release("soniox", "soniox-js")
        assert result["release_id"] == 99999
        assert result["tag_name"] == "v1.5.0"
        assert result["etag"] == '"rel-etag"'

    @patch("github_client.requests.get")
    def test_304_not_modified(self, mock_get, client):
        mock_get.return_value = _mock_response(304)
        result = client.fetch_latest_release("soniox", "soniox-js", etag='"old"')
        assert result is None


class TestRateLimiting:
    @patch("github_client.requests.get")
    def test_403_raises_rate_limit(self, mock_get, client):
        mock_get.return_value = _mock_response(403, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        })
        with pytest.raises(RateLimitError) as exc_info:
            client.fetch_latest_tag("x", "y")
        assert exc_info.value.reset_timestamp == 1700000000

    @patch("github_client.requests.get")
    def test_429_raises_rate_limit(self, mock_get, client):
        mock_get.return_value = _mock_response(429, headers={
            "Retry-After": "60",
        })
        with pytest.raises(RateLimitError):
            client.fetch_latest_tag("x", "y")

    @patch("github_client.requests.get")
    def test_404_raises_api_error(self, mock_get, client):
        mock_get.return_value = _mock_response(404, {"message": "Not Found"})
        with pytest.raises(GitHubAPIError, match="404"):
            client.fetch_latest_tag("x", "nonexistent")
