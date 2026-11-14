"""Unit tests for local Git analysis using synthetic repositories."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from app.services.git_analyzer import (
    GitAnalysisError,
    get_branches,
    get_commit_history,
    get_current_branch,
    get_repository_overview,
    validate_git_repository,
)


class TestGitAnalyzer(unittest.TestCase):
    """Test suite for local git inspection."""

    def setUp(self):
        """Create a temporary synthetic Git repository."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name)

        # Initialize git repo with standard configuration
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.repo_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Synthetic Author"], cwd=str(self.repo_path), check=True)
        subprocess.run(["git", "config", "user.email", "synthetic@example.com"], cwd=str(self.repo_path), check=True)

    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_empty_repository_handling(self):
        """Verify empty repositories without commits do not crash."""
        commits = get_commit_history(self.repo_path)
        self.assertEqual(commits, [])

        overview = get_repository_overview(self.repo_path)
        self.assertTrue(overview["is_valid_git"])
        self.assertIsNone(overview["latest_commit"])

    def test_commit_history_and_stats(self):
        """Verify commit history, authorship, and file change statistics."""
        # 1. Create first commit
        file1 = self.repo_path / "hello.py"
        file1.write_text("print('Hello World')\n", encoding="utf-8")
        subprocess.run(["git", "add", "hello.py"], cwd=str(self.repo_path), check=True)
        subprocess.run(["git", "commit", "-m", "feat: initial commit\n\nFull details here."], cwd=str(self.repo_path), check=True)

        # 2. Create second commit on a new branch
        subprocess.run(["git", "checkout", "-b", "feature-x"], cwd=str(self.repo_path), check=True)
        file2 = self.repo_path / "utils.py"
        file2.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        subprocess.run(["git", "add", "utils.py"], cwd=str(self.repo_path), check=True)
        subprocess.run(["git", "commit", "-m", "feat(utils): add helper math function"], cwd=str(self.repo_path), check=True)

        # Inspect current branch
        current_branch = get_current_branch(self.repo_path)
        self.assertEqual(current_branch, "feature-x")

        # Inspect branches
        branches = get_branches(self.repo_path)
        self.assertIn("main", branches)
        self.assertIn("feature-x", branches)

        # Inspect commit history
        commits = get_commit_history(self.repo_path, limit=10)
        self.assertEqual(len(commits), 2)

        latest = commits[0]
        self.assertEqual(latest["author_name"], "Synthetic Author")
        self.assertEqual(latest["author_email"], "synthetic@example.com")
        self.assertIn("add helper math function", latest["message"])
        self.assertEqual(latest["files_changed"], 1)
        self.assertIn("utils.py", latest["changed_files"])

        initial = commits[1]
        self.assertIn("initial commit", initial["message"])
        self.assertIn("Full details here.", initial["message"])
        self.assertEqual(initial["files_changed"], 1)
        self.assertIn("hello.py", initial["changed_files"])

    def test_invalid_repository_path(self):
        """Verify invalid or non-git paths raise GitAnalysisError."""
        with self.assertRaises(GitAnalysisError):
            validate_git_repository(self.repo_path / "non_existent_folder")

        # Create non-git directory
        non_git = self.repo_path / "plain_dir"
        non_git.mkdir()
        # Even inside a git working tree, we test that pointing outside raises error
        outside_dir = tempfile.TemporaryDirectory()
        try:
            with self.assertRaises(GitAnalysisError):
                validate_git_repository(outside_dir.name)
        finally:
            outside_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
