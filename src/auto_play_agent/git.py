import re
import subprocess
from datetime import datetime

import requests as _req

from .config import BASE_BRANCH, GITHUB_TOKEN, PROJECT_DIR


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def has_staged_changes() -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=PROJECT_DIR
    )
    return result.returncode != 0


def get_diff(max_chars: int = 4000) -> str:
    """Return all uncommitted changes vs HEAD. Truncated to max_chars."""
    try:
        diff = git("diff", "HEAD")
        if not diff:
            diff = git("diff")
        if len(diff) > max_chars:
            return diff[:max_chars] + "\n…(truncated)"
        return diff
    except Exception:
        return ""


def _latest_unmerged_nightly() -> str | None:
    """
    Return the most recent feature/ai-nightly-* remote branch not yet merged into BASE_BRANCH.
    Used to chain nightly branches so multi-day work doesn't conflict.
    """
    try:
        git("fetch", "origin", "--prune", "--quiet")
        out = git(
            "branch", "-r",
            "--no-merged", f"origin/{BASE_BRANCH}",
            "--list", "origin/feature/ai-nightly-*",
        )
        branches = sorted(b.strip() for b in out.splitlines() if b.strip())
        if branches:
            return branches[-1].removeprefix("origin/")
    except Exception:
        pass
    return None


def checkout_nightly_branch() -> tuple[str, bool]:
    """
    Reuse the most recent unmerged nightly branch if one exists (accumulating across nights),
    otherwise create feature/ai-nightly-YYYY-MM-DD from BASE_BRANCH.
    Returns (branch_name, pr_already_exists).
    """
    existing = _latest_unmerged_nightly()
    if existing:
        git("fetch", "origin", existing)
        try:
            git("checkout", "-b", existing, f"origin/{existing}")
        except RuntimeError as exc:
            if "already exists" in str(exc):
                git("checkout", existing)
                git("reset", "--hard", f"origin/{existing}")
            else:
                raise
        return existing, True

    base = f"feature/ai-nightly-{datetime.now().strftime('%Y-%m-%d')}"
    for suffix in [None, *range(2, 10)]:
        candidate = base if suffix is None else f"{base}-{suffix}"
        try:
            git("checkout", "-b", candidate)
            return candidate, False
        except RuntimeError as exc:
            if "already exists" not in str(exc):
                raise
    raise RuntimeError(f"Could not create nightly branch: {base}")


def push_branch(branch: str) -> bool:
    try:
        git("push", "-u", "origin", branch)
        return True
    except RuntimeError:
        return False


def _github_repo() -> tuple[str, str] | None:
    """Parse (owner, repo) from git remote origin. Returns None if not GitHub."""
    try:
        url = git("remote", "get-url", "origin")
        m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)
    except Exception:
        pass
    return None


def create_pr(title: str, body: str, branch: str) -> str:
    """Create GitHub PR via REST API. Returns PR URL or '' when token/repo unset."""
    if not GITHUB_TOKEN:
        return ""
    repo = _github_repo()
    if not repo:
        return ""
    owner, name = repo
    resp = _req.post(
        f"https://api.github.com/repos/{owner}/{name}/pulls",
        json={"title": title, "body": body, "head": branch, "base": BASE_BRANCH},
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    if resp.status_code == 201:
        return resp.json().get("html_url", "")
    raise RuntimeError(f"GitHub API {resp.status_code}: {resp.json()}")
