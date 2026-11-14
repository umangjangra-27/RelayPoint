"""Repository History Ingestion and Normalization Service.

Coordinates:
- GitHub REST API data retrieval (commits, issues, PRs)
- Local Git inspection fallback where applicable
- Deterministic secret sanitization prior to persistence
- SHA-256 content hashing and idempotent duplicate detection
- Relational SQLite storage into repositories, analysis_runs, and source_chunks
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import get_settings
from app.core.database import get_db_context
from app.integrations.github import (
    GitHubClient,
    GitHubError,
    parse_and_validate_github_url,
)
from app.utils.sanitizer import sanitize_text

logger = logging.getLogger("relaypoint.ingestion")


def _generate_id(prefix: str) -> str:
    """Generate a unique prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _compute_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class IngestionService:
    """Coordinates repository history ingestion, sanitization, and persistence."""

    def __init__(self, github_client: Optional[GitHubClient] = None):
        self.github_client = github_client or GitHubClient()
        self.settings = get_settings()

    def connect_repository(self, repository_url: str, custom_name: Optional[str] = None) -> Dict[str, Any]:
        """Validate and register a repository in the database.
        
        Args:
            repository_url: GitHub repository URL.
            custom_name: Optional display name override.
            
        Returns:
            Dictionary representing the stored repository record.
        """
        owner, repo_name = parse_and_validate_github_url(repository_url)
        full_name = f"{owner}/{repo_name}"

        # Check if already registered
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE full_name = ?;", (full_name,))
            existing = cursor.fetchone()
            if existing:
                return dict(existing)

        # Retrieve remote metadata from GitHub
        remote_meta = self.github_client.get_repository(owner, repo_name)

        repo_id = _generate_id("repo")
        now = _now_iso()
        name = custom_name.strip() if custom_name and custom_name.strip() else remote_meta["name"]

        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (
                    id, provider, external_repository_id, name, full_name,
                    description, default_branch, repository_url, created_at, updated_at
                ) VALUES (?, 'github', ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    repo_id,
                    remote_meta.get("external_id"),
                    name,
                    full_name,
                    remote_meta.get("description", ""),
                    remote_meta.get("default_branch", "main"),
                    remote_meta.get("repository_url", repository_url),
                    now,
                    now,
                ),
            )

        return self.get_repository_by_id(repo_id)

    def get_repository_by_id(self, repo_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve repository record by primary key."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories WHERE id = ?;", (repo_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_source_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific source chunk by primary key."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM source_chunks WHERE id = ?;", (chunk_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.get("metadata_json", "{}"))
            except Exception:
                item["metadata"] = {}
            return item

    def list_repositories(self) -> List[Dict[str, Any]]:
        """List all connected repositories ordered by most recent."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM repositories ORDER BY created_at DESC;")
            return [dict(row) for row in cursor.fetchall()]

    def ingest_repository(self, repo_id: str) -> Dict[str, Any]:
        """Execute history ingestion for a registered repository.
        
        Fetches commits, issues, and PRs, scrubs secrets, and saves chunks into SQLite.
        """
        repo = self.get_repository_by_id(repo_id)
        if not repo:
            raise ValueError(f"Repository with ID '{repo_id}' not found.")

        owner, repo_name = parse_and_validate_github_url(repo["repository_url"])

        # 1. Initialize analysis run record
        run_id = _generate_id("run")
        start_time = _now_iso()

        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO analysis_runs (id, repository_id, status, started_at)
                VALUES (?, ?, 'running', ?);
                """,
                (run_id, repo_id, start_time),
            )

        chunks_created = 0
        duplicates_skipped = 0

        try:
            # 2. Ingest Commits
            commits = self.github_client.get_commits(
                owner, repo_name, limit=self.settings.MAX_COMMITS, branch=repo.get("default_branch")
            )
            for c in commits:
                created, skipped = self._persist_source_chunk(
                    repo_id=repo_id,
                    source_type="commit",
                    source_external_id=c.get("commit_hash"),
                    commit_hash=c.get("commit_hash"),
                    raw_content=c.get("message", ""),
                    source_url=c.get("source_url"),
                    metadata={
                        "author_name": c.get("author_name"),
                        "author_email": c.get("author_email"),
                        "timestamp": c.get("timestamp"),
                    },
                )
                chunks_created += created
                duplicates_skipped += skipped

            # 3. Ingest Issues
            issues = self.github_client.get_issues(owner, repo_name, state="all", limit=self.settings.MAX_ISSUES)
            for iss in issues:
                issue_content = f"{iss.get('title', '')}\n\n{iss.get('body', '')}".strip()
                created, skipped = self._persist_source_chunk(
                    repo_id=repo_id,
                    source_type="issue",
                    source_external_id=str(iss.get("number")),
                    commit_hash=None,
                    raw_content=issue_content,
                    source_url=iss.get("source_url"),
                    metadata={
                        "number": iss.get("number"),
                        "title": iss.get("title"),
                        "state": iss.get("state"),
                        "author": iss.get("author"),
                        "created_at": iss.get("created_at"),
                        "closed_at": iss.get("closed_at"),
                        "labels": iss.get("labels", []),
                    },
                )
                chunks_created += created
                duplicates_skipped += skipped

            # 4. Ingest Pull Requests
            prs = self.github_client.get_pull_requests(
                owner, repo_name, state="all", limit=self.settings.MAX_PULL_REQUESTS
            )
            for pr in prs:
                pr_content = f"{pr.get('title', '')}\n\n{pr.get('body', '')}".strip()
                created, skipped = self._persist_source_chunk(
                    repo_id=repo_id,
                    source_type="pull_request",
                    source_external_id=str(pr.get("number")),
                    commit_hash=None,
                    raw_content=pr_content,
                    source_url=pr.get("source_url"),
                    metadata={
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "author": pr.get("author"),
                        "created_at": pr.get("created_at"),
                        "closed_at": pr.get("closed_at"),
                        "merged_at": pr.get("merged_at"),
                        "head_branch": pr.get("head_branch"),
                        "base_branch": pr.get("base_branch"),
                    },
                )
                chunks_created += created
                duplicates_skipped += skipped

            # 5. Mark Run Complete
            completion_time = _now_iso()
            with get_db_context() as conn:
                conn.execute(
                    """
                    UPDATE analysis_runs
                    SET status = 'completed', completed_at = ?
                    WHERE id = ?;
                    """,
                    (completion_time, run_id),
                )
                conn.execute(
                    "UPDATE repositories SET updated_at = ? WHERE id = ?;",
                    (completion_time, repo_id),
                )

            return {
                "run_id": run_id,
                "repository_id": repo_id,
                "status": "completed",
                "chunks_created": chunks_created,
                "duplicates_skipped": duplicates_skipped,
                "started_at": start_time,
                "completed_at": completion_time,
            }

        except Exception as exc:
            logger.error("Ingestion run %s failed: %s", run_id, exc)
            with get_db_context() as conn:
                conn.execute(
                    """
                    UPDATE analysis_runs
                    SET status = 'failed', completed_at = ?, error_message = ?
                    WHERE id = ?;
                    """,
                    (_now_iso(), run_id, "Ingestion failed due to an error fetching or processing repository data."),
                )
            raise

    def _persist_source_chunk(
        self,
        repo_id: str,
        source_type: str,
        source_external_id: Optional[str],
        commit_hash: Optional[str],
        raw_content: str,
        source_url: Optional[str],
        metadata: Dict[str, Any],
    ) -> Tuple[int, int]:
        """Sanitize, hash, and persist a source chunk with duplicate avoidance.
        
        Returns:
            (created_count, skipped_count)
        """
        # Bounded character length
        bounded_raw = raw_content[: self.settings.MAX_CONTENT_LENGTH] if raw_content else ""

        # CRITICAL SECURITY RULE: Sanitize raw content before hashing and persistence
        sanitized_content = sanitize_text(bounded_raw)
        content_hash = _compute_hash(sanitized_content)

        chunk_id = _generate_id("chunk")
        now = _now_iso()
        metadata_str = json.dumps(metadata)

        with get_db_context() as conn:
            # Check duplicate by (repository_id, content_hash)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM source_chunks WHERE repository_id = ? AND content_hash = ?;",
                (repo_id, content_hash),
            )
            existing = cursor.fetchone()
            if existing:
                return 0, 1

            conn.execute(
                """
                INSERT INTO source_chunks (
                    id, repository_id, source_type, source_external_id,
                    commit_hash, content, content_hash, source_url,
                    metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    chunk_id,
                    repo_id,
                    source_type,
                    source_external_id,
                    commit_hash,
                    sanitized_content,
                    content_hash,
                    source_url,
                    metadata_str,
                    now,
                ),
            )
        return 1, 0

    def get_source_chunks(
        self,
        repo_id: str,
        source_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Fetch paginated source chunks for a repository."""
        limit = min(max(1, limit), 100)
        offset = max(0, offset)

        query = "SELECT * FROM source_chunks WHERE repository_id = ?"
        params: List[Any] = [repo_id]

        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            # Total count
            count_query = "SELECT count(*) FROM source_chunks WHERE repository_id = ?"
            count_params: List[Any] = [repo_id]
            if source_type:
                count_query += " AND source_type = ?"
                count_params.append(source_type)
            cursor.execute(count_query, tuple(count_params))
            total_count = cursor.fetchone()[0]

            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["metadata"] = json.loads(item.get("metadata_json", "{}"))
                except Exception:
                    item["metadata"] = {}
                results.append(item)

            return {
                "repository_id": repo_id,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "sources": results,
            }

    def get_activity_timeline(self, repo_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Assemble a chronological activity timeline of commits, issues, and PRs."""
        chunks_data = self.get_source_chunks(repo_id, limit=limit, offset=0)
        timeline = []

        for chunk in chunks_data["sources"]:
            meta = chunk.get("metadata", {})
            source_type = chunk.get("source_type")

            # Determine timestamp
            event_time = meta.get("timestamp") or meta.get("created_at") or chunk.get("created_at")

            # Title / description
            if source_type == "commit":
                title = chunk["content"].splitlines()[0] if chunk["content"] else "Commit"
                author = meta.get("author_name", "Unknown")
            elif source_type in ("issue", "pull_request"):
                title = meta.get("title") or chunk["content"].splitlines()[0] if chunk["content"] else source_type.title()
                author = meta.get("author", "Unknown")
            else:
                title = chunk["content"][:60] if chunk["content"] else "Activity"
                author = "System"

            timeline.append({
                "source_id": chunk["id"],
                "source_type": source_type,
                "identifier": chunk.get("source_external_id"),
                "title": title,
                "author": author,
                "timestamp": event_time,
                "source_url": chunk.get("source_url"),
            })

        # Sort descending by timestamp
        timeline.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)
        return timeline
