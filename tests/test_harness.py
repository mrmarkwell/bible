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

    def test_ralph_script_exists_and_is_executable(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        self.assertTrue(os.path.isfile(ralph_path), "ralph.sh not found")
        self.assertTrue(os.access(ralph_path, os.X_OK), "ralph.sh is not executable")


if __name__ == "__main__":
    unittest.main()
