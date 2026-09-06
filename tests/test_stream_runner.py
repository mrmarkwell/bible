"""Unit tests for live streaming telemetry runner (tools/stream_runner.py).

Zero external dependencies (Python 3 standard library only per ADR-003).
"""

import io
import json
import unittest

from tools.stream_runner import (
    ANSIStyler,
    StreamFormatter,
    summarize_tool_parameters,
)


class TestANSIStyler(unittest.TestCase):
    """Test ANSI terminal styler."""

    def test_disabled_styler(self):
        styler = ANSIStyler(enabled=False)
        self.assertEqual(styler.bold("test"), "test")
        self.assertEqual(styler.cyan("hello"), "hello")
        self.assertEqual(styler.green("ok"), "ok")

    def test_enabled_styler(self):
        styler = ANSIStyler(enabled=True)
        self.assertEqual(styler.bold("test"), "\033[1mtest\033[0m")
        self.assertEqual(styler.green("ok"), "\033[32mok\033[0m")


class TestSummarizeToolParameters(unittest.TestCase):
    """Test tool parameter summarization."""

    def test_empty_parameters(self):
        self.assertEqual(summarize_tool_parameters(None), "")
        self.assertEqual(summarize_tool_parameters({}), "")

    def test_command_line(self):
        summary = summarize_tool_parameters({"CommandLine": "python3 -m unittest discover tests"})
        self.assertEqual(summary, "python3 -m unittest discover tests")

    def test_long_command_line_truncation(self):
        long_cmd = "a" * 120
        summary = summarize_tool_parameters({"CommandLine": long_cmd})
        self.assertTrue(summary.endswith("..."))
        self.assertEqual(len(summary), 90)

    def test_target_file(self):
        summary = summarize_tool_parameters({"TargetFile": "/path/to/file.py"})
        self.assertEqual(summary, "/path/to/file.py")

    def test_query(self):
        summary = summarize_tool_parameters({"Query": "find something"})
        self.assertEqual(summary, '"find something"')

    def test_generic_fallback(self):
        summary = summarize_tool_parameters({"arg1": "val1", "arg2": "val2"})
        self.assertEqual(summary, "arg1=val1, arg2=val2")


class TestStreamFormatter(unittest.TestCase):
    """Test StreamFormatter parsing and rendering."""

    def setUp(self):
        self.out = io.StringIO()
        self.err = io.StringIO()
        self.formatter = StreamFormatter(out=self.out, err=self.err)
        # Force color off in tests for deterministic output
        self.formatter.style.enabled = False

    def test_init_event(self):
        event = {
            "event": "init",
            "conversation_id": "12345678-abcd-1234-abcd-123456789abc",
            "init": {
                "model": "gemini-2.5-pro",
                "tools": ["run_command", "view_file"],
            },
        }
        self.formatter.process_line(json.dumps(event))
        out = self.out.getvalue()
        self.assertIn("⚡ Jetski Initialized", out)
        self.assertIn("gemini-2.5-pro", out)
        self.assertIn("tools: 2", out)

    def test_step_update_tool_call_and_duration(self):
        start_event = {
            "event": "step_update",
            "step_update": {
                "step_index": 1,
                "tool_name": "run_command",
                "tool_info": {
                    "name": "run_command",
                    "parameters": {"CommandLine": "python3 -m unittest"},
                },
                "state": "RUNNING",
            },
        }
        done_event = {
            "event": "step_update",
            "step_update": {
                "step_index": 1,
                "tool_name": "run_command",
                "state": "DONE",
                "duration_seconds": 1.25,
            },
        }
        self.formatter.process_line(json.dumps(start_event))
        self.formatter.process_line(json.dumps(done_event))
        out = self.out.getvalue()
        self.assertIn("⚙ [TOOL] run_command : python3 -m unittest", out)
        self.assertIn("✔ [DONE] run_command (1.25s)", out)

    def test_text_delta_streaming(self):
        delta1 = {
            "event": "step_update",
            "step_update": {"text_delta": "Hello "},
        }
        delta2 = {
            "event": "step_update",
            "step_update": {"text_delta": "world!"},
        }
        self.formatter.process_line(json.dumps(delta1))
        self.formatter.process_line(json.dumps(delta2))
        out = self.out.getvalue()
        self.assertEqual(out, "Hello world!")

    def test_result_success(self):
        result_event = {
            "event": "result",
            "result": {
                "status": "SUCCESS",
                "num_turns": 3,
                "usage": {"total_tokens": 1420},
            },
        }
        self.formatter.process_line(json.dumps(result_event))
        out = self.out.getvalue()
        self.assertIn("🏁 [SUCCESS]", out)
        self.assertIn("Turns: 3", out)
        self.assertIn("Tokens: 1,420", out)
        self.assertEqual(self.formatter.exit_code, 0)

    def test_result_error(self):
        result_event = {
            "event": "result",
            "result": {
                "status": "ERROR",
                "error": "Quota limit reached",
            },
        }
        self.formatter.process_line(json.dumps(result_event))
        out = self.out.getvalue()
        self.assertIn("❌ [ERROR]", out)
        self.assertIn("Quota limit reached", out)
        self.assertEqual(self.formatter.exit_code, 1)

    def test_non_json_passthrough(self):
        raw_text = "Standard error notice or greeting"
        self.formatter.process_line(raw_text)
        out = self.out.getvalue()
        self.assertEqual(out, f"{raw_text}\n")

    def test_full_stream_processing(self):
        stream = [
            json.dumps({"event": "init", "init": {"model": "test-model"}}),
            json.dumps({"event": "step_update", "step_update": {"text_delta": "Working..."}}),
            json.dumps({"event": "result", "result": {"status": "SUCCESS"}}),
        ]
        code = self.formatter.process_stream(stream)
        self.assertEqual(code, 0)
        out = self.out.getvalue()
        self.assertIn("⚡ Jetski Initialized", out)
        self.assertIn("Working...", out)
        self.assertIn("🏁 [SUCCESS]", out)


if __name__ == "__main__":
    unittest.main()
