"""GitHub REST API Client Integration.

Provides authenticated and bounded ingestion of repository metadata, commits,
issues, pull requests, and reviews using Python standard-library urllib.request.
"""

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings

logger = logging.getLogger("relaypoint.github")

GITHUB_API_BASE = "https://api.github.com"
GITHUB_URL_REGEX = re.compile(
    r"^https:\/\/github\.com\/([a-zA-Z0-9_\-\.]+)\/([a-zA-Z0-9_\-\.]+?)(?:\.git)?\/?$"
)


class GitHubError(Exception):
    """Base exception for GitHub integration operations."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GitHubAuthError(GitHubError):
    """Raised on authentication failures (HTTP 401)."""
    pass


class GitHubForbiddenError(GitHubError):
    """Raised on forbidden requests (HTTP 403)."""
    pass


class GitHubRateLimitError(GitHubError):
    """Raised when GitHub API rate limit is exceeded (HTTP 403 / 429)."""
    def __init__(self, message: str, reset_timestamp: Optional[int] = None):
        super().__init__(message, status_code=403)
        self.reset_timestamp = reset_timestamp


class GitHubNotFoundError(GitHubError):
    """Raised when repository or resource is not found (HTTP 404)."""
    pass


def parse_and_validate_github_url(url: str) -> Tuple[str, str]:
    """Parse and validate a GitHub repository URL.
    
    Accepts:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        
    Returns:
        (owner, repo) tuple
        
    Raises:
        ValueError if the URL is not a valid, secure public GitHub URL.
    """
    if not url or not isinstance(url, str):
        raise ValueError("Repository URL must be a non-empty string.")

    cleaned_url = url.strip()
    match = GITHUB_URL_REGEX.match(cleaned_url)
    if not match:
        raise ValueError(
            "Invalid GitHub repository URL. Must be in the format 'https://github.com/{owner}/{repo}'."
        )

    owner, repo = match.group(1), match.group(2)
    # Block path traversals or malicious components
    if ".." in owner or ".." in repo or "/" in owner or "/" in repo:
        raise ValueError("Invalid repository or owner identifier.")

    return owner, repo


class GitHubClient:
    """Client for interacting with the GitHub REST API using urllib.request."""

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        settings = get_settings()
        # Retrieve token if not explicitly provided
        if token is None and settings.GITHUB_TOKEN:
            self._token = settings.GITHUB_TOKEN.get_secret_value().strip()
        else:
            self._token = token.strip() if token else None

        self._timeout = timeout or settings.GITHUB_REQUEST_TIMEOUT

    def _build_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> urllib.request.Request:
        """Construct a secure urllib.request.Request with required GitHub headers."""
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{GITHUB_API_BASE}/{endpoint.lstrip('/')}"

        if params:
            query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}?{query_string}"

        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "RelayPoint-MVP")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")

        if self._token:
            # Authorization header must NEVER be logged or leaked
            req.add_header("Authorization", f"Bearer {self._token}")

        return req

    def _execute_request(self, req: urllib.request.Request) -> Tuple[Any, Dict[str, str]]:
        """Execute HTTP request, inspect headers, and handle GitHub error states."""
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                headers = dict(resp.info().items())
                body_bytes = resp.read()
                try:
                    data = json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as decode_err:
                    raise GitHubError("Failed to decode GitHub API JSON response.") from decode_err
                return data, headers

        except urllib.error.HTTPError as http_err:
            status = http_err.code
            headers = dict(http_err.headers.items()) if http_err.headers else {}
            rate_remaining = headers.get("x-ratelimit-remaining")
            rate_reset = headers.get("x-ratelimit-reset")

            # Check rate limit conditions
            if status in (403, 429) and (rate_remaining == "0" or "rate limit" in str(http_err.reason).lower()):
                reset_ts = int(rate_reset) if rate_reset and rate_reset.isdigit() else None
                raise GitHubRateLimitError(
                    "GitHub API rate limit exceeded. Please configure a personal access token or wait for reset.",
                    reset_timestamp=reset_ts,
                ) from http_err

            if status == 401:
                raise GitHubAuthError("GitHub authentication failed. Please check your personal access token.") from http_err
            elif status == 403:
                raise GitHubForbiddenError("Access to GitHub resource is forbidden or requires additional scopes.") from http_err
            elif status == 404:
                raise GitHubNotFoundError("Requested repository or resource not found on GitHub.") from http_err
            else:
                raise GitHubError(f"GitHub API error (HTTP {status}).", status_code=status) from http_err

        except urllib.error.URLError as url_err:
            raise GitHubError(f"Network error connecting to GitHub: {url_err.reason}") from url_err
        except TimeoutError as timeout_err:
            raise GitHubError(f"GitHub request timed out after {self._timeout}s.") from timeout_err

    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository metadata."""
        endpoint = f"repos/{owner}/{repo}"
        req = self._build_request(endpoint)
        data, _ = self._execute_request(req)
        return {
            "external_id": str(data.get("id")),
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "description": data.get("description") or "",
            "default_branch": data.get("default_branch", "main"),
            "repository_url": data.get("html_url"),
            "is_private": data.get("private", False),
            "stars_count": data.get("stargazers_count", 0),
            "forks_count": data.get("forks_count", 0),
            "open_issues_count": data.get("open_issues_count", 0),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    def get_commits(self, owner: str, repo: str, limit: int = 50, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch recent commit records with bounded pagination."""
        settings = get_settings()
        max_limit = min(limit, settings.MAX_COMMITS)
        endpoint = f"repos/{owner}/{repo}/commits"
        per_page = min(max_limit, 100)

        params: Dict[str, Any] = {"per_page": per_page}
        if branch:
            params["sha"] = branch

        req = self._build_request(endpoint, params=params)
        raw_commits, _ = self._execute_request(req)

        results = []
        for item in raw_commits[:max_limit]:
            commit_data = item.get("commit", {})
            author_data = commit_data.get("author", {}) or {}
            results.append({
                "commit_hash": item.get("sha"),
                "message": commit_data.get("message", ""),
                "author_name": author_data.get("name", "Unknown"),
                "author_email": author_data.get("email", ""),
                "timestamp": author_data.get("date"),
                "source_url": item.get("html_url"),
            })
        return results

    def get_issues(self, owner: str, repo: str, state: str = "open", limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch repository issues (excluding pull requests)."""
        settings = get_settings()
        max_limit = min(limit, settings.MAX_ISSUES)
        endpoint = f"repos/{owner}/{repo}/issues"
        per_page = min(max_limit * 2, 100)  # Account for filtered PRs

        params = {"state": state, "per_page": per_page}
        req = self._build_request(endpoint, params=params)
        raw_issues, _ = self._execute_request(req)

        results = []
        for item in raw_issues:
            # GitHub issues endpoint includes PRs with a 'pull_request' key; filter them out
            if "pull_request" in item:
                continue

            user_data = item.get("user") or {}
            labels = [lbl.get("name") for lbl in item.get("labels", []) if isinstance(lbl, dict)]
            results.append({
                "number": item.get("number"),
                "title": item.get("title", ""),
                "body": item.get("body") or "",
                "state": item.get("state"),
                "author": user_data.get("login", "Unknown"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "closed_at": item.get("closed_at"),
                "comments_count": item.get("comments", 0),
                "labels": labels,
                "source_url": item.get("html_url"),
            })
            if len(results) >= max_limit:
                break
        return results

    def get_pull_requests(self, owner: str, repo: str, state: str = "all", limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch repository pull requests with bounded records."""
        settings = get_settings()
        max_limit = min(limit, settings.MAX_PULL_REQUESTS)
        endpoint = f"repos/{owner}/{repo}/pulls"
        per_page = min(max_limit, 100)

        params = {"state": state, "per_page": per_page}
        req = self._build_request(endpoint, params=params)
        raw_prs, _ = self._execute_request(req)

        results = []
        for item in raw_prs[:max_limit]:
            user_data = item.get("user") or {}
            head_data = item.get("head") or {}
            base_data = item.get("base") or {}
            results.append({
                "number": item.get("number"),
                "title": item.get("title", ""),
                "body": item.get("body") or "",
                "state": item.get("state"),
                "author": user_data.get("login", "Unknown"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "closed_at": item.get("closed_at"),
                "merged_at": item.get("merged_at"),
                "head_branch": head_data.get("ref"),
                "base_branch": base_data.get("ref"),
                "source_url": item.get("html_url"),
            })
        return results

    def get_pull_request_reviews(self, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """Fetch review decisions and comments for a pull request."""
        endpoint = f"repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        req = self._build_request(endpoint)
        try:
            raw_reviews, _ = self._execute_request(req)
        except GitHubError as err:
            logger.warning("Could not fetch PR #%s reviews: %s", pull_number, err)
            return []

        results = []
        for rev in raw_reviews:
            user_data = rev.get("user") or {}
            results.append({
                "review_id": str(rev.get("id")),
                "reviewer": user_data.get("login", "Unknown"),
                "state": rev.get("state"),  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
                "body": rev.get("body") or "",
                "submitted_at": rev.get("submitted_at"),
                "source_url": rev.get("html_url"),
            })
        return results
