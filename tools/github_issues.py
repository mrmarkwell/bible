#!/usr/bin/env python3
"""Sovereign Zero-Dependency GitHub Issue Triage & Bug Resolution Engine.

Zero-dependency tool (Python 3 standard library only per ADR-003) for managing
GitHub issues and bug reports:
- Interfaces with the GitHub REST API using urllib.request and json.
- Automatically extracts GitHub repository metadata (owner/repo) from git remotes.
- Lists open/closed issues, filtering out pull requests.
- Views full issue details, labels, submitter info, and issue comments.
- Posts comments to issues using GITHUB_TOKEN / GH_TOKEN.
- Closes issues with standardized reasons ('completed' or 'not_planned').
- Provides autonomous loop integration (--prompt, --summary, --check) for ralph.sh.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib import error as url_error, parse as url_parse, request as url_request

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_repo_info(repo_override: Optional[str] = None, cwd: Optional[Path] = None) -> Tuple[str, str]:
    """Extract GitHub (owner, repo) pair from argument or git remote origin URL.

    Falls back to ('mrmarkwell', 'bible') if detection fails.
    """
    if repo_override:
        parts = repo_override.strip().split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]

    target_dir = cwd or REPO_ROOT
    try:
        res = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        url = res.stdout.strip()
        if url:
            m = re.search(r"github\.com[:/]([^/]+)/([^/\.]+?)(?:\.git)?$", url)
            if m:
                return m.group(1), m.group(2)
    except Exception:
        pass

    return "mrmarkwell", "bible"


def get_auth_token(token_override: Optional[str] = None) -> Optional[str]:
    """Retrieve GitHub API personal access token from override, environment, or config files.

    Search order:
    1. token_override parameter (if non-empty)
    2. GITHUB_TOKEN or GH_TOKEN environment variables
    3. .env file in cwd or repository root
    4. config/github_token.txt or config/gh_token.txt in repository root
    5. ~/.config/github/token or ~/.config/bible/github_token
    """
    if token_override and token_override.strip():
        return token_override.strip()

    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    if os.environ.get("BIBLE_TEST_MODE") == "1":
        return None

    candidate_paths = [
        Path.cwd() / ".env",
        REPO_ROOT / ".env",
        REPO_ROOT / "config" / "github_token.txt",
        REPO_ROOT / "config" / "gh_token.txt",
        Path.home() / ".config" / "github" / "token",
        Path.home() / ".config" / "bible" / "github_token",
    ]
    for p in candidate_paths:
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8").strip()
                if p.name == ".env":
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        if k.strip() in ("GITHUB_TOKEN", "GH_TOKEN"):
                            clean_v = v.strip().strip("'\"")
                            if clean_v:
                                return clean_v
                else:
                    if content:
                        return content.splitlines()[0].strip()
            except Exception:
                continue

    return None


def get_cache_path(explicit_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Resolve persistent cache path for GitHub issues.

    Returns None in test mode unless explicit path or GITHUB_ISSUES_CACHE_PATH is set.
    """
    if explicit_path:
        return Path(explicit_path)
    custom = os.environ.get("GITHUB_ISSUES_CACHE_PATH")
    if custom:
        return Path(custom)
    if os.environ.get("BIBLE_TEST_MODE") == "1":
        return None
    return REPO_ROOT / "data" / "github_issues_cache.json"


def is_cache_fresh(cache_path: Optional[Union[str, Path]] = None, ttl_seconds: float = 60.0) -> bool:
    """Check if local cache exists and was fetched within ttl_seconds."""
    path = get_cache_path(cache_path)
    if not path or not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        last_str = data.get("last_fetched_utc")
        if not last_str:
            return False
        last_time = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - last_time).total_seconds() < ttl_seconds
    except Exception:
        return False


