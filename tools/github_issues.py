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
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
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
    """Retrieve GitHub API personal access token from override or environment."""
    if token_override and token_override.strip():
        return token_override.strip()
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None


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
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """Fetch issues from GitHub API, filtering out pull requests."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state={url_parse.quote(state)}&per_page={limit}"
    status, data, _ = make_api_request(url, method="GET", token=token)

    if status == 200 and isinstance(data, list):
        # Exclude Pull Requests returned by the issues endpoint
        issues_only = [item for item in data if "pull_request" not in item]
        return True, issues_only, ""
    elif status == 0:
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
) -> Tuple[bool, Dict[str, Any], str]:
    """Fetch detailed information for a single issue including its comments."""
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    status, data, _ = make_api_request(url, method="GET", token=token)

    if status != 200 or not isinstance(data, dict):
        err_msg = data.get("message", "Issue not found") if isinstance(data, dict) else str(data)
        return False, {}, f"GitHub API error (HTTP {status}): {err_msg}"

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

    return True, data, ""


def add_comment(
    owner: str,
    repo: str,
    issue_number: int,
    comment: str,
    token: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Add a new comment to an issue via the GitHub API."""
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
        ok, _, err = add_comment(owner, repo, issue_number, comment.strip(), token=token)
        if not ok:
            return False, {}, f"Failed to post closing comment: {err}"

    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
    payload = {"state": "closed", "state_reason": reason}
    status, data, _ = make_api_request(url, method="PATCH", data=payload, token=token)

    if status == 200 and isinstance(data, dict):
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

    ok, issues, err = list_issues(owner, repo, state=args.state, token=token, limit=args.limit)
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

    ok, issue, err = get_issue(owner, repo, args.issue_number, token=token, include_comments=True)
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

    ok, issues, err = list_issues(owner, repo, state="open", token=token, limit=10)
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

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # list
    p_list = subparsers.add_parser("list", help="List GitHub issues")
    p_list.add_argument("--state", choices=["open", "closed", "all"], default="open", help="Issue state (default: open)")
    p_list.add_argument("--limit", type=int, default=30, help="Maximum number of issues to fetch (default: 30)")
    p_list.add_argument("--json", action="store_true", help="Output raw JSON")

    # view
    p_view = subparsers.add_parser("view", help="View issue details and discussion comments")
    p_view.add_argument("issue_number", type=int, help="Issue number to view")
    p_view.add_argument("--json", action="store_true", help="Output raw JSON")

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
