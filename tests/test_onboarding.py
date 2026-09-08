"""Hermetic Unit Tests for Sovereign API Key Onboarding & Credential Manager.

Zero-dependency implementation (Python 3 standard library unittest and unittest.mock only per ADR-003).
Verifies:
- Masking of sensitive API keys.
- Credential discovery across environment variables, config files, and .env files.
- Live HTTP probe mocking (HTTP 200 success, 401 unauthorized, 403 forbidden, URLError offline).
- File persistence with POSIX 0600 security permissions.
- Interactive onboarding wizard with simulated user inputs.
- CLI argument parsing, status output, and JSON telemetry.
"""

import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from tools.onboarding import (
    clear_api_key,
    discover_esv_api_key,
    discover_gemini_api_key,
    get_credential_status,
    main,
    mask_api_key,
    probe_esv_api_key,
    probe_gemini_api_key,
    run_onboarding_wizard,
    save_api_key,
)


class TestOnboarding(unittest.TestCase):
    """Test suite for tools/onboarding.py."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_mask_api_key(self):
        """Verify API keys are masked safely."""
        self.assertEqual(mask_api_key(None), "(none)")
        self.assertEqual(mask_api_key(""), "(none)")
        self.assertEqual(mask_api_key("   "), "(none)")
        self.assertEqual(mask_api_key("123456"), "12...56")
        self.assertEqual(mask_api_key("abcdefghijklmnop"), "abcd...mnop")

    def test_discover_esv_key_from_env(self):
        """Verify discovery of ESV API key from environment variable."""
        with patch.dict(os.environ, {"ESV_API_KEY": "test_env_key_123"}):
            key, src = discover_esv_api_key(self.test_root)
            self.assertEqual(key, "test_env_key_123")
            self.assertIn("environment variable", src)

    def test_discover_esv_key_from_config_file(self):
        """Verify discovery of ESV key from repository config file."""
        config_dir = self.test_root / "config"
        config_dir.mkdir(parents=True)
        key_file = config_dir / "esv_api_key.txt"
        key_file.write_text("file_esv_key_456\n")

        with patch.dict(os.environ, {}, clear=True):
            key, src = discover_esv_api_key(self.test_root)
            self.assertEqual(key, "file_esv_key_456")
            self.assertIn("repository config file", src)

    def test_discover_esv_key_from_dotenv(self):
        """Verify discovery of ESV key from .env file."""
        dotenv = self.test_root / ".env"
        dotenv.write_text("SOME_VAR=foo\nESV_API_KEY='dotenv_esv_key_789'\n")

        with patch.dict(os.environ, {}, clear=True):
            key, src = discover_esv_api_key(self.test_root)
            self.assertEqual(key, "dotenv_esv_key_789")
            self.assertIn("repository .env file", src)

    def test_discover_gemini_key_from_env(self):
        """Verify discovery of Gemini key from environment variables."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gem_test_key_001"}, clear=True):
            key, src = discover_gemini_api_key(self.test_root)
            self.assertEqual(key, "gem_test_key_001")
            self.assertIn("environment variable GEMINI_API_KEY", src)

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "goog_test_key_002"}, clear=True):
            key, src = discover_gemini_api_key(self.test_root)
            self.assertEqual(key, "goog_test_key_002")
            self.assertIn("environment variable GOOGLE_API_KEY", src)

    def test_discover_gemini_key_from_config_file(self):
        """Verify discovery of Gemini key from config file."""
        config_dir = self.test_root / "config"
        config_dir.mkdir(parents=True)
        key_file = config_dir / "gemini_api_key.txt"
        key_file.write_text("file_gemini_key_999\n")

        with patch.dict(os.environ, {}, clear=True):
            key, src = discover_gemini_api_key(self.test_root)
            self.assertEqual(key, "file_gemini_key_999")
            self.assertIn("repository config file", src)

    def test_probe_esv_key_missing(self):
        """Verify probe result when ESV key is absent."""
        with patch.dict(os.environ, {}, clear=True):
            ok, msg, det = probe_esv_api_key(None)
            self.assertFalse(ok)
            self.assertEqual(det["status"], "missing")
            self.assertIn("not configured", msg)

    def test_probe_esv_key_success(self):
        """Verify probe result on HTTP 200 success from ESV API."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {"passages": ["In the beginning was the Word, and the Word was with God."]}
        ).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response

        ok, msg, det = probe_esv_api_key("valid_esv_key_12345", opener=mock_opener)
        self.assertTrue(ok)
        self.assertEqual(det["status"], "authorized")
        self.assertIn("In the beginning", det["sample_passage"])
        self.assertIn("valid and authorized", msg)

    def test_probe_esv_key_unauthorized_401(self):
        """Verify probe result on HTTP 401 Unauthorized."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.HTTPError(
            url="https://api.esv.org/v3/passage/text/",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"detail": "Invalid token."}'),
        )

        ok, msg, det = probe_esv_api_key("bad_key_123", opener=mock_opener)
        self.assertFalse(ok)
        self.assertEqual(det["status"], "unauthorized")
        self.assertIn("Invalid API key (HTTP 401)", msg)

    def test_probe_esv_key_network_error(self):
        """Verify probe result on network unreachable / offline."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("Temporary failure in name resolution")

        ok, msg, det = probe_esv_api_key("any_key", opener=mock_opener)
        self.assertFalse(ok)
        self.assertEqual(det["status"], "offline")
        self.assertIn("unreachable", msg)

    def test_probe_gemini_key_missing(self):
        """Verify probe result when Gemini key is absent."""
        with patch.dict(os.environ, {}, clear=True):
            ok, msg, det = probe_gemini_api_key(None)
            self.assertFalse(ok)
            self.assertEqual(det["status"], "missing")
            self.assertIn("not configured", msg)

    def test_probe_gemini_key_success(self):
        """Verify probe result on HTTP 200 success from Google Gemini API."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(
            {"models": [{"name": "models/gemini-2.5-flash"}, {"name": "models/gemini-2.5-pro"}]}
        ).encode("utf-8")
        mock_response.__enter__.return_value = mock_response

        mock_opener = MagicMock()
        mock_opener.open.return_value = mock_response

        ok, msg, det = probe_gemini_api_key("valid_gemini_key_abc", opener=mock_opener)
        self.assertTrue(ok)
        self.assertEqual(det["status"], "authorized")
        self.assertEqual(det["models_count"], 2)
        self.assertIn("valid and authorized", msg)

    def test_probe_gemini_key_unauthorized_400(self):
        """Verify probe result on HTTP 400 Bad Request (API key not valid)."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(b'{"error": {"message": "API key not valid."}}'),
        )

        ok, msg, det = probe_gemini_api_key("invalid_gemini_key", opener=mock_opener)
        self.assertFalse(ok)
        self.assertEqual(det["status"], "unauthorized")
        self.assertIn("Invalid API key (HTTP 400)", msg)

    def test_probe_gemini_key_network_error(self):
        """Verify probe result on network offline."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError("Network unreachable")

        ok, msg, det = probe_gemini_api_key("any_key", opener=mock_opener)
        self.assertFalse(ok)
        self.assertEqual(det["status"], "offline")
        self.assertIn("unreachable", msg)

    def test_save_and_clear_api_keys(self):
        """Verify secure file persistence with 0600 permissions and removal."""
        esv_path = save_api_key("esv", "secret_esv_value", repo_root=self.test_root)
        self.assertTrue(esv_path.is_file())
        self.assertEqual(esv_path.read_text(encoding="utf-8").strip(), "secret_esv_value")

        # Check POSIX permissions (0600: user read/write only)
        mode = stat.S_IMODE(esv_path.stat().st_mode)
        self.assertEqual(mode, 0o600)

        gem_path = save_api_key("gemini", "secret_gemini_value", repo_root=self.test_root)
        self.assertTrue(gem_path.is_file())
        self.assertEqual(gem_path.read_text(encoding="utf-8").strip(), "secret_gemini_value")
        self.assertEqual(stat.S_IMODE(gem_path.stat().st_mode), 0o600)

        # Clear ESV key
        deleted = clear_api_key("esv", repo_root=self.test_root)
        self.assertTrue(any(p == esv_path for p in deleted))
        self.assertFalse(esv_path.exists())

        # Clear Gemini key
        deleted_gem = clear_api_key("gemini", repo_root=self.test_root)
        self.assertTrue(any(p == gem_path for p in deleted_gem))
        self.assertFalse(gem_path.exists())

    def test_get_credential_status(self):
        """Verify structured credential status extraction."""
        with patch.dict(os.environ, {"ESV_API_KEY": "test_esv", "GEMINI_API_KEY": "test_gem"}):
            status = get_credential_status(probe=False)
            self.assertTrue(status["esv"]["configured"])
            self.assertTrue(status["gemini"]["configured"])
            self.assertIsNone(status["esv"]["probe"])

    def test_run_onboarding_wizard_non_interactive_flags(self):
        """Verify onboarding wizard execution with explicit arguments."""
        output_lines = []

        with patch("tools.onboarding.probe_esv_api_key") as mock_probe_esv, patch(
            "tools.onboarding.probe_gemini_api_key"
        ) as mock_probe_gem:
            mock_probe_esv.return_value = (True, "ESV OK", {"status": "authorized"})
            mock_probe_gem.return_value = (True, "Gemini OK", {"status": "authorized"})

            outcomes = run_onboarding_wizard(
                repo_root=self.test_root,
                interactive=False,
                esv_key="test_esv_arg_key",
                gemini_key="test_gemini_arg_key",
                probe=True,
                print_fn=output_lines.append,
            )

            self.assertTrue(outcomes["esv_updated"])
            self.assertTrue(outcomes["gemini_updated"])
            self.assertEqual(outcomes["esv_status"]["status"], "authorized")
            self.assertEqual(outcomes["gemini_status"]["status"], "authorized")

            esv_file = self.test_root / "config" / "esv_api_key.txt"
            gem_file = self.test_root / "config" / "gemini_api_key.txt"
            self.assertTrue(esv_file.is_file())
            self.assertTrue(gem_file.is_file())
            self.assertEqual(esv_file.read_text(encoding="utf-8").strip(), "test_esv_arg_key")
            self.assertEqual(gem_file.read_text(encoding="utf-8").strip(), "test_gemini_arg_key")

    def test_run_onboarding_wizard_simulated_inputs(self):
        """Verify interactive wizard loop with simulated user inputs."""
        output_lines = []
        user_inputs = iter(["my_new_esv_key", "my_new_gemini_key"])

        with patch("tools.onboarding.probe_esv_api_key") as mock_probe_esv, patch(
            "tools.onboarding.probe_gemini_api_key"
        ) as mock_probe_gem, patch("sys.stdin.isatty", return_value=True):
            mock_probe_esv.return_value = (True, "ESV Valid", {"status": "authorized"})
            mock_probe_gem.return_value = (True, "Gemini Valid", {"status": "authorized"})

            outcomes = run_onboarding_wizard(
                repo_root=self.test_root,
                interactive=True,
                probe=True,
                input_fn=lambda _: next(user_inputs),
                print_fn=output_lines.append,
            )

            self.assertTrue(outcomes["esv_updated"])
            self.assertTrue(outcomes["gemini_updated"])

    def test_cli_main_status_json(self):
        """Verify CLI status --json command."""
        buf = io.StringIO()
        with patch("sys.stdout", buf), patch.dict(os.environ, {}, clear=True):
            exit_code = main(["status", "--json"])
            self.assertEqual(exit_code, 0)
            data = json.loads(buf.getvalue())
            self.assertIn("esv", data)
            self.assertIn("gemini", data)
            self.assertFalse(data["esv"]["configured"])

    def test_cli_main_set_and_clear(self):
        """Verify CLI set and clear commands."""
        buf = io.StringIO()
        with patch("sys.stdout", buf), patch("tools.onboarding.REPO_ROOT", self.test_root):
            exit_code = main(["set", "--esv", "cli_esv_key", "--gemini", "cli_gemini_key"])
            self.assertEqual(exit_code, 0)

            # Verify saved
            esv_f = self.test_root / "config" / "esv_api_key.txt"
            self.assertTrue(esv_f.is_file())
            self.assertEqual(esv_f.read_text(encoding="utf-8").strip(), "cli_esv_key")

            # Verify clear
            exit_clear = main(["clear", "all"])
            self.assertEqual(exit_clear, 0)
            self.assertFalse(esv_f.exists())


if __name__ == "__main__":
    unittest.main()