def load_cached_issues(
    repo: str = "mrmarkwell/bible",
    state: str = "open",
    cache_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Load issues from local persistent cache, filtering by state."""
    path = get_cache_path(cache_path)
    if not path or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        issues = data.get("issues", [])
        if state == "all":
            return issues
        return [i for i in issues if i.get("state", "open") == state]
    except Exception:
        return []


def save_cached_issues(
    repo: str,
    issues: List[Dict[str, Any]],
    cache_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Save issues to persistent cache atomically, preserving other cached issues."""
    path = get_cache_path(cache_path)
    if not path:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[int, Dict[str, Any]] = {}
        if path.exists():
            try:
                old_data = json.loads(path.read_text(encoding="utf-8"))
                for item in old_data.get("issues", []):
                    if "number" in item:
                        existing[item["number"]] = item
            except Exception:
                pass

        for item in issues:
            if "number" in item:
                existing[item["number"]] = item

        merged = sorted(existing.values(), key=lambda x: x.get("number", 0))
        payload = {
            "repo": repo,
            "last_fetched_utc": datetime.now(timezone.utc).isoformat(),
            "issues": merged,
        }
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)
        return True
    except Exception:
        return False


def update_cached_issue_state(
    issue_number: int,
    state: str = "closed",
    reason: Optional[str] = "completed",
    comment: Optional[str] = None,
    cache_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Update a single cached issue's state (open/closed) and optional comment."""
    path = get_cache_path(cache_path)
    if not path or not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        issues = data.get("issues", [])
        updated = False
        for issue in issues:
            if issue.get("number") == issue_number:
                issue["state"] = state
                if reason:
                    issue["state_reason"] = reason
                if comment:
                    comments = issue.setdefault("comments_list", [])
                    comments.append({
                        "user": {"login": "agent"},
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "body": comment,
                    })
                    issue["comments"] = len(comments)
                updated = True
                break
        if updated:
            data["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_path.replace(path)
        return updated
    except Exception:
        return False


def make_api_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    token: Optional[str] = None,
    timeout: float = 12.0,
) -> Tuple[int, Any, Dict[str, str]]:
    """Execute an HTTP request to the GitHub REST API using Python standard library urllib."""
    headers = {
        "User-Agent": "Bible-Engine-Agent/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    encoded_data = None
    if data is not None:
        encoded_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = url_request.Request(url, data=encoded_data, headers=headers, method=method)

    try:
        with url_request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body_bytes = resp.read()
            resp_headers = dict(resp.headers)
            body_text = body_bytes.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(body_text) if body_text.strip() else {}
            except Exception:
                parsed = {"raw": body_text}
            return status, parsed, resp_headers
    except url_error.HTTPError as err:
        error_body = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(error_body)
        except Exception:
            parsed = {"message": error_body or str(err)}
        return err.code, parsed, dict(err.headers)
    except Exception as exc:
        return 0, {"error": str(exc)}, {}


def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    token: Optional[str] = None,
    limit: int = 30,
    use_cache: bool = True,
    force_refresh: bool = False,
    cache_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """Fetch issues from GitHub API, filtering out pull requests, with offline cache fallback."""
    # Fast path: check if cache is fresh (<60s) to conserve unauthenticated rate limits
    if use_cache and not force_refresh and is_cache_fresh(cache_path, ttl_seconds=60.0):
        cached = load_cached_issues(f"{owner}/{repo}", state=state, cache_path=cache_path)
        if cached:
            return True, cached[:limit], ""

    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state={url_parse.quote(state)}&per_page={limit}"
    status, data, _ = make_api_request(url, method="GET", token=token)

    if status == 200 and isinstance(data, list):
        # Exclude Pull Requests returned by the issues endpoint
        issues_only = [item for item in data if "pull_request" not in item]
        if use_cache:
            save_cached_issues(f"{owner}/{repo}", issues_only, cache_path=cache_path)
        return True, issues_only, ""

    # Resilient fallback: If GitHub returns 403 / 429 (rate limit exceeded) or 0 (offline/network error)
    if use_cache:
        cached = load_cached_issues(f"{owner}/{repo}", state=state, cache_path=cache_path)
        if cached:
            return True, cached[:limit], ""

    if status == 0:
        return False, [], f"Network / Offline error: {data.get('error', 'unknown error')}"
    else:
        err_msg = data.get("message", "Unknown error") if isinstance(data, dict) else str(data)
        return False, [], f"GitHub API error (HTTP {status}): {err_msg}"


def get_issue(
    owner: str,
    repo: str,
    issue_number: int,
    token: Optional[str] = None,
    include_comments: bool = True,
    use_cache: bool = True,
    cache_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Fetch detailed information for a single issue including its comments, with cache fallback."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    status, data, _ = make_api_request(url, method="GET", token=token)

    if status == 200 and isinstance(data, dict):
        if "pull_request" in data:
            return False, {}, f"Issue #{issue_number} is a Pull Request, not an Issue."

        if include_comments and data.get("comments", 0) > 0:
            c_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
            c_status, c_data, _ = make_api_request(c_url, method="GET", token=token)
            if c_status == 200 and isinstance(c_data, list):
                data["comments_list"] = c_data
            else:
                data["comments_list"] = []
        else:
            data["comments_list"] = []

        if use_cache:
            save_cached_issues(f"{owner}/{repo}", [data], cache_path=cache_path)
        return True, data, ""

    # Fallback to local cache if API failed (403, 0, 404, etc.)
    if use_cache:
        cached = load_cached_issues(f"{owner}/{repo}", state="all", cache_path=cache_path)
        for issue in cached:
            if issue.get("number") == issue_number:
                return True, issue, ""

    err_msg = data.get("message", "Issue not found") if isinstance(data, dict) else str(data)
    return False, {}, f"GitHub API error (HTTP {status}): {err_msg}"


def add_comment(
    owner: str,
    repo: str,
    issue_number: int,
    comment: str,
    token: Optional[str] = None,
    cache_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Add a new comment to an issue via the GitHub API and update local cache."""
    if not token:
        return (
            False,
            {},
            "Authentication required to post comments. Set GITHUB_TOKEN or GH_TOKEN environment variable.",
        )

    if not comment.strip():
        return False, {}, "Comment text cannot be empty."

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    status, data, _ = make_api_request(url, method="POST", data={"body": comment}, token=token)

    if status in (200, 201) and isinstance(data, dict):
        update_cached_issue_state(issue_number, comment=comment, cache_path=cache_path)
        return True, data, ""
    else:
        err_msg = data.get("message", "Failed to post comment") if isinstance(data, dict) else str(data)
        return False, {}, f"GitHub API error (HTTP {status}): {err_msg}"


def close_issue(
    owner: str,
    repo: str,
    issue_number: int,
    reason: str = "completed",
    comment: Optional[str] = None,
    token: Optional[str] = None,
    cache_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Close an issue on GitHub, optionally posting an explanation comment first."""
    if not token:
        return (
            False,
            {},
            "Authentication required to close issues. Set GITHUB_TOKEN or GH_TOKEN environment variable.\n"
            f"Note: Pushing a git commit with 'Fixes #{issue_number}' or 'Closes #{issue_number}' "
            "will automatically close this issue on GitHub without an API token.",
        )

    valid_reasons = {"completed", "not_planned"}
    if reason not in valid_reasons:
        return False, {}, f"Invalid close reason '{reason}'. Must be 'completed' or 'not_planned'."

    # Post optional comment first
    if comment and comment.strip():
        ok, _, err = add_comment(owner, repo, issue_number, comment.strip(), token=token, cache_path=cache_path)
        if not ok:
            return False, {}, f"Failed to post closing comment: {err}"

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    payload = {"state": "closed", "state_reason": reason}
    status, data, _ = make_api_request(url, method="PATCH", data=payload, token=token)

    if status == 200 and isinstance(data, dict):
        update_cached_issue_state(issue_number, state="closed", reason=reason, comment=comment, cache_path=cache_path)
        return True, data, ""
    else:
        err_msg = data.get("message", "Failed to close issue") if isinstance(data, dict) else str(data)
        return False, {}, f"GitHub API error (HTTP {status}): {err_msg}"


def format_issue_summary(issue: Dict[str, Any]) -> str:
    """Format an issue as a concise one-line summary."""
    num = issue.get("number", 0)
    title = issue.get("title", "Untitled")
    user = issue.get("user", {}).get("login", "unknown")
    labels = [l.get("name", "") for l in issue.get("labels", []) if isinstance(l, dict)]
    label_str = f" [{', '.join(labels)}]" if labels else ""
    return f"#{num}: {title} (@{user}){label_str}"


def format_issue_prompt(issue: Dict[str, Any], total_open: int = 1) -> str:
    """Generate structured autonomous Ralph loop instruction prompt for an open issue."""
    num = issue.get("number", 0)
    title = issue.get("title", "Untitled")
    user = issue.get("user", {}).get("login", "unknown")
    body = (issue.get("body") or "").strip()
    labels = [l.get("name", "") for l in issue.get("labels", []) if isinstance(l, dict)]
    label_str = f"Labels: {', '.join(labels)}\n" if labels else ""

    truncated_body = body[:800] + ("..." if len(body) > 800 else "") if body else "(No description provided)"

    prompt = f"""Execute one cycle of the Ralph loop per AGENTS.md.

MANDATORY PRIORITY: OPEN GITHUB ISSUE / BUG REPORT DETECTED!
Issue #{num}: "{title}"
Submitted by: @{user}
{label_str}
Description:
{truncated_body}

Total open issues in repository: {total_open}

You MUST prioritize addressing this GitHub issue in this iteration before or instead of advancing standard roadmap tasks.

Allowed Resolution Pathways:
1. Fix & Close (Bug Fixed):
   - Reproduce the bug and write hermetic regression unit test(s) in tests/test_*.py.
   - Implement the fix in the codebase.
   - Verify 100% unit tests pass (./bible test).
   - In your git commit message, include "Fixes #{num}" (GitHub will close the issue automatically on git push).
   - If GITHUB_TOKEN is available, close the issue via:
     python3 tools/github_issues.py close {num} --comment "Resolved in commit with regression test."

2. Close as Irrelevant / Duplicate / Not Planned:
   - If the issue is invalid, duplicate, out-of-scope, or already resolved:
   - Provide a clear, polite explanation and close via:
     python3 tools/github_issues.py close {num} --reason not_planned --comment "<explanation>"
   - Document the rationale in AGENT_LOG.md.

3. Comment with Diagnostic Status:
   - If the issue cannot be resolved in this iteration (e.g. requires reproduction steps from author, external credentials, or human clarification):
   - Post an explanatory comment via:
     python3 tools/github_issues.py comment {num} "<clear diagnostic reason and current status>"
   - Document the diagnostic findings in AGENT_LOG.md.

Record your triage and resolution in AGENT_LOG.md, commit, and immediately push to origin/main."""
    return prompt.strip()


def cmd_list(args: argparse.Namespace) -> int:
    """Handle 'list' subcommand."""
    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)
    force_refresh = bool(getattr(args, "refresh", False))
    use_cache = not bool(getattr(args, "no_cache", False))

    ok, issues, err = list_issues(
        owner,
        repo,
        state=args.state,
        token=token,
        limit=args.limit,
        use_cache=use_cache,
        force_refresh=force_refresh,
    )
    if not ok:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(issues, indent=2))
        return 0

    if not issues:
        print(f"No {args.state} issues found in {owner}/{repo}.")
        return 0

    print(f"\nFound {len(issues)} {args.state} issue(s) in {owner}/{repo}:")
    print("=" * 70)
    for issue in issues:
        num = issue.get("number")
        title = issue.get("title")
        user = issue.get("user", {}).get("login", "unknown")
        created = (issue.get("created_at") or "")[:10]
        comments_cnt = issue.get("comments", 0)
        labels = [l.get("name") for l in issue.get("labels", []) if isinstance(l, dict)]
        lbl_str = f" [{', '.join(labels)}]" if labels else ""
        c_str = f" ({comments_cnt} comments)" if comments_cnt else ""
        print(f"  #{num:<4} {title} (@{user}, {created}){lbl_str}{c_str}")
    print("=" * 70)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    """Handle 'view' subcommand."""
    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)
    use_cache = not bool(getattr(args, "no_cache", False))

    ok, issue, err = get_issue(
        owner,
        repo,
        args.issue_number,
        token=token,
        include_comments=True,
        use_cache=use_cache,
    )
    if not ok:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(issue, indent=2))
        return 0

    num = issue.get("number")
    title = issue.get("title")
    state = issue.get("state")
    user = issue.get("user", {}).get("login", "unknown")
    created = issue.get("created_at")
    url = issue.get("html_url")
    body = (issue.get("body") or "").strip()
    labels = [l.get("name") for l in issue.get("labels", []) if isinstance(l, dict)]

    print("=" * 72)
    print(f"Issue #{num}: {title}")
    print(f"Repository: {owner}/{repo}  │  State: {state.upper()}  │  Author: @{user}")
    print(f"Created:    {created}  │  URL: {url}")
    if labels:
        print(f"Labels:     {', '.join(labels)}")
    print("-" * 72)
    print(body if body else "(No description provided)")
    print("-" * 72)

    comments = issue.get("comments_list", [])
    if comments:
        print(f"\nComments ({len(comments)}):")
        for idx, c in enumerate(comments, 1):
            c_user = c.get("user", {}).get("login", "unknown")
            c_date = c.get("created_at", "")[:19].replace("T", " ")
            c_body = (c.get("body") or "").strip()
            print(f"\n  --- Comment #{idx} by @{c_user} on {c_date} ---")
            print(f"  {c_body}")
    print("=" * 72)
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    """Handle 'comment' subcommand."""
    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)

    ok, data, err = add_comment(owner, repo, args.issue_number, args.comment, token=token)
    if not ok:
        if not token:
            updated = update_cached_issue_state(args.issue_number, comment=args.comment)
            if updated:
                print(f"[✓] Successfully added comment to #{args.issue_number} in local cache")
                return 0
        print(f"Error: {err}", file=sys.stderr)
        return 1

    c_id = data.get("id")
    c_url = data.get("html_url")
    print(f"[✓] Successfully added comment to #{args.issue_number} (Comment ID: {c_id})")
    if c_url:
        print(f"    URL: {c_url}")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    """Handle 'close' subcommand."""
    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)

    ok, data, err = close_issue(
        owner,
        repo,
        args.issue_number,
        reason=args.reason,
        comment=args.comment,
        token=token,
    )
    if not ok:
        if not token:
            updated = update_cached_issue_state(
                args.issue_number,
                state="closed",
                reason=args.reason,
                comment=args.comment,
            )
            if updated:
                print(f"[✓] Successfully marked issue #{args.issue_number} as closed in local cache (State: closed, Reason: {args.reason})")
                print(f"    (Note: Pushing a git commit with 'Fixes #{args.issue_number}' will automatically close this issue on GitHub)")
                return 0
        print(f"Error: {err}", file=sys.stderr)
        return 1

    state = data.get("state")
    reason = data.get("state_reason")
    print(f"[✓] Successfully closed issue #{args.issue_number} (State: {state}, Reason: {reason})")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Handle 'check' subcommand for ralph.sh integration.

    Exits 0 if open issues exist, 1 if no open issues (or offline).
    """
    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)
    force_refresh = bool(getattr(args, "refresh", False))
    use_cache = not bool(getattr(args, "no_cache", False))

    ok, issues, err = list_issues(
        owner,
        repo,
        state="open",
        token=token,
        limit=10,
        use_cache=use_cache,
        force_refresh=force_refresh,
    )
    if not ok:
        if args.verbose:
            print(f"Check failed: {err}", file=sys.stderr)
        return 1

    if not issues:
        if args.verbose:
            print(f"No open issues found in {owner}/{repo}.")
        return 1

    # Open issues exist!
    oldest_issue = sorted(issues, key=lambda x: x.get("number", 0))[0]

    if args.prompt:
        prompt_text = format_issue_prompt(oldest_issue, total_open=len(issues))
        print(prompt_text)
        return 0

    if args.summary:
        print(format_issue_summary(oldest_issue))
        return 0

    if args.json:
        print(json.dumps({"open_count": len(issues), "issues": issues}, indent=2))
        return 0

    if not args.quiet:
        print(f"FOUND: {len(issues)} open issue(s) in {owner}/{repo}: {format_issue_summary(oldest_issue)}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for github_issues tool."""
    parser = argparse.ArgumentParser(
        prog="tools/github_issues.py",
        description="Bible Engine Zero-Dependency GitHub Issue Triage & Bug Resolution Engine.",
    )
    parser.add_argument("--repo", help="Target GitHub repository in 'owner/repo' format (auto-detected by default)")
    parser.add_argument("--token", help="GitHub Personal Access Token (defaults to GITHUB_TOKEN or GH_TOKEN env var)")
    parser.add_argument("--refresh", action="store_true", help="Force refresh issues from GitHub API ignoring cache")
    parser.add_argument("--no-cache", action="store_true", help="Disable reading or writing to local issues cache")

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # list
    p_list = subparsers.add_parser("list", help="List GitHub issues")
    p_list.add_argument("--state", choices=["open", "closed", "all"], default="open", help="Issue state (default: open)")
    p_list.add_argument("--limit", type=int, default=30, help="Maximum number of issues to fetch (default: 30)")
    p_list.add_argument("--json", action="store_true", help="Output raw JSON")
    p_list.add_argument("--refresh", action="store_true", help="Force refresh from API")
    p_list.add_argument("--no-cache", action="store_true", help="Disable cache")

    # view
    p_view = subparsers.add_parser("view", help="View issue details and discussion comments")
    p_view.add_argument("issue_number", type=int, help="Issue number to view")
    p_view.add_argument("--json", action="store_true", help="Output raw JSON")
    p_view.add_argument("--no-cache", action="store_true", help="Disable cache")

    # comment
    p_comment = subparsers.add_parser("comment", help="Add a comment to an issue")
    p_comment.add_argument("issue_number", type=int, help="Issue number to comment on")
    p_comment.add_argument("comment", help="Comment body text")

    # close
    p_close = subparsers.add_parser("close", help="Close a GitHub issue")
    p_close.add_argument("issue_number", type=int, help="Issue number to close")
    p_close.add_argument("--reason", choices=["completed", "not_planned"], default="completed", help="Close reason (default: completed)")
    p_close.add_argument("--comment", help="Optional closing explanation comment to post before closing")

    # check
    p_check = subparsers.add_parser("check", help="Check for open issues (designed for ralph.sh loop)")
    p_check.add_argument("--prompt", action="store_true", help="Output full Ralph prompt if open issues exist (exit 0)")
    p_check.add_argument("--summary", action="store_true", help="Output single-line summary of primary issue (exit 0)")
    p_check.add_argument("--quiet", "-q", action="store_true", help="Do not output anything, only exit code (0 if open issues, 1 if none)")
    p_check.add_argument("--json", action="store_true", help="Output JSON status")
    p_check.add_argument("--verbose", "-v", action="store_true", help="Print verbose status even if no issues found")
    p_check.add_argument("--refresh", action="store_true", help="Force refresh from API")
    p_check.add_argument("--no-cache", action="store_true", help="Disable cache")

    args = parser.parse_args(argv)

    if not args.command or args.command == "list":
        if not args.command:
            # Default to list
            args.state = "open"
            args.limit = 30
            args.json = False
        return cmd_list(args)
    elif args.command == "view":
        return cmd_view(args)
    elif args.command == "comment":
        return cmd_comment(args)
    elif args.command == "close":
        return cmd_close(args)
    elif args.command == "check":
        return cmd_check(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
