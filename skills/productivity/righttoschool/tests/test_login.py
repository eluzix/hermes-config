"""Offline tests: no real browser, vault, credentials, or portal requests."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import traceback
import types
import unittest
from unittest.mock import Mock, call, patch


spec = importlib.util.spec_from_file_location(
    "righttoschool_login", Path(__file__).resolve().parents[1] / "scripts/login.py"
)
login = importlib.util.module_from_spec(spec)
spec.loader.exec_module(login)


class LoginTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.browser = Mock()
        self.browser.cdp.return_value = {"userAgent": "HeadlessChrome/test"}
        self.browser.new_tab.return_value = "test-tab"
        self.remembered = False
        self.resolved_email = "fake user"
        self.browser.js.side_effect = self.evaluate
        self.recorder = Mock()
        self.recorder.recording_dir.return_value = None
        self.telemetry = Mock()
        self.telemetry.is_enabled.return_value = False
        harness = types.ModuleType("browser_harness")
        harness.helpers = self.browser
        harness.recorder = self.recorder
        harness.telemetry = self.telemetry
        self.stack.enter_context(patch.dict(sys.modules, browser_harness=harness))
        self.stack.enter_context(patch.dict(os.environ, {
            "BU_CDP_WS": "ws://127.0.0.1:9223/devtools/browser/test",
            "BH_RECORD": "1", "BH_TELEMETRY": "1", "BH_DEBUG_CLICKS": "1",
        }))
        self.run = self.stack.enter_context(patch.object(login.subprocess, "run"))
        self.run.side_effect = [
            types.SimpleNamespace(stdout="fake user\n"),
            types.SimpleNamespace(stdout=" fake password rn \n"),
        ]
        self.auth = self.stack.enter_context(
            patch.object(login, "_authenticated", side_effect=[False, True])
        )

    def evaluate(self, expression):
        if expression == "!!document.querySelector('#login-password')":
            return self.remembered
        if expression == "document.querySelector('#login-email').value":
            return self.resolved_email
        return True

    def submissions(self):
        return [c for c in self.browser.js.call_args_list
                if c.args[0] == "document.querySelector('#kt_login_signin_submit').click()"]

    def test_login_fills_exact_values_and_submits_once_without_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(login.open_portal(), "test-tab")
        self.assertEqual(output.getvalue(), "")
        self.browser.fill_input.assert_has_calls([
            call("#login-identifier", "fake user"),
            call("#login-password", " fake password rn "),
        ])
        self.browser.js.assert_any_call("document.querySelector('#kt_login_continue_submit').click()")
        self.assertEqual(len(self.submissions()), 1)
        self.browser.close_tab.assert_not_called()
        self.assertEqual(os.environ["BH_TELEMETRY"], "0")
        self.assertEqual(os.environ["BH_RECORD"], "0")
        self.assertNotIn("BH_DEBUG_CLICKS", os.environ)
        for invocation in self.run.call_args_list:
            self.assertIn("--show-protected", invocation.args[0])
            self.assertIn("--quiet", invocation.args[0])
            self.assertTrue(invocation.kwargs["capture_output"])
            self.assertEqual(invocation.kwargs["stdin"], subprocess.DEVNULL)
            self.assertNotIn("shell", invocation.kwargs)

    def test_existing_authenticated_session_never_reads_vault_or_submits(self):
        self.auth.side_effect = [True]
        self.assertEqual(login.open_portal(), "test-tab")
        self.run.assert_not_called()
        self.assertFalse(self.submissions())

    def test_remote_endpoint_stops_before_browser_or_vault(self):
        os.environ["BU_CDP_WS"] = "wss://example.com/devtools/browser/test"
        with self.assertRaisesRegex(RuntimeError, "browser safety checks"):
            login.open_portal()
        self.browser.new_tab.assert_not_called()
        self.run.assert_not_called()

    def test_recording_stops_before_vault(self):
        self.recorder.recording_dir.return_value = "active-recording"
        with self.assertRaisesRegex(RuntimeError, "browser safety checks"):
            login.open_portal()
        self.run.assert_not_called()

    def test_visible_browser_stops_before_vault(self):
        self.browser.cdp.return_value = {"userAgent": "Chrome/test"}
        with self.assertRaisesRegex(RuntimeError, "browser safety checks"):
            login.open_portal()
        self.run.assert_not_called()

    def test_untrusted_form_stops_before_vault(self):
        with patch.object(login, "_check_identifier_form", side_effect=RuntimeError):
            with self.assertRaisesRegex(RuntimeError, "validating email form"):
                login.open_portal()
        self.run.assert_not_called()
        self.browser.close_tab.assert_called_once_with("test-tab")

    def test_form_is_rechecked_before_each_fill(self):
        with patch.object(login, "_check_login_form", side_effect=[None, RuntimeError()]):
            with self.assertRaisesRegex(RuntimeError, "filling password"):
                login.open_portal()
        self.browser.fill_input.assert_called_once_with("#login-identifier", "fake user")
        self.assertFalse(self.submissions())

    def test_remembered_email_is_reset_before_identifying(self):
        self.remembered = True
        self.assertEqual(login.open_portal(), "test-tab")
        expressions = [c.args[0] for c in self.browser.js.call_args_list]
        reset = next(i for i, e in enumerate(expressions) if '/login/not-you' in e)
        identify = expressions.index("document.querySelector('#kt_login_continue_submit').click()")
        self.assertLess(reset, identify)
        self.assertEqual(self.browser.fill_input.call_args_list, [
            call('#login-identifier', 'fake user'),
            call('#login-password', ' fake password rn '),
        ])

    def test_different_resolved_email_never_reads_or_submits_password(self):
        self.resolved_email = 'another fake user'
        with self.assertRaisesRegex(RuntimeError, 'waiting for password step'):
            login.open_portal()
        self.assertEqual(self.run.call_count, 1)
        self.assertFalse(self.submissions())

    def test_missing_password_step_never_reads_password(self):
        self.browser.wait_for_element.side_effect = [True, False]
        with self.assertRaisesRegex(RuntimeError, 'waiting for password step'):
            login.open_portal()
        self.assertEqual(self.run.call_count, 1)
        self.assertFalse(self.submissions())

    def test_vault_error_does_not_expose_output_or_traceback_context(self):
        self.run.side_effect = subprocess.CalledProcessError(
            1, ["fake-vault"], output="FAKE_SECRET", stderr="FAKE_SECRET"
        )
        try:
            login.open_portal()
        except RuntimeError:
            rendered = traceback.format_exc()
        else:
            self.fail("Expected sanitized failure")
        self.assertNotIn("FAKE_SECRET", rendered)
        self.assertIn("reading username", rendered)
        self.browser.fill_input.assert_not_called()
        self.assertFalse(self.submissions())

    def test_fill_error_is_sanitized_and_tab_closed(self):
        self.browser.fill_input.side_effect = RuntimeError("FAKE_SECRET")
        with self.assertRaisesRegex(RuntimeError, "filling username") as error:
            login.open_portal()
        self.assertNotIn("FAKE_SECRET", str(error.exception))
        self.browser.close_tab.assert_called_once_with("test-tab")
        self.assertFalse(self.submissions())

    def test_empty_vault_value_never_fills_or_submits(self):
        self.run.side_effect = [types.SimpleNamespace(stdout="\n")]
        with self.assertRaisesRegex(RuntimeError, "reading username"):
            login.open_portal()
        self.browser.fill_input.assert_not_called()
        self.assertFalse(self.submissions())

    def test_try_again_response_is_reported_without_retrying(self):
        self.auth.side_effect = [False, False]
        with self.assertRaisesRegex(RuntimeError, "login page asked to try again"):
            login.open_portal()
        self.assertEqual(len(self.submissions()), 1)
        self.assertEqual(self.run.call_count, 2)
        self.browser.close_tab.assert_called_once_with("test-tab")

    def test_verification_timeout_does_not_repeat_submission(self):
        with patch.object(login.time, "monotonic", side_effect=[0, 0, 0, 36]):
            with self.assertRaisesRegex(RuntimeError, "verifying authenticated portal"):
                login.open_portal()
        self.assertEqual(len(self.submissions()), 1)
        self.assertEqual(self.run.call_count, 2)
        self.browser.close_tab.assert_called_once_with("test-tab")


if __name__ == "__main__":
    unittest.main()
