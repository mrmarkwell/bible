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


    def test_ralph_status_and_overview_commands(self):
        """Verify ./ralph.sh status, --status, overview, and summary display overview without running an iteration."""
        import subprocess

        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")

        for cmd_arg in ["status", "--status", "overview", "--overview", "summary", "--summary"]:
            res = subprocess.run([ralph_path, cmd_arg, "--no-doctor"], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"ralph.sh {cmd_arg} failed with code {res.returncode}")
            self.assertIn("AUTOLOOP EXECUTIVE PROJECT OVERVIEW", res.stdout)
            self.assertIn("1. REPOSITORY & VCS STATUS", res.stdout)
            self.assertIn("3. ROADMAP & MILESTONE PROGRESS", res.stdout)
            # Verify it did not invoke Jetski
            self.assertNotIn("Invoking Executive Summary & Trajectory Briefing", res.stdout)

    def test_default_prompt_contains_mandatory_issue_and_ci_checks(self):
        """Verify DEFAULT_PROMPT instructs agents on Priority 0 (CI/CD) and Priority 1 (GitHub issues) on every cycle."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("tools/ci.py check", content)
        self.assertIn("tools/github_issues.py check", content)
        self.assertIn("MANDATORY PRE-CHECKS ON EVERY CYCLE:", content)

    def test_cleanup_and_summary_prompts_contain_priority_checks(self):
        """Verify CLEANUP_PROMPT and SUMMARY_PROMPT instruct agents on priority pre-checks."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Both prompts must mandate checking CI and issues before proceeding with meta-audit
        self.assertIn("Priority 0: Check GitHub Actions CI/CD health (python3 tools/ci.py check)", content)
        self.assertIn("Priority 1: Check for open GitHub issues (python3 tools/github_issues.py check)", content)

    def test_ralph_loop_evaluates_github_issues_across_all_iterations(self):
        """Verify ralph.sh continuous loop evaluates GitHub issues independently on every loop iteration."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Loop body must reset variables and evaluate github_issues.py
        self.assertIn('CI_PROMPT=""', content)
        self.assertIn('GITHUB_PROMPT=""', content)
        self.assertIn('GITHUB_PROMPT=$(python3 "$REPO_DIR/tools/github_issues.py" check --prompt 2>/dev/null || true)', content)
        self.assertIn('elif [ -n "$GITHUB_PROMPT" ]; then', content)

    def test_ralph_cleanup_and_milestone_check_github_issues(self):
        """Verify on-demand --cleanup and --milestone modes check CI/CD and GitHub issues before launching."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ralph_path = os.path.join(repo_root, "ralph.sh")
        with open(ralph_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Ensure --milestone checks for broken CI and open issues
        milestone_idx = content.find('if [ "${1:-}" = "--milestone" ]')
        cleanup_idx = content.find('if [ "${1:-}" = "--cleanup" ]')
        self.assertNotEqual(milestone_idx, -1)
        self.assertNotEqual(cleanup_idx, -1)

        milestone_block = content[milestone_idx:cleanup_idx]
        self.assertIn('tools/github_issues.py" check --prompt', milestone_block)
        self.assertIn('tools/ci.py" check --prompt', milestone_block)

        cleanup_block = content[cleanup_idx:content.find('# Check if user explicitly passed print/headless mode')]
        self.assertIn('tools/github_issues.py" check --prompt', cleanup_block)
        self.assertIn('tools/ci.py" check --prompt', cleanup_block)

    def test_agents_md_universal_prechecks_hierarchy(self):
        """Verify AGENTS.md encodes universal priority checks across all iterations."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        agents_path = os.path.join(repo_root, "AGENTS.md")
        with open(agents_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Universal Loop Lifecycle (Mandatory Pre-Checks on EVERY Iteration)", content)
        self.assertIn("Priority 0 Check: GitHub Actions CI/CD Health (TOP PRIORITY ON EVERY ITERATION)", content)
        self.assertIn("Priority 1 Check: Open GitHub Issue / Bug Report Triage (MANDATORY ON EVERY ITERATION)", content)


if __name__ == "__main__":
    unittest.main()
