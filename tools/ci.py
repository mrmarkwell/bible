#!/usr/bin/env python3
"""Sovereign Zero-Dependency GitHub Actions CI Status & Monitoring Engine.

Zero-dependency tool (Python 3 standard library only per ADR-003):
- Interrogates the GitHub Actions REST API using urllib.request and json.
- Automatically detects GitHub repository from git remote origin URL.
- Supports authenticated requests via GITHUB_TOKEN or GH_TOKEN (5,000 req/hr rate limit).
- Displays workflow runs across branches with status icons and commit metadata.
- Drills down into individual job matrix steps (Python 3.10, 3.11, 3.12, 3.13).
- Real-time watch/polling mode (--watch) to monitor in-progress runs after push.
- Machine-readable JSON output (--json) for autonomous agents and tooling.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
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


def make_ci_request(
    url: str,
    token: Optional[str] = None,
    timeout: float = 15.0,
) -> Tuple[int, Any, Dict[str, str]]:
    """Execute an HTTP GET request to the GitHub Actions REST API using stdlib urllib."""
    headers = {
        "User-Agent": "Bible-Engine-CI/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = url_request.Request(url, headers=headers, method="GET")

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
    except url_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return exc.code, parsed, dict(exc.headers)
    except Exception as exc:
        return 0, {"error": str(exc)}, {}


def get_runs(
    owner: str = "mrmarkwell",
    repo: str = "bible",
    limit: int = 5,
    branch: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve recent GitHub Actions workflow runs for the specified repository."""
    params: Dict[str, str] = {"per_page": str(max(1, min(100, limit)))}
    if branch:
        params["branch"] = branch

    query_str = url_parse.urlencode(params)
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?{query_str}"
    status, data, _ = make_ci_request(url, token=token)

    if status != 200:
        err = data.get("message") or data.get("error") or f"HTTP status {status}"
        print(f"Error fetching GitHub Actions status: {err}", file=sys.stderr)
        return None

    return data


