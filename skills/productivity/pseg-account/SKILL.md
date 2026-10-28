---
name: pseg-account
description: Use when accessing the PSE&G electricity account.
version: 0.1.0
author: Uzi, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pseg, electricity, utility, account, login]
    related_skills: [himalaya, hermes-agent]
---

# PSE&G Account

Access the user's New Jersey PSE&G electricity account through the official browser portal. Default to read-only account access; payments, autopay changes, service changes, and security-setting changes require an explicit user request.

## When to use

- Sign into PSE&G or inspect the user's electricity balance, bills, usage, or account notices.
- The user's requested authentication flow is username/password followed by email OTP sent to their Gmail.

## Status and prerequisites

This skill is installed but the login workflow is NOT end-to-end validated. The initial live attempt reached a blank PSE&G sign-in page with no inputs, and the vault selected an unrelated open PaySchools tab. The incorrectly origin-bound entry was removed and its absence verified. No PSE&G login remains saved from that attempt.

Gmail access through Himalaya account `gmail` was verified; `myaccount@pseg.com` was observed as a sender. A matching sender alone does not authenticate an email or establish that it belongs to a newly requested login challenge.

The current `browser_vault_enter_code` interface supports a masked user prompt or a saved authenticator key, NOT automatic email retrieval. Do not claim automatic Gmail OTP completion is implemented. Do not work around the tool's secret-entry restrictions using scripts, browser JS, clipboard injection, or direct CDP entry.

## Procedure

1. Open exactly `https://nj.myaccount.pseg.com/user/login` with `browser_exec`. A redirect to `https://id.myaccount.pseg.com` was observed and is the expected PSE&G authentication origin. Do not reuse captured OAuth query strings, state, or nonce values.
2. Wait for rendering and inspect visible text and input metadata only (not values). A blank page, title, or HTTP 200 is not a ready login form. If still blank after one reload and a bounded wait, stop authentication and report the page blocker. Do not send login URLs containing session state or private account pages to archives or proxy services.
3. Call `browser_vault_list`. Use only an item bound to the exact authentication origin. If no item exists, use `browser_vault_save_login(label='PSE&G My Account')` to prompt privately for username/password, but ONLY after a real PSE&G password form is present. Check that the private prompt names `id.myaccount.pseg.com`; cancel if it names another domain. Verify the returned origin before proceeding. Never guess a username, request a password in chat, or put credentials in this skill.
4. Fill the returned identifier using `fill_input` and the currently observed username selector. Enter passwords only through `browser_vault_fill` (the save tool may already have filled it). Submit the actual sign-in control once and inspect the resulting state. Avoid repeated submissions on failure.
5. When offered email MFA, choose email only if its masked destination matches the user's Gmail. Record the request time from the live system clock before requesting a code. Do not switch security settings, enroll factors, or select persistent trust/remember-device options without approval.
6. Gmail scope is ONLY Himalaya account `gmail` (`eluzix@gmail.com`), not `shuki` or `icloud`. Load `himalaya` and discover installed CLI help. Search INBOX for recent PSE&G mail. Keep OTP message bodies and subjects out of tool output because subjects may contain codes. Use sender/time metadata to check delivery; do not confuse historical messages with the current challenge. Never print, save, or repeat an OTP in chat or the skill.
7. For the current supported flow, call `browser_vault_enter_code(handle=the_current_login_handle)` to obtain the code through the private UI. Be explicit that the user must read the email and enter it there: automatic Gmail-to-vault transfer is not available in this interface. If the user requires fully automatic OTP, report the capability blocker instead of claiming completion.
8. After OTP submission, verify navigation back to the official account portal plus visible authenticated account content and absence of the login/MFA form. Read the requested account view without changing anything. Avoid exposing complete account numbers or addresses unnecessarily.

## Safe Gmail delivery check

Installed syntax was verified as:

`himalaya --account gmail --json envelope search --mailbox INBOX --page-size 20 'from pseg order by date desc'`

Run it through `subprocess.run(..., capture_output=True)` inside `execute_code` or a terminal Python helper, parse JSON, and print only sender/date metadata. The observed JSON shape is `{'envelopes': [...]}`. Never dump the complete response: an OTP can appear in a subject. Apply the current challenge timestamp and a bounded retry window; no indefinite polling and no repeated resend clicks. This checks delivery metadata, not the code itself.

## Pitfalls

- A credential label does not determine its origin. The vault save implementation can select another tab containing a password field when the intended page has no form. A PSE&G label with another origin is a failed setup, not a usable credential.
- Do not call the save-login tool on the blank page. Do not close or alter unrelated user tabs to hide a routing problem. Resolve browser/vault targeting before another credential attempt.
- Stop on `save_declined`; do not prompt again that turn. On `prompt_unavailable`, tell the user to use an interactive Hermes session.
- Do not read input values, full page source, or OAuth tokens for routine diagnostics. Prefer origin, title, visible labels, input types, and narrowly filtered errors.
- Reuse a valid existing authenticated session when available, but still verify the actual account page before reporting login success.

## Verification

Report these independently:
- Skill installed and discoverable.
- Credential saved against the exact PSE&G origin and filled into its real form.
- New email challenge delivered to the intended Gmail account.
- MFA completed via the supported private mechanism.
- Authenticated PSE&G account content visible.

Only mark the account connection working when the last four checks have actually succeeded. Until then, report partial setup and the precise blocker.
