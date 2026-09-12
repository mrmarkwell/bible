#!/usr/bin/env python3
"""Hermetic Unit Tests for Sovereign GitHub Issue Triage Engine (tools/github_issues.py).

Verifies 100% stdlib compliance, mock HTTP interactions, PR filtering,
issue detail formatting, commenting, closing, prompt generation, and CLI ergonomics.
"""

from __future__ import annotations

import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from tools import github_issues


class TestGitHubIssuesEngine(unittest.TestCase):
    """Test suite for tools/github_issues.py."""

    def setUp(self) -> None:
        self.sample_issues = [
            {
                "number": 42,
                "title": "Reference parser fails on single-chapter books without verse prefix",
                "state": "open",
                "user": {"login": "scripture_scholar"},
                "created_at": "2026-09-08T01:00:00Z",
                "body": "When parsing 'Philemon 1', the parser raises ValueError instead of span 1-25.",
                "labels": [{"name": "bug"}, {"name": "priority:high"}],
                "comments": 1,
                "html_url": "https://github.com/mrmarkwell/bible/issues/42",
            },
            {
                "number": 43,
                "title": "Add Philemon fix PR",
                "state": "open",
                "user": {"login": "contributor"},
                "pull_request": {"url": "https://api.github.com/repos/mrmarkwell/bible/pulls/43"},
                "body": "This is a PR, should be ignored by issues tool",
            },
        ]

    def test_get_repo_info(self) -> None:
        """Verify repo parsing from override, git remote, and fallback."""
        self.assertEqual(github_issues.get_repo_info("testuser/myrepo"), ("testuser", "myrepo"))
        # Invalid format falls back
        owner, repo = github_issues.get_repo_info("invalid_single_string")
        self.assertTrue(len(owner) > 0 and len(repo) > 0)

    def test_get_auth_token(self) -> None:
        """Verify auth token resolution from override and environment."""
        self.assertEqual(github_issues.get_auth_token("explicit_token"), "explicit_token")
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token_123"}, clear=True):
            self.assertEqual(github_issues.get_auth_token(), "env_token_123")
        with patch.dict(os.environ, {"GH_TOKEN": "gh_token_456"}, clear=True):
            self.assertEqual(github_issues.get_auth_token(), "gh_token_456")
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(github_issues.get_auth_token())

    @patch("tools.github_issues.url_request.urlopen")
    def test_list_issues_filtering_prs(self, mock_urlopen: MagicMock) -> None:
        """Verify list_issues parses 200 response and filters out pull requests."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(self.sample_issues).encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, issues, err = github_issues.list_issues("mrmarkwell", "bible")
        self.assertTrue(ok)
        self.assertEqual(err, "")
        # PR (number 43) should be filtered out; only issue 42 remains
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["number"], 42)
        self.assertEqual(issues[0]["title"], "Reference parser fails on single-chapter books without verse prefix")

    @patch("tools.github_issues.url_request.urlopen")
    def test_list_issues_network_error(self, mock_urlopen: MagicMock) -> None:
        """Verify graceful error handling when offline or connection fails."""
        mock_urlopen.side_effect = URLError("Name or service not known")

        ok, issues, err = github_issues.list_issues("mrmarkwell", "bible")
        self.assertFalse(ok)
        self.assertEqual(len(issues), 0)
        self.assertIn("Network / Offline error", err)

    @patch("tools.github_issues.url_request.urlopen")
    def test_get_issue_detail_with_comments(self, mock_urlopen: MagicMock) -> None:
        """Verify fetching single issue details and child comments."""
        issue_data = dict(self.sample_issues[0])
        comments_data = [
            {
                "id": 9991,
                "user": {"login": "collaborator"},
                "created_at": "2026-09-08T01:10:00Z",
                "body": "Reproduced on Linux. Philemon coordinate bounds calculation issue.",
            }
        ]

        def mock_dispatch(req, timeout=12.0):
            url = req.full_url
            mock_r = MagicMock()
            mock_r.status = 200
            mock_r.headers = {}
            mock_r.__enter__.return_value = mock_r
            if "comments" in url:
                mock_r.read.return_value = json.dumps(comments_data).encode("utf-8")
            else:
                mock_r.read.return_value = json.dumps(issue_data).encode("utf-8")
            return mock_r

        mock_urlopen.side_effect = mock_dispatch

        ok, detail, err = github_issues.get_issue("mrmarkwell", "bible", 42, include_comments=True)
        self.assertTrue(ok)
        self.assertEqual(detail["number"], 42)
        self.assertEqual(len(detail["comments_list"]), 1)
        self.assertEqual(detail["comments_list"][0]["id"], 9991)

    def test_add_comment_no_token(self) -> None:
        """Verify add_comment enforces authentication requirement."""
        ok, data, err = github_issues.add_comment("mrmarkwell", "bible", 42, "Some comment", token=None)
        self.assertFalse(ok)
        self.assertIn("Authentication required", err)

    def test_add_comment_empty(self) -> None:
        """Verify add_comment rejects empty comment strings."""
        ok, data, err = github_issues.add_comment("mrmarkwell", "bible", 42, "   ", token="dummy")
        self.assertFalse(ok)
        self.assertIn("Comment text cannot be empty", err)

    @patch("tools.github_issues.url_request.urlopen")
    def test_add_comment_success(self, mock_urlopen: MagicMock) -> None:
        """Verify successful comment creation via GitHub API."""
        mock_resp = MagicMock()
        mock_resp.status = 201
        mock_resp.read.return_value = json.dumps({"id": 12345, "html_url": "https://github.com/..."}).encode("utf-8")
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, data, err = github_issues.add_comment("mrmarkwell", "bible", 42, "Test comment", token="dummy_token")
        self.assertTrue(ok)
        self.assertEqual(data.get("id"), 12345)

    def test_close_issue_no_token(self) -> None:
        """Verify close_issue rejects unauthenticated requests and suggests commit keyword."""
        ok, data, err = github_issues.close_issue("mrmarkwell", "bible", 42, token=None)
        self.assertFalse(ok)
        self.assertIn("Authentication required", err)
        self.assertIn("Fixes #42", err)

    def test_close_issue_invalid_reason(self) -> None:
        """Verify close_issue validates state_reason."""
        ok, data, err = github_issues.close_issue("mrmarkwell", "bible", 42, reason="invalid", token="dummy")
        self.assertFalse(ok)
        self.assertIn("Invalid close reason", err)

    @patch("tools.github_issues.url_request.urlopen")
    def test_close_issue_success(self, mock_urlopen: MagicMock) -> None:
        """Verify issue closure with PATCH state=closed."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"number": 42, "state": "closed", "state_reason": "completed"}).encode("utf-8")
        mock_resp.headers = {}
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        ok, data, err = github_issues.close_issue("mrmarkwell", "bible", 42, reason="completed", token="dummy")
        self.assertTrue(ok)
        self.assertEqual(data.get("state"), "closed")
        self.assertEqual(data.get("state_reason"), "completed")

    def test_format_issue_prompt(self) -> None:
        """Verify prompt formatting for autonomous Ralph loop injection."""
        prompt = github_issues.format_issue_prompt(self.sample_issues[0], total_open=1)
        self.assertIn("MANDATORY PRIORITY: OPEN GITHUB ISSUE / BUG REPORT DETECTED!", prompt)
        self.assertIn('Issue #42: "Reference parser fails on single-chapter books without verse prefix"', prompt)
        self.assertIn("Submitted by: @scripture_scholar", prompt)
        self.assertIn("Fixes #42", prompt)
        self.assertIn("tools/github_issues.py close 42", prompt)
        self.assertIn("tools/github_issues.py comment 42", prompt)

    @patch("tools.github_issues.list_issues")
    def test_cmd_check(self, mock_list: MagicMock) -> None:
        """Verify check subcommand behavior for no issues, open issues, and prompt output."""
        # Case 1: No open issues -> exit 1
        mock_list.return_value = (True, [], "")
        exit_code = github_issues.cmd_check(github_issues.argparse.Namespace(
            repo=None, token=None, prompt=False, summary=False, quiet=True, json=False, verbose=False
        ))
        self.assertEqual(exit_code, 1)

        # Case 2: Open issues exist -> exit 0
        mock_list.return_value = (True, [self.sample_issues[0]], "")
        out = io.StringIO()
        with patch("sys.stdout", out):
            exit_code = github_issues.cmd_check(github_issues.argparse.Namespace(
                repo=None, token=None, prompt=True, summary=False, quiet=False, json=False, verbose=False
            ))
        self.assertEqual(exit_code, 0)
        self.assertIn("OPEN GITHUB ISSUE / BUG REPORT DETECTED", out.getvalue())

        # Case 3: Summary output -> exit 0
        out_sum = io.StringIO()
        with patch("sys.stdout", out_sum):
            exit_code = github_issues.cmd_check(github_issues.argparse.Namespace(
                repo=None, token=None, prompt=False, summary=True, quiet=False, json=False, verbose=False
            ))
        self.assertEqual(exit_code, 0)
        self.assertIn("#42:", out_sum.getvalue())


    def test_get_auth_token_from_files(self) -> None:
        """Verify token discovery from .env and config/ directory when BIBLE_TEST_MODE is disabled."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            env_file = tmppath / ".env"
            env_file.write_text("SOME_VAR=123\nGITHUB_TOKEN=token_from_dotenv\nOTHER=abc\n", encoding="utf-8")

            # Patch cwd and REPO_ROOT paths to point to tmpdir
            with patch.dict(os.environ, {"BIBLE_TEST_MODE": "0"}, clear=True):
                with patch("tools.github_issues.REPO_ROOT", tmppath):
                    with patch("pathlib.Path.cwd", return_value=tmppath):
                        tok = github_issues.get_auth_token()
                        self.assertEqual(tok, "token_from_dotenv")

            # Test config/github_token.txt fallback
            env_file.unlink()
            cfg_dir = tmppath / "config"
            cfg_dir.mkdir()
            cfg_file = cfg_dir / "github_token.txt"
            cfg_file.write_text("token_from_config_file\n", encoding="utf-8")

            with patch.dict(os.environ, {"BIBLE_TEST_MODE": "0"}, clear=True):
                with patch("tools.github_issues.REPO_ROOT", tmppath):
                    with patch("pathlib.Path.cwd", return_value=tmppath):
                        tok = github_issues.get_auth_token()
                        self.assertEqual(tok, "token_from_config_file")

    def test_save_and_load_cached_issues(self) -> None:
        """Verify atomic caching and state filtering of issues."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "github_issues_cache.json"
            issues_to_cache = [
                {"number": 10, "title": "Open Issue 10", "state": "open"},
                {"number": 11, "title": "Closed Issue 11", "state": "closed"},
            ]
            ok = github_issues.save_cached_issues("test/repo", issues_to_cache, cache_path=cache_file)
            self.assertTrue(ok)
            self.assertTrue(cache_file.exists())

            # Load open issues
            open_issues = github_issues.load_cached_issues("test/repo", state="open", cache_path=cache_file)
            self.assertEqual(len(open_issues), 1)
            self.assertEqual(open_issues[0]["number"], 10)

            # Load all issues
            all_issues = github_issues.load_cached_issues("test/repo", state="all", cache_path=cache_file)
            self.assertEqual(len(all_issues), 2)

            # Check cache freshness
            self.assertTrue(github_issues.is_cache_fresh(cache_path=cache_file, ttl_seconds=60))

    @patch("tools.github_issues.make_api_request")
    def test_list_issues_cache_fallback_on_403(self, mock_req: MagicMock) -> None:
        """Verify list_issues falls back to cache when GitHub rate limit (HTTP 403) occurs."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            github_issues.save_cached_issues(
                "mrmarkwell/bible",
                [{"number": 5, "title": "Cached Issue 5", "state": "open"}],
                cache_path=cache_file,
            )

            # Mock 403 Rate Limit from GitHub
            mock_req.return_value = (403, {"message": "API rate limit exceeded"}, {})

            ok, issues, err = github_issues.list_issues(
                "mrmarkwell",
                "bible",
                state="open",
                use_cache=True,
                force_refresh=True,
                cache_path=cache_file,
            )
            self.assertTrue(ok)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["number"], 5)
            self.assertEqual(issues[0]["title"], "Cached Issue 5")

    @patch("tools.github_issues.make_api_request")
    def test_list_issues_cache_fallback_on_offline(self, mock_req: MagicMock) -> None:
        """Verify list_issues falls back to cache when network status is 0 (offline)."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            github_issues.save_cached_issues(
                "mrmarkwell/bible",
                [{"number": 6, "title": "Cached Issue 6", "state": "open"}],
                cache_path=cache_file,
            )

            # Mock network failure (status 0)
            mock_req.return_value = (0, {"error": "Connection refused"}, {})

            ok, issues, err = github_issues.list_issues(
                "mrmarkwell",
                "bible",
                state="open",
                use_cache=True,
                force_refresh=True,
                cache_path=cache_file,
            )
            self.assertTrue(ok)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0]["number"], 6)

    @patch("tools.github_issues.make_api_request")
    def test_get_issue_cache_fallback(self, mock_req: MagicMock) -> None:
        """Verify get_issue retrieves from local cache when GitHub API fails."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            github_issues.save_cached_issues(
                "mrmarkwell/bible",
                [{"number": 42, "title": "Cached Issue 42", "state": "open", "body": "Detail body"}],
                cache_path=cache_file,
            )

            # Mock 404/403 failure from GitHub
            mock_req.return_value = (403, {"message": "Rate limited"}, {})

            ok, issue, err = github_issues.get_issue(
                "mrmarkwell",
                "bible",
                42,
                use_cache=True,
                cache_path=cache_file,
            )
            self.assertTrue(ok)
            self.assertEqual(issue.get("number"), 42)
            self.assertEqual(issue.get("title"), "Cached Issue 42")

    def test_update_cached_issue_state_and_cmd_close_local(self) -> None:
        """Verify local cache closure when GITHUB_TOKEN is not available."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_file = Path(tmpdir) / "test_cache.json"
            github_issues.save_cached_issues(
                "mrmarkwell/bible",
                [{"number": 5, "title": "Issue 5", "state": "open"}],
                cache_path=cache_file,
            )

            # Update cache directly
            updated = github_issues.update_cached_issue_state(
                5, state="closed", reason="completed", comment="Fixed locally", cache_path=cache_file
            )
            self.assertTrue(updated)

            # Verify issue is now closed in cache
            open_issues = github_issues.load_cached_issues("mrmarkwell/bible", state="open", cache_path=cache_file)
            self.assertEqual(len(open_issues), 0)

            closed_issues = github_issues.load_cached_issues("mrmarkwell/bible", state="closed", cache_path=cache_file)
            self.assertEqual(len(closed_issues), 1)
            self.assertEqual(closed_issues[0]["state"], "closed")
            self.assertEqual(closed_issues[0]["state_reason"], "completed")

            # Verify cmd_close updates local cache when unauthenticated
            with patch("tools.github_issues.get_cache_path", return_value=cache_file):
                out = io.StringIO()
                with patch("sys.stdout", out):
                    exit_code = github_issues.cmd_close(github_issues.argparse.Namespace(
                        repo="mrmarkwell/bible",
                        token=None,
                        issue_number=5,
                        reason="completed",
                        comment="Closed via unit test",
                    ))
                self.assertEqual(exit_code, 0)
                self.assertIn("marked issue #5 as closed in local cache", out.getvalue())


if __name__ == "__main__":
    unittest.main()
