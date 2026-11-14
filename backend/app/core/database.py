"""RelayPoint SQLite Database Engine.

Provides robust, connection-safe SQLite database management using Python's
built-in sqlite3 module. Features foreign key enforcement, WAL mode for concurrency,
transaction context managers, and idempotent schema initialization.
"""

from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Generator, List, Optional, Union

from app.core.config import get_settings

logger = logging.getLogger("relaypoint.database")

# Schema DDL definitions
SCHEMA_SQL = """
-- 1. Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'github',
    external_repository_id TEXT,
    name TEXT NOT NULL,
    full_name TEXT NOT NULL UNIQUE,
    description TEXT,
    default_branch TEXT NOT NULL DEFAULT 'main',
    repository_url TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 2. Analysis Runs table
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE
);

-- 3. Source Chunks table
CREATE TABLE IF NOT EXISTS source_chunks (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_external_id TEXT,
    commit_hash TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE,
    UNIQUE (repository_id, content_hash)
);

-- 4. Evidence References table
CREATE TABLE IF NOT EXISTS evidence_references (
    id TEXT PRIMARY KEY,
    analysis_run_id TEXT NOT NULL,
    source_chunk_id TEXT NOT NULL,
    reference_type TEXT NOT NULL,
    reference_identifier TEXT NOT NULL,
    source_url TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs (id) ON DELETE CASCADE,
    FOREIGN KEY (source_chunk_id) REFERENCES source_chunks (id) ON DELETE CASCADE
);

-- 5. Handover Reports table
CREATE TABLE IF NOT EXISTS handover_reports (
    id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    title TEXT NOT NULL,
    report_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (repository_id) REFERENCES repositories (id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_run_id) REFERENCES analysis_runs (id) ON DELETE CASCADE
);

-- 6. Review Decisions table
CREATE TABLE IF NOT EXISTS review_decisions (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer_name TEXT NOT NULL,
    reviewer_comment TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES handover_reports (id) ON DELETE CASCADE
);

-- Indexes for performant lookups
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories (full_name);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_repo ON analysis_runs (repository_id, status);
CREATE INDEX IF NOT EXISTS idx_source_chunks_repo ON source_chunks (repository_id, source_type);
CREATE INDEX IF NOT EXISTS idx_source_chunks_hash ON source_chunks (content_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence_references (analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_chunk ON evidence_references (source_chunk_id);
CREATE INDEX IF NOT EXISTS idx_handover_reports_repo ON handover_reports (repository_id);
CREATE INDEX IF NOT EXISTS idx_handover_reports_run ON handover_reports (analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_review_decisions_report ON review_decisions (report_id);
"""


def get_db_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve the SQLite database file path."""
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    settings = get_settings()
    return settings.get_database_path()


def create_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Create a configured SQLite connection.
    
    Enforces:
    - Foreign keys ON
    - WAL journal mode for safe concurrent access
    - 5000ms busy timeout to prevent transient locks
    - sqlite3.Row row factory for column-name mapping
    """
    resolved_path = get_db_path(db_path)
    # Ensure parent directory exists
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        database=str(resolved_path),
        timeout=5.0,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row

    # Performance and integrity pragmas
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    return conn


@contextmanager
def get_db_context(db_path: Optional[Union[str, Path]] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite transactions.
    
    Automatically commits on normal block exit and rolls back on unhandled exceptions.
    Ensures connection is closed cleanly.
    """
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Database transaction rolled back due to error: %s", exc)
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Union[str, Path]] = None) -> None:
    """Idempotently initialize all database tables and indexes."""
    with get_db_context(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
    logger.info("Database schema initialized successfully at %s", get_db_path(db_path))


def check_db_health(db_path: Optional[Union[str, Path]] = None) -> dict:
    """Execute a lightweight diagnostic query to verify database health.
    
    Returns status dict without exposing internal filesystem paths or sensitive details.
    """
    try:
        with get_db_context(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS probe;")
            row = cursor.fetchone()
            if not row or row["probe"] != 1:
                return {"status": "error", "message": "Probe query failed"}

            # Retrieve active tables count
            cursor.execute("SELECT count(*) AS tbl_count FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tbl_count = cursor.fetchone()["tbl_count"]

            return {
                "status": "connected",
                "tables_count": tbl_count,
            }
    except Exception as exc:
        logger.warning("Database health check probe failed: %s", exc)
        return {
            "status": "error",
            "message": "Database connection error",
        }


def get_existing_tables(db_path: Optional[Union[str, Path]] = None) -> List[str]:
    """Retrieve list of user tables in the database."""
    with get_db_context(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
        return [row["name"] for row in cursor.fetchall()]
