"""Unit tests for GitHub REST API client integration."""

from io import BytesIO
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from app.integrations.github import (
    GitHubAuthError,
    GitHubClient,
    GitHubError,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    parse_and_validate_github_url,
)


class TestGitHubClient(unittest.TestCase):
    """Test suite for GitHub REST API client."""

    def test_url_validation_valid(self):
        """Verify valid GitHub URLs parse correctly."""
        owner, repo = parse_and_validate_github_url("https://github.com/fastapi/fastapi")
        self.assertEqual(owner, "fastapi")
        self.assertEqual(repo, "fastapi")

        owner, repo = parse_and_validate_github_url("https://github.com/torvalds/linux.git")
        self.assertEqual(owner, "torvalds")
        self.assertEqual(repo, "linux")

        owner, repo = parse_and_validate_github_url("https://github.com/org-name/repo.sub-name")
        self.assertEqual(owner, "org-name")
        self.assertEqual(repo, "repo.sub-name")

    def test_url_validation_invalid(self):
        """Verify invalid, non-GitHub, or malicious URLs are rejected."""
        invalid_urls = [
            "",
            "http://github.com/owner/repo",  # Insecure HTTP
            "https://gitlab.com/owner/repo", # Wrong domain
            "https://github.com/owner",      # Missing repo
            "https://github.com/owner/repo/extra", # Extra path segments
            "https://github.com/../evil/repo",     # Path traversal
            "https://github.com/owner/repo;rm -rf", # Command injection attempt
            "ftp://github.com/owner/repo",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_and_validate_github_url(url)

    @patch("urllib.request.urlopen")
    def test_get_repository_success(self, mock_urlopen):
        """Verify repository metadata extraction."""
        payload = {
            "id": 12345678,
            "name": "sample-repo",
            "full_name": "owner/sample-repo",
            "description": "A sample repository",
            "default_branch": "main",
            "html_url": "https://github.com/owner/sample-repo",
            "private": False,
            "stargazers_count": 42,
            "forks_count": 5,
            "open_issues_count": 2,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.info.return_value = {"content-type": "application/json"}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GitHubClient(token="mock_token")
        meta = client.get_repository("owner", "sample-repo")

        self.assertEqual(meta["name"], "sample-repo")
        self.assertEqual(meta["full_name"], "owner/sample-repo")
        self.assertEqual(meta["default_branch"], "main")
        self.assertEqual(meta["stars_count"], 42)

    @patch("urllib.request.urlopen")
    def test_authentication_error_401(self, mock_urlopen):
        """Verify HTTP 401 raises GitHubAuthError."""
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b'{"message": "Bad credentials"}'),
        )
        mock_urlopen.side_effect = http_err

        client = GitHubClient(token="invalid_token")
        with self.assertRaises(GitHubAuthError):
            client.get_repository("owner", "repo")

    @patch("urllib.request.urlopen")
    def test_rate_limit_error_403(self, mock_urlopen):
        """Verify rate-limit response raises GitHubRateLimitError with reset timestamp."""
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo",
            code=403,
            msg="rate limit exceeded",
            hdrs={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "1731320000"},
            fp=BytesIO(b'{"message": "API rate limit exceeded"}'),
        )
        mock_urlopen.side_effect = http_err

        client = GitHubClient()
        with self.assertRaises(GitHubRateLimitError) as cm:
            client.get_repository("owner", "repo")
        self.assertEqual(cm.exception.reset_timestamp, 1731320000)

    @patch("urllib.request.urlopen")
    def test_not_found_error_404(self, mock_urlopen):
        """Verify HTTP 404 raises GitHubNotFoundError."""
        http_err = urllib.error.HTTPError(
            url="https://api.github.com/repos/owner/repo",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(b'{"message": "Not Found"}'),
        )
        mock_urlopen.side_effect = http_err

        client = GitHubClient()
        with self.assertRaises(GitHubNotFoundError):
            client.get_repository("owner", "repo")

    @patch("urllib.request.urlopen")
    def test_issues_filtering_out_pull_requests(self, mock_urlopen):
        """Verify GitHub issues endpoint ignores pull request items."""
        raw_items = [
            {
                "number": 1,
                "title": "Legitimate Bug Issue",
                "body": "Issue description",
                "state": "open",
                "user": {"login": "alice"},
                "labels": [{"name": "bug"}],
                "html_url": "https://github.com/owner/repo/issues/1",
            },
            {
                "number": 2,
                "title": "Pull Request disguised as Issue",
                "body": "PR description",
                "state": "open",
                "pull_request": {"url": "https://api.github.com/repos/owner/repo/pulls/2"},
                "user": {"login": "bob"},
                "html_url": "https://github.com/owner/repo/pull/2",
            },
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(raw_items).encode("utf-8")
        mock_resp.info.return_value = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GitHubClient()
        issues = client.get_issues("owner", "repo")

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["number"], 1)
        self.assertEqual(issues[0]["title"], "Legitimate Bug Issue")


if __name__ == "__main__":
    unittest.main()
