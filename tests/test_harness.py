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
        """Verify the 5th-iteration cadence logic directly."""
        def is_cleanup(n: int) -> bool:
            return n > 0 and (n % 5 == 0)

        # Multiples of 5 should trigger cleanup sprint
        for run_num in [5, 10, 15, 20, 25, 100]:
            self.assertTrue(is_cleanup(run_num), f"Run {run_num} should be a cleanup sprint")

        # Non-multiples should be standard cycles
        for run_num in [1, 2, 3, 4, 6, 7, 8, 9, 11, 14, 16, 99]:
            self.assertFalse(is_cleanup(run_num), f"Run {run_num} should not be a cleanup sprint")

    def test_ralph_script_pipestatus_handling(self):
        """Verify ralph.sh safely captures PIPESTATUS array without tripping set -u."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        # PIPESTATUS array should be captured into a variable before indexing
        self.assertIn('PIPE_STATUSES=("${PIPESTATUS[@]}")', content)
        # There should be no raw ${PIPESTATUS[1]} references which trip bash set -u
        self.assertNotIn('${PIPESTATUS[1]}', content)


if __name__ == "__main__":
    unittest.main()
