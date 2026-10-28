"""Open Genesis from browser_exec; credentials never leave this process."""

import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


ORIGIN = "https://parents.tenafly.k12.nj.us"
ENTRY = ORIGIN + "/genesis/sis/view?gohome=true"
PARENTS = ORIGIN + "/genesis/parents"


def open_portal():
    """Return our authenticated tab; close it on failure, with no login retry."""
    os.environ["BH_TELEMETRY"] = "0"
    os.environ["ANONYMIZED_TELEMETRY"] = "false"
    os.environ["BH_RECORD"] = "0"
    os.environ.pop("BH_DEBUG_CLICKS", None)
    from browser_harness import helpers as browser, recorder, telemetry

    tab = None
    stage = "browser safety checks"
    try:
        endpoint = urlsplit(
            os.environ.get("BU_CDP_WS") or os.environ.get("BU_CDP_URL", "")
        )
        ua = browser.cdp("Browser.getVersion")["userAgent"]
        if (
            endpoint.scheme not in ("http", "ws")
            or endpoint.hostname != "127.0.0.1"
            or endpoint.port != 9223
            or endpoint.username
            or endpoint.password
            or "HeadlessChrome/" not in ua
            or telemetry.is_enabled()
            or recorder.recording_dir()
        ):
            raise RuntimeError

        stage = "opening parent portal"
        tab = browser.new_tab("about:blank")
        # This portal returns HTTP 405 for the default headless user-agent.
        # Apply only to our tab, before navigation; never change shared Chrome.
        browser.cdp(
            "Network.setUserAgentOverride",
            userAgent=ua.replace("HeadlessChrome/", "Chrome/"),
        )
        browser.goto_url(PARENTS)
        if not browser.wait_for_element(
            "#j_password, .selectStudentItem.selected", timeout=25
        ):
            raise RuntimeError
        if _authenticated(browser):
            return tab

        # The district's /sis/view entry can show login even with an existing
        # parent session. Use it only when /parents is not authenticated.
        stage = "loading district sign-in"
        browser.goto_url(ENTRY)
        if not browser.wait_for_element("#j_password", timeout=25, visible=True):
            raise RuntimeError
        stage = "validating sign-in form"
        _check_login_form(browser)
        for attribute, selector in (
            ("Username", "#j_username"), ("Password", "#j_password")
        ):
            value = None
            try:
                _check_login_form(browser)
                stage = "reading credential"
                value = _read_credential(attribute)
                stage = "filling sign-in form"
                _check_login_form(browser)
                browser.fill_input(selector, value)
            finally:
                value = None

        stage = "submitting sign-in once"
        _check_login_form(browser)
        browser.js(
            "document.querySelector('#j_password').form"
            ".querySelector('input[type=submit]').click()"
        )
        stage = "verifying authenticated portal"
        if not browser.wait_for_element(".selectStudentItem.selected", timeout=30):
            raise RuntimeError
        if not _authenticated(browser):
            raise RuntimeError
        return tab
    except Exception:
        if tab:
            try:
                browser.close_tab(tab)
            except Exception:
                pass
        raise RuntimeError(
            "Genesis login stopped during " + stage + ". No automatic retry."
        ) from None


def _read_credential(attribute):
    home = Path(__file__).resolve().parents[4]
    value = subprocess.run(
        [
            "keepassxc-cli", "show", "--quiet", "--show-protected",
            "-k", str(home / "eluzix.key"), "--no-password",
            "-a", attribute, str(home / "eluzix.kdbx"), "genesis-eluzix",
        ],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        check=True, timeout=15,
    ).stdout.removesuffix("\n")
    if not value:
        raise RuntimeError
    return value


def _check_login_form(browser):
    if browser.js("""(() => {
        const u = document.querySelector('#j_username');
        const p = document.querySelector('#j_password');
        const f = p?.form;
        const b = f?.querySelector('input[type=submit]');
        return location.origin === 'https://parents.tenafly.k12.nj.us' &&
            u?.type === 'email' && u.name === 'j_username' &&
            p?.type === 'password' && p.name === 'j_password' &&
            !u.readOnly && !p.readOnly && !u.disabled && !p.disabled &&
            u.checkVisibility() && p.checkVisibility() &&
            f && u.form === f && f.method === 'post' &&
            f.action === 'https://parents.tenafly.k12.nj.us/genesis/sis/j_security_check?parents=Y' &&
            b?.value === 'Login' && !b.disabled && b.checkVisibility();
    })()""") is not True:
        raise RuntimeError


def _authenticated(browser):
    return browser.js("""
        location.origin === 'https://parents.tenafly.k12.nj.us' &&
        location.pathname === '/genesis/parents' &&
        !document.querySelector('input[type=password]') &&
        !!document.querySelector('#selectableStudents .selectStudentItem.selected') &&
        !!document.querySelector('.mainMenuTabs a[href*="tab2=forms"]')
    """) is True