def get_jobs(
    owner: str = "mrmarkwell",
    repo: str = "bible",
    run_id: int | str = 0,
    token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve detailed jobs and matrix steps for a specific workflow run."""
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
    status, data, _ = make_ci_request(url, token=token)

    if status != 200:
        err = data.get("message") or data.get("error") or f"HTTP status {status}"
        print(f"Error fetching jobs for run {run_id}: {err}", file=sys.stderr)
        return None

    return data


def get_annotations(
    owner: str = "mrmarkwell",
    repo: str = "bible",
    job_id: int | str = 0,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve check-run annotations for a specific job from GitHub Actions REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/check-runs/{job_id}/annotations"
    status, data, _ = make_ci_request(url, token=token)
    if status == 200 and isinstance(data, list):
        return data
    return []


def format_runs(
    runs: List[Dict[str, Any]],
    owner: str,
    repo: str,
    title: Optional[str] = None,
) -> str:
    """Format workflow runs into human-readable terminal text."""
    lines = [
        "=" * 72,
        f" {title or 'GitHub Actions CI Status'}: {owner}/{repo}",
        "=" * 72,
    ]
    if not runs:
        lines.append(" No workflow runs found.")
        return "\n".join(lines)

    for r in runs:
        sha = (r.get("head_sha") or "unknown")[:7]
        msg = (
            r.get("head_commit", {}).get("message", "N/A").splitlines()[0]
            if r.get("head_commit")
            else r.get("display_title", "N/A")
        )
        status = r.get("status", "unknown")
        conclusion = r.get("conclusion") or "in_progress"
        icon = "✅" if conclusion == "success" else ("❌" if conclusion == "failure" else "⏳")
        branch = r.get("head_branch") or "main"
        lines.append(f" {icon} Run #{r.get('id')} [{status}/{conclusion}] (branch: {branch})")
        lines.append(f"    Commit: {sha} - \"{msg}\"")
        lines.append(f"    URL:    {r.get('html_url', '')}")
        lines.append("")

    return "\n".join(lines)


def format_jobs(
    run_id: int | str,
    jobs_data: Dict[str, Any],
    owner: str = "mrmarkwell",
    repo: str = "bible",
    token: Optional[str] = None,
) -> str:
    """Format job matrix and step details into human-readable terminal text."""
    lines = [
        "-" * 72,
        f" Detailed Jobs & Steps for Run #{run_id}:",
        "-" * 72,
    ]
    jobs = jobs_data.get("jobs", [])
    if not jobs:
        lines.append("  No jobs reported.")
        return "\n".join(lines)

    for j in jobs:
        conclusion = j.get("conclusion") or j.get("status", "unknown")
        j_icon = "✅" if conclusion == "success" else ("❌" if conclusion == "failure" else "⏳")
        name = j.get("name", "job")
        status = j.get("status", "unknown")
        lines.append(f"  {j_icon} {name}: {status} ({conclusion})")
        for s in j.get("steps", []):
            s_conc = s.get("conclusion") or s.get("status")
            s_icon = "✓" if s_conc == "success" else ("✗" if s_conc == "failure" else "○")
            s_name = s.get("name", "step")
            lines.append(f"     [{s_icon}] {s_name}")

        if conclusion == "failure" and j.get("id"):
            annotations = get_annotations(owner, repo, j.get("id"), token=token)
            failures = [a for a in annotations if a.get("annotation_level") in ("failure", "warning")]
            if failures:
                lines.append("     Failure Diagnostics & Workflow Annotations:")
                for a in failures:
                    path = a.get("path") or "general"
                    title = a.get("title") or a.get("annotation_level", "error")
                    msg = a.get("message", "").strip()
                    lines.append(f"       • [{a.get('annotation_level')}] {path} ({title}):")
                    for m_line in msg.splitlines():
                        lines.append(f"           {m_line}")
    lines.append("")
    return "\n".join(lines)


def watch_run(
    owner: str,
    repo: str,
    run_id: int | str,
    token: Optional[str] = None,
    interval: float = 6.0,
    max_wait_seconds: float = 600.0,
    json_output: bool = False,
) -> int:
    """Poll an in-progress workflow run until it completes or reaches timeout."""
    start_time = time.time()
    if not json_output:
        print(f"[*] Watching GitHub Actions Run #{run_id} in {owner}/{repo} (polling every {interval:.0f}s)...")

    while time.time() - start_time < max_wait_seconds:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
        status_code, run_data, _ = make_ci_request(url, token=token)
        if status_code != 200:
            err = run_data.get("message") or run_data.get("error") or f"HTTP {status_code}"
            if json_output:
                print(json.dumps({"error": err, "run_id": run_id}))
            else:
                print(f"Error checking run #{run_id}: {err}", file=sys.stderr)
            return 1

        run_status = run_data.get("status")
        conclusion = run_data.get("conclusion")

        if run_status == "completed":
            if json_output:
                jobs_data = get_jobs(owner, repo, run_id, token=token) or {}
                print(json.dumps({"run": run_data, "jobs": jobs_data.get("jobs", [])}, indent=2))
            else:
                icon = "✅" if conclusion == "success" else "❌"
                elapsed = time.time() - start_time
                print(f"\n{icon} Run #{run_id} completed in {elapsed:.1f}s: {conclusion.upper()}")
                jobs_data = get_jobs(owner, repo, run_id, token=token)
                if jobs_data:
                    print(format_jobs(run_id, jobs_data, owner=owner, repo=repo, token=token))
            return 0 if conclusion == "success" else 1

        if not json_output:
            elapsed = time.time() - start_time
            print(f"  ... Run #{run_id} still {run_status} ({elapsed:.0f}s elapsed)")
        time.sleep(interval)

    msg = f"Timed out waiting for run #{run_id} after {max_wait_seconds:.0f}s."
    if json_output:
        print(json.dumps({"error": msg, "run_id": run_id}))
    else:
        print(f"\n[!] {msg}", file=sys.stderr)
    return 1


def check_ci_status(
    owner: str = "mrmarkwell",
    repo: str = "bible",
    branch: Optional[str] = "main",
    token: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Inspect the latest completed CI run on the target branch.

    Returns:
        Tuple of (healthy: bool, message: str, latest_run: Optional[Dict[str, Any]]).
        healthy is False if the latest completed run failed.
        healthy is True if the latest completed run succeeded or if offline/unreachable.
    """
    data = get_runs(owner, repo, limit=5, branch=branch, token=token)
    if not data or "workflow_runs" not in data:
        return True, "Could not reach GitHub Actions API (offline or rate limited). Proceeding with local verification.", None

    runs = data.get("workflow_runs", [])
    if not runs:
        return True, f"No GitHub Actions workflow runs found for {owner}/{repo} (branch: {branch or 'all'}).", None

    # Find the most recent completed run
    completed_run = next((r for r in runs if r.get("status") == "completed"), runs[0])

    run_id = completed_run.get("id")
    conclusion = completed_run.get("conclusion")
    status = completed_run.get("status")
    sha = (completed_run.get("head_sha") or "unknown")[:7]
    msg = (
        completed_run.get("head_commit", {}).get("message", "N/A").splitlines()[0]
        if completed_run.get("head_commit")
        else completed_run.get("display_title", "N/A")
    )
    branch_name = completed_run.get("head_branch") or branch or "main"

    if conclusion == "failure":
        return False, f"GitHub Actions CI is FAILING on {branch_name} (Run #{run_id} [{conclusion}], commit {sha}: \"{msg}\")", completed_run
    elif conclusion == "success":
        return True, f"GitHub Actions CI is HEALTHY on {branch_name} (Run #{run_id} [{conclusion}], commit {sha}: \"{msg}\")", completed_run
    else:
        return True, f"GitHub Actions CI is {status} on {branch_name} (Run #{run_id} [{conclusion or status}], commit {sha}: \"{msg}\")", completed_run


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for sovereign CI status and monitoring tool."""
    parser = argparse.ArgumentParser(
        prog="tools/ci.py",
        description="Bible Engine Sovereign Zero-Dependency GitHub Actions CI Status & Monitoring Engine.",
    )
    parser.add_argument("action", nargs="?", default="status", choices=["status", "check", "watch"], help="Action to execute ('status', 'check', 'watch')")
    parser.add_argument("--check", "-c", action="store_true", help="Pre-flight health check: exit with code 1 if latest CI run failed")
    parser.add_argument("--repo", "-r", help="Target repository in 'owner/repo' format (auto-detected from git)")
    parser.add_argument("--token", "-t", help="GitHub Personal Access Token (defaults to GITHUB_TOKEN or GH_TOKEN)")
    parser.add_argument("--branch", "-b", help="Filter workflow runs by branch (e.g. main)")
    parser.add_argument("--limit", "-n", type=int, default=5, help="Number of workflow runs to fetch (default: 5)")
    parser.add_argument("--details", "-d", action="store_true", help="Show detailed job matrix steps for latest run")
    parser.add_argument("--run-id", type=int, help="Specific workflow run ID to inspect or watch")
    parser.add_argument("--watch", "-w", action="store_true", help="Continuously monitor latest or specified run until complete")
    parser.add_argument("--interval", type=float, default=6.0, help="Polling interval in seconds for --watch (default: 6.0)")
    parser.add_argument("--prompt", action="store_true", help="Emit instructions prompt for autonomous agent loop if CI is failing")
    parser.add_argument("--summary", action="store_true", help="Emit one-line summary if CI is failing")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args(argv)

    owner, repo = get_repo_info(args.repo)
    token = get_auth_token(args.token)

    # Pre-flight check mode (either --check flag, 'check' positional action, or --prompt/--summary)
    if args.check or args.action == "check" or args.prompt or args.summary:
        healthy, message, latest = check_ci_status(owner, repo, branch=args.branch or "main", token=token)
        if args.prompt:
            if not healthy:
                print(
                    f"GitHub Actions CI/CD is currently FAILING on origin/main ({message}). "
                    f"As top priority per AGENTS.md, diagnose and fix the broken CI/CD pipeline on GitHub "
                    f"before addressing GitHub issues or roadmap tasks. Verify hermetic tests pass across "
                    f"all Python matrix versions and push to origin/main immediately."
                )
                return 0
            return 1

        if args.summary:
            if not healthy:
                print(message)
                return 0
            return 1

        if args.json:
            payload = {
                "healthy": healthy,
                "message": message,
                "owner": owner,
                "repo": repo,
                "latest_run": latest,
            }
            print(json.dumps(payload, indent=2))
        else:
            icon = "✅" if healthy else "❌"
            if healthy:
                print(f"{icon} {message}")
            else:
                print(f"{icon} {message}", file=sys.stderr)
        return 0 if healthy else 1

    # Watch mode for specific run ID
    if (args.watch or args.action == "watch") and args.run_id:
        return watch_run(
            owner,
            repo,
            args.run_id,
            token=token,
            interval=args.interval,
            json_output=args.json,
        )

    # Fetch workflow runs
    data = get_runs(owner, repo, limit=args.limit, branch=args.branch, token=token)
    if not data or "workflow_runs" not in data:
        if args.json:
            print(json.dumps({"error": "Could not retrieve workflow runs", "owner": owner, "repo": repo}))
        else:
            print(f"Could not retrieve workflow runs for {owner}/{repo}.", file=sys.stderr)
        return 1

    runs = data.get("workflow_runs", [])

    if args.watch and runs:
        latest_id = runs[0].get("id")
        return watch_run(
            owner,
            repo,
            latest_id,
            token=token,
            interval=args.interval,
            json_output=args.json,
        )

    if args.json:
        payload: Dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "total_count": data.get("total_count", len(runs)),
            "workflow_runs": runs,
        }
        if args.details and runs:
            latest = runs[0]
            jobs_data = get_jobs(owner, repo, latest.get("id"), token=token)
            payload["latest_jobs"] = jobs_data.get("jobs", []) if jobs_data else []
        print(json.dumps(payload, indent=2))
        return 0

    # Human-readable text display
    print(format_runs(runs, owner, repo))

    if (args.details or args.run_id) and runs:
        target_id = args.run_id or runs[0].get("id")
        jobs_data = get_jobs(owner, repo, target_id, token=token)
        if jobs_data:
            print(format_jobs(target_id, jobs_data, owner=owner, repo=repo, token=token))

    return 0


if __name__ == "__main__":
    sys.exit(main())

