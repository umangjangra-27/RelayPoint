"""RelayPoint Demonstration Data Seeder.

Loads the verified, sanitized demonstration dataset for 'octocat/Hello-World'
into the local SQLite database. This allows fresh clones and offline evaluations
to immediately explore the complete handover workflow without external network calls.
"""

import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.core.database import get_db_context, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("relaypoint.seeder")


def seed_demo_data(fixture_path: Path = None, db_path: Path = None) -> bool:
    """Populate the local SQLite database with verified demonstration fixtures."""
    init_db(db_path)

    if fixture_path is None:
        fixture_path = backend_dir / "app" / "fixtures" / "demo_data.json"

    if not fixture_path.exists():
        logger.error(f"Demonstration fixture file not found at: {fixture_path}")
        return False

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    repo = data.get("repository", {})
    run = data.get("analysis_run", {})
    chunks = data.get("source_chunks", [])
    evidence = data.get("evidence_references", [])
    report = data.get("handover_report", {})

    report_payload = report.get("report_json")
    if not report_payload and "report_data" in report:
        report_payload = json.dumps(report["report_data"]) if isinstance(report["report_data"], dict) else report["report_data"]

    with get_db_context(db_path) as conn:
        # 1. Repository
        conn.execute(
            """
            INSERT OR REPLACE INTO repositories
            (id, provider, external_repository_id, name, full_name, description, default_branch, repository_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo["id"],
                repo.get("provider", "github"),
                repo.get("external_repository_id"),
                repo["name"],
                repo["full_name"],
                repo.get("description", ""),
                repo.get("default_branch", "master"),
                repo["repository_url"],
                repo["created_at"],
                repo["updated_at"],
            ),
        )

        # 2. Analysis Run
        conn.execute(
            """
            INSERT OR REPLACE INTO analysis_runs
            (id, repository_id, status, started_at, completed_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run["id"],
                run["repository_id"],
                run["status"],
                run["started_at"],
                run.get("completed_at"),
                run.get("error_message"),
            ),
        )

        # 3. Source Chunks
        for ch in chunks:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_chunks
                (id, repository_id, source_type, source_external_id, commit_hash, content, content_hash, source_url, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ch["id"],
                    ch["repository_id"],
                    ch["source_type"],
                    ch.get("source_external_id"),
                    ch.get("commit_hash"),
                    ch["content"],
                    ch["content_hash"],
                    ch.get("source_url"),
                    ch.get("metadata_json", "{}"),
                    ch["created_at"],
                ),
            )

        # 4. Evidence References
        for ev in evidence:
            conn.execute(
                """
                INSERT OR REPLACE INTO evidence_references
                (id, analysis_run_id, source_chunk_id, reference_type, reference_identifier, source_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev["id"],
                    ev["analysis_run_id"],
                    ev["source_chunk_id"],
                    ev["reference_type"],
                    ev.get("reference_identifier"),
                    ev.get("source_url"),
                    ev["created_at"],
                ),
            )

        # 5. Handover Report
        conn.execute(
            """
            INSERT OR REPLACE INTO handover_reports
            (id, repository_id, analysis_run_id, title, status, created_at, updated_at, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["id"],
                report["repository_id"],
                report["analysis_run_id"],
                report["title"],
                report["status"],
                report["created_at"],
                report["updated_at"],
                report_payload,
            ),
        )

    logger.info("Successfully seeded demonstration data:")
    logger.info(" - Repository: %s (%s)", repo["full_name"], repo["id"])
    logger.info(" - Ingested Source Chunks: %d", len(chunks))
    logger.info(" - Evidence References: %d", len(evidence))
    logger.info(" - Handover Report: %s (%s)", report["title"], report["id"])
    return True


if __name__ == "__main__":
    success = seed_demo_data()
    sys.exit(0 if success else 1)
