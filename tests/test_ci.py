"""Hermetic unit tests for tools/ci.py GitHub Actions query and monitoring utility.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from tools.ci import (
    check_ci_status,
    format_jobs,
    format_runs,
    get_auth_token,
    get_jobs,
    get_repo_info,
    get_runs,
    main,
    make_ci_request,
    watch_run,
)


class TestCITool(unittest.TestCase):
    """Unit tests for tools/ci.py GitHub Actions status tool."""

    def test_get_repo_info_default_and_override(self):
        # Override takes precedence
        owner, repo = get_repo_info(repo_override="custom_owner/custom_repo")
        self.assertEqual(owner, "custom_owner")
        self.assertEqual(repo, "custom_repo")

        # Invalid override falls back
        owner, repo = get_repo_info(repo_override="invalid")
        self.assertIsInstance(owner, str)
        self.assertIsInstance(repo, str)

    def test_get_auth_token(self):
        # Override takes precedence
        self.assertEqual(get_auth_token("my_token"), "my_token")

        with patch.dict("os.environ", {"GITHUB_TOKEN": "token_abc"}, clear=False):
            self.assertEqual(get_auth_token(), "token_abc")

        with patch.dict("os.environ", {"GH_TOKEN": "token_xyz"}, clear=False):
            with patch.dict("os.environ", {"GITHUB_TOKEN": ""}, clear=False):
                self.assertEqual(get_auth_token(), "token_xyz")

    @patch("urllib.request.urlopen")
    def test_make_ci_request_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"status": "ok"}).encode("utf-8")
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        status, parsed, headers = make_ci_request("https://api.github.com/test", token="sec_tok")
        self.assertEqual(status, 200)
        self.assertEqual(parsed.get("status"), "ok")

    @patch("urllib.request.urlopen")
    def test_make_ci_request_http_error(self, mock_urlopen):
        mock_err = urllib.error.HTTPError(
            url="https://api.github.com/test",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b'{"message": "Not Found"}'),
        )
        mock_urlopen.side_effect = mock_err

        status, parsed, _ = make_ci_request("https://api.github.com/test")
        self.assertEqual(status, 404)
        self.assertEqual(parsed.get("message"), "Not Found")

    @patch("tools.ci.make_ci_request")
    def test_get_runs_success(self, mock_request):
        payload = {
            "total_count": 1,
            "workflow_runs": [
                {
                    "id": 123456,
                    "head_sha": "abc1234567890",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/mrmarkwell/bible/actions/runs/123456",
                    "head_commit": {"message": "feat: test commit\nsecond line"},
                }
            ],
        }
        mock_request.return_value = (200, payload, {})

        res = get_runs(limit=5)
        self.assertIsNotNone(res)
        self.assertIn("workflow_runs", res)
        self.assertEqual(len(res["workflow_runs"]), 1)
        self.assertEqual(res["workflow_runs"][0]["id"], 123456)

    @patch("tools.ci.make_ci_request")
    def test_get_runs_network_error(self, mock_request):
        mock_request.return_value = (500, {"error": "Server Error"}, {})
        with patch("sys.stderr", new_callable=io.StringIO):
            res = get_runs(limit=2)
            self.assertIsNone(res)

    @patch("tools.ci.make_ci_request")
    def test_get_jobs_success(self, mock_request):
        payload = {
            "total_count": 1,
            "jobs": [
                {
                    "id": 789,
                    "name": "Verify & Audit (Python 3.12)",
                    "status": "completed",
                    "conclusion": "success",
                    "steps": [
                        {"name": "Set up Python", "conclusion": "success"},
                        {"name": "Run Hermetic Unit Test Suite", "conclusion": "success"},
                    ],
                }
            ],
        }
        mock_request.return_value = (200, payload, {})

        res = get_jobs("mrmarkwell", "bible", 123456)
        self.assertIsNotNone(res)
        self.assertIn("jobs", res)
        self.assertEqual(len(res["jobs"]), 1)
        self.assertEqual(res["jobs"][0]["name"], "Verify & Audit (Python 3.12)")

    @patch("tools.ci.make_ci_request")
    def test_get_jobs_network_error(self, mock_request):
        mock_request.return_value = (0, {"error": "Connection reset"}, {})
        with patch("sys.stderr", new_callable=io.StringIO):
            res = get_jobs("mrmarkwell", "bible", 123456)
            self.assertIsNone(res)

    def test_format_runs_empty(self):
        out = format_runs([], "owner", "repo")
        self.assertIn("No workflow runs found", out)

    def test_format_jobs_empty(self):
        out = format_jobs(123, {"jobs": []})
        self.assertIn("No jobs reported", out)

    @patch("tools.ci.get_runs")
    def test_main_runs_display(self, mock_get_runs):
        mock_get_runs.return_value = {
            "workflow_runs": [
                {
                    "id": 999111,
                    "head_sha": "fedcba987654",
                    "status": "completed",
                    "conclusion": "success",
                    "html_url": "https://github.com/mrmarkwell/bible/actions/runs/999111",
                    "head_commit": {"message": "docs: update manifesto"},
                },
                {
                    "id": 999222,
                    "head_sha": "123456789abc",
                    "status": "in_progress",
                    "conclusion": None,
                    "html_url": "https://github.com/mrmarkwell/bible/actions/runs/999222",
                    "head_commit": None,
                },
            ]
        }

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = main(["--limit", "2"])
            self.assertEqual(code, 0)
            out = mock_stdout.getvalue()
            self.assertIn("GitHub Actions CI Status", out)
            self.assertIn("Run #999111", out)
            self.assertIn("Run #999222", out)
            self.assertIn("docs: update manifesto", out)
            self.assertIn("fedcba9", out)

    @patch("tools.ci.get_jobs")
    @patch("tools.ci.get_runs")
    def test_main_with_details(self, mock_get_runs, mock_get_jobs):
        mock_get_runs.return_value = {
            "workflow_runs": [
                {
                    "id": 555666,
                    "head_sha": "aabbccddeeff",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/mrmarkwell/bible/actions/runs/555666",
                    "head_commit": {"message": "fix: bug in parser"},
                }
            ]
        }
        mock_get_jobs.return_value = {
            "jobs": [
                {
                    "name": "Verify & Audit (Python 3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "steps": [
                        {"name": "Checkout Repository", "conclusion": "success"},
                        {"name": "Hermetic Unit Test Suite", "conclusion": "failure"},
                        {"name": "Subsequent Step", "conclusion": "skipped"},
                    ],
                }
            ]
        }

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = main(["-d"])
            self.assertEqual(code, 0)
            out = mock_stdout.getvalue()
            self.assertIn("Detailed Jobs & Steps for Run #555666", out)
            self.assertIn("Hermetic Unit Test Suite", out)
            self.assertIn("Subsequent Step", out)

    @patch("tools.ci.get_jobs")
    @patch("tools.ci.get_runs")
    def test_main_json_output(self, mock_get_runs, mock_get_jobs):
        mock_get_runs.return_value = {
            "total_count": 1,
            "workflow_runs": [
                {
                    "id": 111222,
                    "head_sha": "abcdef123456",
                    "status": "completed",
                    "conclusion": "success",
                }
            ],
        }
        mock_get_jobs.return_value = {"jobs": [{"id": 1, "name": "test_job"}]}

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            code = main(["--json", "-d"])
            self.assertEqual(code, 0)
            parsed = json.loads(mock_stdout.getvalue())
            self.assertEqual(parsed["owner"], "mrmarkwell")
            self.assertEqual(parsed["total_count"], 1)
            self.assertEqual(len(parsed["workflow_runs"]), 1)
            self.assertEqual(len(parsed["latest_jobs"]), 1)

    @patch("tools.ci.get_runs")
    def test_main_no_runs_exits(self, mock_get_runs):
        mock_get_runs.return_value = None
        with patch("sys.stderr", new_callable=io.StringIO):
            code = main([])
            self.assertEqual(code, 1)

    @patch("tools.ci.get_jobs")
    @patch("tools.ci.make_ci_request")
    def test_watch_run_completed_success(self, mock_req, mock_jobs):
        mock_req.return_value = (
            200,
            {"id": 444, "status": "completed", "conclusion": "success"},
            {},
        )
        mock_jobs.return_value = {"jobs": []}

        with patch("sys.stdout", new_callable=io.StringIO):
            code = watch_run("mrmarkwell", "bible", 444, interval=0.01, max_wait_seconds=1.0)
            self.assertEqual(code, 0)

    @patch("tools.ci.make_ci_request")
    def test_watch_run_timeout(self, mock_req):
        mock_req.return_value = (
            200,
            {"id": 444, "status": "in_progress", "conclusion": None},
            {},
        )

        with patch("sys.stderr", new_callable=io.StringIO), patch("sys.stdout", new_callable=io.StringIO):
            code = watch_run("mrmarkwell", "bible", 444, interval=0.01, max_wait_seconds=0.03)
            self.assertEqual(code, 1)

    @patch("tools.ci.get_runs")
    def test_check_ci_status_success(self, mock_get_runs):
        mock_get_runs.return_value = {
            "workflow_runs": [
                {
                    "id": 999,
                    "head_sha": "abc1234",
                    "status": "completed",
                    "conclusion": "success",
                    "head_branch": "main",
                    "head_commit": {"message": "feat: great feature"},
                }
            ]
        }
        healthy, message, latest = check_ci_status("mrmarkwell", "bible")
        self.assertTrue(healthy)
        self.assertIn("HEALTHY", message)
        self.assertEqual(latest["id"], 999)

    @patch("tools.ci.get_runs")
    def test_check_ci_status_failure(self, mock_get_runs):
        mock_get_runs.return_value = {
            "workflow_runs": [
                {
                    "id": 888,
                    "head_sha": "def5678",
                    "status": "completed",
                    "conclusion": "failure",
                    "head_branch": "main",
                    "head_commit": {"message": "fix: broken test"},
                }
            ]
        }
        healthy, message, latest = check_ci_status("mrmarkwell", "bible")
        self.assertFalse(healthy)
        self.assertIn("FAILING", message)
        self.assertEqual(latest["id"], 888)

    @patch("tools.ci.get_runs")
    def test_check_ci_status_offline_fallback(self, mock_get_runs):
        mock_get_runs.return_value = None
        healthy, message, latest = check_ci_status("mrmarkwell", "bible")
        self.assertTrue(healthy)
        self.assertIn("offline", message)
        self.assertIsNone(latest)

    @patch("tools.ci.get_runs")
    def test_main_check_success_and_failure(self, mock_get_runs):
        # Success scenario
        mock_get_runs.return_value = {
            "workflow_runs": [
                {"id": 1, "head_sha": "aaa", "status": "completed", "conclusion": "success", "display_title": "ci pass"}
            ]
        }
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["check"])
            self.assertEqual(code, 0)
            self.assertIn("HEALTHY", mock_out.getvalue())

        # Failure scenario
        mock_get_runs.return_value = {
            "workflow_runs": [
                {"id": 2, "head_sha": "bbb", "status": "completed", "conclusion": "failure", "display_title": "ci fail"}
            ]
        }
        with patch("sys.stderr", new_callable=io.StringIO) as mock_err:
            code = main(["--check"])
            self.assertEqual(code, 1)
            self.assertIn("FAILING", mock_err.getvalue())

    @patch("tools.ci.get_runs")
    def test_main_check_prompt_and_summary(self, mock_get_runs):
        # Failing CI emits prompt with instructions
        mock_get_runs.return_value = {
            "workflow_runs": [
                {"id": 3, "head_sha": "ccc", "status": "completed", "conclusion": "failure", "display_title": "bug"}
            ]
        }
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["check", "--prompt"])
            self.assertEqual(code, 0)
            self.assertIn("FAILING", mock_out.getvalue())
            self.assertIn("top priority per AGENTS.md", mock_out.getvalue())

        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["check", "--summary"])
            self.assertEqual(code, 0)
            self.assertIn("FAILING", mock_out.getvalue())

        # Passing CI emits nothing and returns 1 (no prompt needed)
        mock_get_runs.return_value = {
            "workflow_runs": [
                {"id": 4, "head_sha": "ddd", "status": "completed", "conclusion": "success", "display_title": "pass"}
            ]
        }
        with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["check", "--prompt"])
            self.assertEqual(code, 1)
            self.assertEqual(mock_out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()


