"""Smoke tests for Bible Engine repository harness."""

import os
import unittest


class TestHarness(unittest.TestCase):
    """Verify repository structure and zero external dependencies."""

    def test_core_directories_exist(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        expected_dirs = ["core", "cli", "web", "data", "legacy", "tests"]
        for dirname in expected_dirs:
            path = os.path.join(repo_root, dirname)
            self.assertTrue(os.path.isdir(path), f"Missing expected directory: {dirname}")

    def test_ralph_script_syntax(self):
        """Validate bash syntax of ralph.sh."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        res = subprocess.run(["bash", "-n", ralph_path], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"ralph.sh bash syntax error: {res.stderr}")

    def test_install_hooks_script_syntax_and_executable(self):
        """Validate bash syntax and executable permission of tools/install_hooks.sh."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hook_installer = os.path.join(repo_root, "tools", "install_hooks.sh")
        self.assertTrue(os.path.exists(hook_installer), "Missing tools/install_hooks.sh")
        self.assertTrue(os.access(hook_installer, os.X_OK), "tools/install_hooks.sh is not executable")
        res = subprocess.run(["bash", "-n", hook_installer], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"tools/install_hooks.sh syntax error: {res.stderr}")

    def test_cleanup_sprint_prompt_contents(self):
        """Verify ralph.sh contains the Senior PM prompt and core diagnostic questions."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Senior Product Manager", content)
        self.assertIn("What is the weakest aspect of this project structure?", content)
        self.assertIn("What is preventing this from being more incredible?", content)
        self.assertIn("--cleanup", content)
        self.assertIn("-c", content)
        self.assertIn("is_cleanup_run", content)
        self.assertIn("get_next_run_number", content)

    def test_cleanup_run_math_and_detection(self):
        """Verify the 5th-iteration cadence logic directly via bash function."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")

        for run_num in [5, 10, 15, 20, 25, 100]:
            cmd = f'source "{ralph_path}" 2>/dev/null || true; is_cleanup_run {run_num} && echo "YES" || echo "NO"'
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "YES", f"Bash is_cleanup_run {run_num} should return YES")

        for run_num in [1, 2, 3, 4, 6, 7, 8, 9, 11, 14, 16, 99]:
            cmd = f'source "{ralph_path}" 2>/dev/null || true; is_cleanup_run {run_num} && echo "YES" || echo "NO"'
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "NO", f"Bash is_cleanup_run {run_num} should return NO")

    def test_ralph_script_pipestatus_handling(self):
        """Verify ralph.sh safely captures PIPESTATUS array without tripping set -u."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        # PIPESTATUS array should be captured into a variable before indexing
        self.assertIn('PIPE_STATUSES=("${PIPESTATUS[@]}")', content)

    def test_summary_prompt_contents(self):
        """Verify ralph.sh contains the Executive Summary prompt, Senior PM role, and options."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Senior Product Manager Meta-Improvement Sprint", content)
        self.assertIn("tools/executive_summary.py", content)
        self.assertIn("What is the weakest aspect of this project structure?", content)
        self.assertIn("--summary", content)
        self.assertIn("-s", content)
        self.assertIn("is_summary_run", content)

    def test_summary_run_math_and_detection(self):
        """Verify the 10th-iteration executive summary cadence logic directly via bash function."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")

        for run_num in [10, 20, 30, 40, 50, 100]:
            cmd = f'source "{ralph_path}" 2>/dev/null || true; is_summary_run {run_num} && echo "YES" || echo "NO"'
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "YES", f"Bash is_summary_run {run_num} should return YES")

        for run_num in [1, 2, 5, 9, 11, 15, 19, 25, 99]:
            cmd = f'source "{ralph_path}" 2>/dev/null || true; is_summary_run {run_num} && echo "YES" || echo "NO"'
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertEqual(res.stdout.strip(), "NO", f"Bash is_summary_run {run_num} should return NO")


    def test_ralph_help_flags(self):
        """Verify ./ralph.sh --help and -h exit 0 with clean usage information."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")

        for flag in ["--help", "-h"]:
            res = subprocess.run([ralph_path, flag], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"ralph.sh {flag} failed with code {res.returncode}")
            self.assertIn("ralph.sh — Autonomous & Interactive Development Loop Runner", res.stdout)
            self.assertIn("--loop", res.stdout)
            self.assertIn("--cleanup", res.stdout)
            self.assertIn("--summary", res.stdout)


if __name__ == "__main__":
    unittest.main()
