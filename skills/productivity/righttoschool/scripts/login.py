"""Sign in only; use from browser_exec, never return credentials to the agent."""

import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit


PORTAL = "https://rightatschool.momentpath.com/"


def open_portal():
    """Return the authenticated tab ID, or a sanitized error. Never retry login."""
    # Import the helpers directly: CLI-injected helpers trace their arguments.
    # Also disable telemetry/recording for the rest of this browser_exec call.
    os.environ["BH_TELEMETRY"] = "0"
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["BH_RECORD"] = "0"
    os.environ.pop("BH_DEBUG_CLICKS", None)
    from browser_harness import helpers as browser, recorder, telemetry

    tab = None
    stage = "browser safety checks"
    try:
        # The CLI normalizes BU_CDP_URL into BU_CDP_WS before running Python.
        endpoint = urlsplit(
            os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL", "")
        )
        if (
            endpoint.scheme not in ("http", "ws")
            or endpoint.hostname != "127.0.0.1"
            or endpoint.port != 9223
            or endpoint.username
            or endpoint.password
            or telemetry.is_enabled()
            or recorder.recording_dir()
            or "HeadlessChrome/" not in browser.cdp("Browser.getVersion")["userAgent"]
        ):
            raise RuntimeError

        stage = "opening portal"
        tab = browser.new_tab(PORTAL)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if _authenticated(browser):
                return tab
            if browser.js(
                "location.origin === 'https://login.lineleader.com' && "
                "location.pathname === '/login' && "
                "!!document.querySelector('#login-identifier, #login-password')"
            ):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError

        stage = "establishing email step"
        if browser.js("!!document.querySelector('#login-password')") is True:
            # The password page remembers a server-side identity. Its email is
            # readonly: changing that field is not a substitute for identify.
            _check_login_form(browser)
            if not browser.js(
                "(() => { const a = Array.from(document.querySelectorAll('a'))"
                ".find(e => e.innerText.trim() === 'Not you?');"
                "if (!a || new URL(a.href).origin !== location.origin || "
                "new URL(a.href).pathname !== '/login/not-you') return false;"
                "a.click(); return true; })()"
            ):
                raise RuntimeError
        if not browser.wait_for_element('#login-identifier', timeout=20, visible=True):
            raise RuntimeError

        stage = "validating email form"
        _check_identifier_form(browser)
        username = password = None
        try:
            stage = "reading username from KeePassXC"
            username = _read_credential("Username")
            stage = "filling username"
            _check_identifier_form(browser)
            browser.fill_input('#login-identifier', username)
            _check_identifier_form(browser)
            browser.js("document.querySelector('#kt_login_continue_submit').click()")
            stage = "waiting for password step"
            if not browser.wait_for_element('#login-password', timeout=20, visible=True):
                raise RuntimeError
            _check_login_form(browser)
            # Read back only inside this process, never into tool output.
            if browser.js("document.querySelector('#login-email').value") != username:
                raise RuntimeError
            username = None
            stage = "reading password from KeePassXC"
            password = _read_credential("Password")
            stage = "filling password"
            _check_login_form(browser)
            browser.fill_input('#login-password', password)
        finally:
            username = password = None

        stage = "submitting sign-in"
        _check_login_form(browser)
        browser.js("document.querySelector('#kt_login_signin_submit').click()")
        stage = "verifying authenticated portal"
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if _authenticated(browser):
                return tab
            if browser.js(
                "location.origin === 'https://login.lineleader.com' && "
                "location.pathname === '/login' && "
                "/try again/i.test(document.body.innerText)"
            ) is True:
                stage = "sign-in response (login page asked to try again)"
                raise RuntimeError
            time.sleep(0.5)
        raise RuntimeError
    except Exception:
        if tab:
            try:
                browser.close_tab(tab)
            except Exception:
                pass
        # Never include exception text, subprocess output, or Python locals.
        raise RuntimeError(
            "Right At School login stopped during " + stage + ". No automatic retry."
        ) from None


def _read_credential(attribute):
    home = Path(__file__).resolve().parents[4]
    value = subprocess.run(
        [
            "keepassxc-cli", "show", "--quiet", "--show-protected",
            "-k", str(home / "eluzix.key"), "--no-password",
            "-a", attribute, str(home / "eluzix.kdbx"), "righttoschool-eluzix",
        ],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=True, timeout=15,
    ).stdout.removesuffix("\n")
    if not value:
        raise RuntimeError
    return value


def _check_identifier_form(browser):
    if not browser.js(
        "(() => {"
        "const u = document.querySelector('#login-identifier');"
        "const b = document.querySelector('#kt_login_continue_submit');"
        "return location.origin === 'https://login.lineleader.com' && "
        "location.pathname === '/login' && u?.name === '_identifier' && "
        "!u.readOnly && u.checkVisibility() && u.form && b?.form === u.form && "
        "b.type === 'submit' && b.innerText.trim() === 'Continue' && "
        "u.form.method.toLowerCase() === 'post' && "
        "new URL(u.form.action, location.href).origin === location.origin && "
        "new URL(u.form.action, location.href).pathname === '/login/identify';"
        "})()"
    ):
        raise RuntimeError


def _check_login_form(browser):
    if not browser.js(
        "(() => {"
        "const p = document.querySelector('#login-password');"
        "const u = document.querySelector('#login-email');"
        "const b = document.querySelector('#kt_login_signin_submit');"
        "return location.origin === 'https://login.lineleader.com' && "
        "location.pathname === '/login' && p?.type === 'password' && "
        "u?.name === '_username' && u.readOnly && p.checkVisibility() && "
        "p.form && u.form === p.form && "
        "b?.form === p.form && b.type === 'submit' && "
        "b.innerText.trim() === 'Sign In' && "
        "p.form.method.toLowerCase() === 'post' && "
        "new URL(p.form.action, location.href).origin === location.origin && "
        "new URL(p.form.action, location.href).pathname === '/login';"
        "})()"
    ):
        raise RuntimeError


def _authenticated(browser):
    # The portal is a Meteor app; a page shell or redirect is not authentication.
    # Test only presence, never return the user object or ID to tool output.
    return browser.js(
        "location.origin === 'https://rightatschool.momentpath.com' && "
        "!document.querySelector('input[type=password]') && "
        "typeof Meteor !== 'undefined' && "
        "typeof Meteor.userId === 'function' && !!Meteor.userId() && "
        "typeof Meteor.user === 'function' && !!Meteor.user()"
    ) is True
