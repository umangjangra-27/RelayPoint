"""Local Git Repository Inspection and Analysis Service.

Executes native git CLI operations safely via subprocess without shell=True,
extracting commit graphs, author stats, file churn, and branch metadata.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Union

from app.core.config import get_settings

logger = logging.getLogger("relaypoint.git_analyzer")

# Separators for robust log parsing
RECORD_SEPARATOR = "\x1e"  # ASCII 30 (Record Separator)
UNIT_SEPARATOR = "\x1f"    # ASCII 31 (Unit Separator)


class GitAnalysisError(Exception):
    """Exception raised for errors during local git inspection."""
    pass


def _run_git_command(args: List[str], cwd: Path, timeout: Optional[int] = None) -> str:
    """Execute a git command using argument arrays (never shell=True).
    
    Args:
        args: Full argument list starting with 'git'.
        cwd: Directory path in which to run git.
        timeout: Maximum seconds to wait.
        
    Returns:
        Standard output string stripped of trailing whitespace.
        
    Raises:
        GitAnalysisError if git exits non-zero or times out.
    """
    settings = get_settings()
    effective_timeout = timeout or settings.GIT_SUBPROCESS_TIMEOUT

    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            check=False,
        )
    except FileNotFoundError as err:
        raise GitAnalysisError("Git executable not found on system PATH.") from err
    except subprocess.TimeoutExpired as err:
        raise GitAnalysisError(
            f"Git command '{' '.join(args[:2])}' timed out after {effective_timeout}s."
        ) from err

    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"Git command failed with exit code {result.returncode}"
        raise GitAnalysisError(error_msg)

    return result.stdout.strip()


def validate_git_repository(repo_path: Union[str, Path]) -> Path:
    """Verify that a path exists, is a directory, and is inside a git working tree.
    
    Returns:
        Resolved absolute Path.
        
    Raises:
        GitAnalysisError if validation fails.
    """
    try:
        resolved = Path(repo_path).expanduser().resolve()
    except Exception as err:
        raise GitAnalysisError("Invalid filesystem path.") from err

    if not resolved.exists():
        raise GitAnalysisError("Repository path does not exist.")
    if not resolved.is_dir():
        raise GitAnalysisError("Repository path is not a directory.")

    try:
        out = _run_git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=resolved)
        if out != "true":
            raise GitAnalysisError("Directory is not inside a git working tree.")
    except GitAnalysisError as err:
        raise GitAnalysisError(f"Not a valid git repository: {err}") from err

    return resolved


def get_remote_url(repo_path: Union[str, Path]) -> Optional[str]:
    """Retrieve remote origin URL if configured."""
    resolved = validate_git_repository(repo_path)
    try:
        url = _run_git_command(["git", "config", "--get", "remote.origin.url"], cwd=resolved)
        return url if url else None
    except GitAnalysisError:
        return None


def get_current_branch(repo_path: Union[str, Path]) -> str:
    """Detect current active git branch or commit reference."""
    resolved = validate_git_repository(repo_path)
    try:
        branch = _run_git_command(["git", "branch", "--show-current"], cwd=resolved)
        if branch:
            return branch
        # Fallback for detached HEAD or newborn branch
        return _run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=resolved)
    except GitAnalysisError:
        return "main"


def get_branches(repo_path: Union[str, Path]) -> List[str]:
    """List local branch names."""
    resolved = validate_git_repository(repo_path)
    try:
        output = _run_git_command(["git", "branch", "--list", "--format=%(refname:short)"], cwd=resolved)
        if not output:
            return []
        return [b.strip() for b in output.splitlines() if b.strip()]
    except GitAnalysisError:
        return []


def get_commit_stats(repo_path: Path, commit_hash: str) -> Dict[str, Any]:
    """Extract addition, deletion, and touched file lists for a specific commit."""
    try:
        output = _run_git_command(
            ["git", "diff-tree", "--root", "--no-commit-id", "--numstat", "-r", commit_hash],
            cwd=repo_path,
        )
        if not output:
            return {"files_changed": 0, "additions": 0, "deletions": 0, "files": []}

        files = []
        total_additions = 0
        total_deletions = 0

        for line in output.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                raw_adds, raw_dels, file_path = parts[0], parts[1], parts[2]
                adds = int(raw_adds) if raw_adds.isdigit() else 0
                dels = int(raw_dels) if raw_dels.isdigit() else 0
                total_additions += adds
                total_deletions += dels
                files.append({
                    "path": file_path,
                    "additions": adds,
                    "deletions": dels,
                })

        return {
            "files_changed": len(files),
            "additions": total_additions,
            "deletions": total_deletions,
            "files": files,
        }
    except GitAnalysisError as err:
        logger.debug("Could not fetch numstat for commit %s: %s", commit_hash, err)
        return {"files_changed": 0, "additions": 0, "deletions": 0, "files": []}


def get_commit_history(
    repo_path: Union[str, Path],
    limit: int = 50,
    branch: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract recent commits with author details, subject, body, and file churn.
    
    Handles empty repositories gracefully without crashing.
    """
    resolved = validate_git_repository(repo_path)
    settings = get_settings()
    max_limit = min(limit, settings.MAX_COMMITS)

    # Format: hash | author_name | author_email | date_iso | subject | body
    format_spec = f"%H{UNIT_SEPARATOR}%an{UNIT_SEPARATOR}%ae{UNIT_SEPARATOR}%aI{UNIT_SEPARATOR}%s{UNIT_SEPARATOR}%b{RECORD_SEPARATOR}"

    args = ["git", "log", f"-n{max_limit}", f"--format={format_spec}"]
    if branch:
        args.append(branch)

    try:
        output = _run_git_command(args, cwd=resolved)
    except GitAnalysisError as err:
        # Handle repository with no commits
        if "does not have any commits yet" in str(err) or "unknown revision" in str(err) or "bad default revision" in str(err):
            return []
        raise

    if not output:
        return []

    commits: List[Dict[str, Any]] = []
    records = output.split(RECORD_SEPARATOR)

    for record in records:
        clean_record = record.strip()
        if not clean_record:
            continue

        parts = clean_record.split(UNIT_SEPARATOR)
        if len(parts) < 5:
            continue

        commit_hash = parts[0].strip()
        author_name = parts[1].strip()
        author_email = parts[2].strip()
        date_iso = parts[3].strip()
        subject = parts[4].strip()
        body = parts[5].strip() if len(parts) > 5 else ""

        full_message = f"{subject}\n\n{body}".strip() if body else subject

        # Retrieve file churn statistics
        stats = get_commit_stats(resolved, commit_hash)

        commits.append({
            "commit_hash": commit_hash,
            "author_name": author_name,
            "author_email": author_email,
            "timestamp": date_iso,
            "message": full_message,
            "subject": subject,
            "files_changed": stats["files_changed"],
            "additions": stats["additions"],
            "deletions": stats["deletions"],
            "changed_files": [f["path"] for f in stats["files"]],
        })

    return commits


def get_repository_overview(repo_path: Union[str, Path]) -> Dict[str, Any]:
    """Assemble a comprehensive local git repository overview."""
    resolved = validate_git_repository(repo_path)
    current_branch = get_current_branch(resolved)
    branches = get_branches(resolved)
    remote_url = get_remote_url(resolved)
    commits = get_commit_history(resolved, limit=1)

    return {
        "is_valid_git": True,
        "current_branch": current_branch,
        "branches": branches,
        "remote_url": remote_url,
        "latest_commit": commits[0] if commits else None,
        "total_branches": len(branches),
    }
