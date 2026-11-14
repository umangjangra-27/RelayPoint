"""Unit tests for SQLite database layer, schema, transactions, and foreign keys."""

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from app.core.database import (
    check_db_health,
    create_connection,
    get_db_context,
    get_existing_tables,
    init_db,
)


class TestDatabaseLayer(unittest.TestCase):
    """Test suite for SQLite operations."""

    def setUp(self):
        """Create a dedicated temporary database file for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_relaypoint.db"

    def tearDown(self):
        """Clean up temporary test resources."""
        self.temp_dir.cleanup()

    def test_schema_initialization_and_idempotency(self):
        """Verify all 6 tables and indexes are created, and re-running is safe."""
        init_db(self.db_path)
        tables = get_existing_tables(self.db_path)

        expected_tables = {
            "repositories",
            "analysis_runs",
            "source_chunks",
            "evidence_references",
            "handover_reports",
            "review_decisions",
        }
        self.assertTrue(expected_tables.issubset(set(tables)))

        # Idempotency test: Re-running init_db must not raise exceptions
        init_db(self.db_path)
        tables_after = get_existing_tables(self.db_path)
        self.assertEqual(tables, tables_after)

    def test_database_health_check(self):
        """Verify health check probe reports connected status and table count."""
        init_db(self.db_path)
        health = check_db_health(self.db_path)
        self.assertEqual(health["status"], "connected")
        self.assertGreaterEqual(health["tables_count"], 6)

    def test_foreign_key_enforcement(self):
        """Verify foreign key constraint violations raise sqlite3.IntegrityError."""
        init_db(self.db_path)

        # Attempting to insert an analysis_run with non-existent repository_id must fail
        with self.assertRaises(sqlite3.IntegrityError):
            with get_db_context(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO analysis_runs (id, repository_id, status, started_at)
                    VALUES ('run-1', 'non-existent-repo-id', 'running', '2026-11-11T12:00:00Z');
                    """
                )

    def test_cascade_deletion(self):
        """Verify deleting a parent repository cascades to child analysis_runs and source_chunks."""
        init_db(self.db_path)

        with get_db_context(self.db_path) as conn:
            # 1. Insert repository
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo-100', 'github', 'test-repo', 'org/test-repo', 'main', 'https://github.com/org/test-repo', '2026-11-11T12:00:00Z', '2026-11-11T12:00:00Z');
                """
            )
            # 2. Insert child analysis run
            conn.execute(
                """
                INSERT INTO analysis_runs (id, repository_id, status, started_at)
                VALUES ('run-100', 'repo-100', 'completed', '2026-11-11T12:00:00Z');
                """
            )
            # 3. Insert child source chunk
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, content, content_hash, created_at)
                VALUES ('chunk-100', 'repo-100', 'commit', 'fix: resolve race condition', 'hash123', '2026-11-11T12:00:00Z');
                """
            )

        # Verify records exist
        with get_db_context(self.db_path) as conn:
            run_count = conn.execute("SELECT count(*) FROM analysis_runs WHERE repository_id = 'repo-100';").fetchone()[0]
            chunk_count = conn.execute("SELECT count(*) FROM source_chunks WHERE repository_id = 'repo-100';").fetchone()[0]
            self.assertEqual(run_count, 1)
            self.assertEqual(chunk_count, 1)

            # Delete parent repository
            conn.execute("DELETE FROM repositories WHERE id = 'repo-100';")

        # Verify child records were automatically cascaded
        with get_db_context(self.db_path) as conn:
            run_count = conn.execute("SELECT count(*) FROM analysis_runs WHERE repository_id = 'repo-100';").fetchone()[0]
            chunk_count = conn.execute("SELECT count(*) FROM source_chunks WHERE repository_id = 'repo-100';").fetchone()[0]
            self.assertEqual(run_count, 0)
            self.assertEqual(chunk_count, 0)

    def test_transaction_rollback(self):
        """Verify exceptions inside get_db_context trigger automatic rollback."""
        init_db(self.db_path)

        try:
            with get_db_context(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                    VALUES ('repo-rollback', 'github', 'rollback-repo', 'org/rollback-repo', 'main', 'https://github.com/org/rollback-repo', '2026-11-11T12:00:00Z', '2026-11-11T12:00:00Z');
                    """
                )
                # Intentionally trigger an error
                raise RuntimeError("Simulated transient processing failure")
        except RuntimeError:
            pass

        # Verify the insert was rolled back
        with get_db_context(self.db_path) as conn:
            cursor = conn.execute("SELECT count(*) FROM repositories WHERE id = 'repo-rollback';")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
