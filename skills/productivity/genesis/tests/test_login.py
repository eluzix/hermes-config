import importlib.util
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch


spec = importlib.util.spec_from_file_location(
    "genesis_login", Path(__file__).resolve().parents[1] / "scripts/login.py"
)
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.browser = Mock()
        self.browser.cdp.return_value = {"userAgent": "Test HeadlessChrome/152.0"}
        self.browser.new_tab.return_value = "our-tab"
        self.browser.wait_for_element.return_value = True
        self.harness = types.ModuleType("browser_harness")
        self.harness.helpers = self.browser
        self.harness.telemetry = Mock(is_enabled=Mock(return_value=False))
        self.harness.recorder = Mock(recording_dir=Mock(return_value=None))
        self.modules = patch.dict(sys.modules, {"browser_harness": self.harness})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.env = patch.dict(os.environ, {"BU_CDP_WS": "ws://127.0.0.1:9223/devtools/browser/test"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_session_reuse_never_reads_vault_and_sets_ua_before_navigation(self):
        with patch.object(login, "_authenticated", return_value=True), patch.object(login, "_read_credential") as read:
            self.assertEqual(login.open_portal(), "our-tab")
        read.assert_not_called()
        self.browser.goto_url.assert_called_once_with(login.PARENTS)
        calls = self.browser.mock_calls
        override = call.cdp("Network.setUserAgentOverride", userAgent="Test Chrome/152.0")
        self.assertLess(calls.index(override), calls.index(call.goto_url(login.PARENTS)))
        self.browser.close_tab.assert_not_called()

    def test_wrong_endpoint_stops_before_tab_or_credentials(self):
        for endpoint in ("ws://127.0.0.1:9222/test", "ws://example.org:9223/test", "ws://user:pass@127.0.0.1:9223/test"):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {"BU_CDP_WS": endpoint}), patch.object(login, "_read_credential") as read:
                with self.assertRaisesRegex(RuntimeError, "browser safety checks"):
                    login.open_portal()
                read.assert_not_called()
                self.browser.new_tab.assert_not_called()

    def test_recording_stops_before_navigation(self):
        self.harness.recorder.recording_dir.return_value = "/recording"
        with self.assertRaisesRegex(RuntimeError, "browser safety checks"):
            login.open_portal()
        self.browser.new_tab.assert_not_called()

    def test_http_failure_does_not_read_vault(self):
        self.browser.goto_url.side_effect = RuntimeError("private diagnostic")
        with patch.object(login, "_read_credential") as read:
            with self.assertRaisesRegex(RuntimeError, "opening parent portal") as raised:
                login.open_portal()
        self.assertNotIn("private diagnostic", str(raised.exception))
        read.assert_not_called()
        self.browser.close_tab.assert_called_once_with("our-tab")

    def test_invalid_form_does_not_read_vault(self):
        with patch.object(login, "_authenticated", return_value=False), patch.object(login, "_check_login_form", side_effect=RuntimeError), patch.object(login, "_read_credential") as read:
            with self.assertRaisesRegex(RuntimeError, "validating sign-in form"):
                login.open_portal()
        read.assert_not_called()
        self.browser.fill_input.assert_not_called()

    def test_sign_in_once_and_verify_before_success(self):
        with patch.object(login, "_authenticated", side_effect=[False, True]), patch.object(login, "_check_login_form"), patch.object(login, "_read_credential", side_effect=["fake-user", "fake-pass"]) as read:
            self.assertEqual(login.open_portal(), "our-tab")
        self.assertEqual(read.call_args_list, [call("Username"), call("Password")])
        self.assertEqual(self.browser.fill_input.call_args_list, [call("#j_username", "fake-user"), call("#j_password", "fake-pass")])
        self.browser.js.assert_called_once()
        self.browser.close_tab.assert_not_called()

    def test_failed_authentication_is_not_retried(self):
        with patch.object(login, "_authenticated", return_value=False), patch.object(login, "_check_login_form"), patch.object(login, "_read_credential", side_effect=["fake-user", "fake-pass"]):
            with self.assertRaisesRegex(RuntimeError, "No automatic retry"):
                login.open_portal()
        self.browser.js.assert_called_once()
        self.browser.close_tab.assert_called_once_with("our-tab")

    def test_fill_error_cannot_leak_credential(self):
        self.browser.fill_input.side_effect = RuntimeError("fake-secret-output")
        with patch.object(login, "_authenticated", return_value=False), patch.object(login, "_check_login_form"), patch.object(login, "_read_credential", return_value="fake-secret-output"):
            with self.assertRaises(RuntimeError) as raised:
                login.open_portal()
        self.assertNotIn("fake-secret-output", str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)
        self.browser.js.assert_not_called()

    def test_keepass_trims_only_one_newline_and_captures_output(self):
        for raw, expected in (("  fake pass \n", "  fake pass "), ("fake\n\n", "fake\n")):
            with self.subTest(raw=raw), patch.object(login.subprocess, "run", return_value=types.SimpleNamespace(stdout=raw)) as run:
                self.assertEqual(login._read_credential("Password"), expected)
                args, kwargs = run.call_args
                self.assertEqual(args[0][-1], "genesis-eluzix")
                self.assertIn("--no-password", args[0])
                self.assertEqual(kwargs, dict(stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=15))


if __name__ == "__main__":
    unittest.main()
