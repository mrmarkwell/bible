"""Hermetic unit tests for tools/ci.py GitHub Actions query utility.

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from tools.ci import get_runs, get_jobs, main


class TestCITool(unittest.TestCase):
    """Unit tests for tools/ci.py GitHub Actions status tool."""

    @patch("urllib.request.urlopen")
    def test_get_runs_success(self, mock_urlopen):
        mock_response = MagicMock()
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
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = get_runs(limit=5)
        self.assertIsNotNone(res)
        self.assertIn("workflow_runs", res)
        self.assertEqual(len(res["workflow_runs"]), 1)
        self.assertEqual(res["workflow_runs"][0]["id"], 123456)

    @patch("urllib.request.urlopen")
    def test_get_runs_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")
        with patch("sys.stderr", new_callable=io.StringIO):
            res = get_runs(limit=2)
            self.assertIsNone(res)

    @patch("urllib.request.urlopen")
    def test_get_jobs_success(self, mock_urlopen):
        mock_response = MagicMock()
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
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = get_jobs(123456)
        self.assertIsNotNone(res)
        self.assertIn("jobs", res)
        self.assertEqual(len(res["jobs"]), 1)
        self.assertEqual(res["jobs"][0]["name"], "Verify & Audit (Python 3.12)")

    @patch("urllib.request.urlopen")
    def test_get_jobs_network_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection reset by peer")
        with patch("sys.stderr", new_callable=io.StringIO):
            res = get_jobs(123456)
            self.assertIsNone(res)

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

        with patch("sys.argv", ["tools/ci.py", "--limit", "2"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
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

        with patch("sys.argv", ["tools/ci.py", "-d"]):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                main()
                out = mock_stdout.getvalue()
                self.assertIn("Detailed Steps for Run #555666", out)
                self.assertIn("Hermetic Unit Test Suite", out)
                self.assertIn("Subsequent Step", out)

    @patch("tools.ci.get_runs")
    def test_main_no_runs_exits(self, mock_get_runs):
        mock_get_runs.return_value = None
        with patch("sys.argv", ["tools/ci.py"]):
            with patch("sys.stdout", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as cm:
                    main()
                self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
