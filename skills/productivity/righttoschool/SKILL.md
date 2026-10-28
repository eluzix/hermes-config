---
name: righttoschool
description: Retrieve and manage Right At School account information.
version: 0.1.0
author: Eluzix, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Right At School, LineLeader, family portal, childcare]
    category: productivity
---

# RightToSchool Skill

Access the user's Right At School family portal through LineLeader Manage, retrieve requested account information, and perform a portal action only when the user explicitly requests that exact action. This skill permits read-only access for information requests; it never grants autonomous permission to change portal state.

## When to Use

- The user asks about their Right At School account, children, programs, schedules, registrations, attendance, statements, invoices, payments, documents, or messages.
- The user asks to perform a specific action in the Right At School family portal.
- Do not use for public information that does not require the user's account.

## Prerequisites

- Use `browser_exec` with a named session such as `righttoschool`. Hermes is configured to attach it to a dedicated background-only Chromium at `http://127.0.0.1:9223`; it never uses the user's visible Chrome.
- The user service `hermes-headless-browser.service` keeps that browser available. If attachment fails, use `terminal` only to check `systemctl --user is-active hermes-headless-browser.service`; never switch to visible Chrome.
- Use the supplied `scripts/login.py` helper inside `browser_exec`; do not rewrite credential retrieval or type secrets through the CLI-injected helpers. The helper imports browser helpers directly to avoid argument tracing, disables telemetry and recording, checks the dedicated headless endpoint and login forms, and captures KeePassXC output privately. It uses only login controls: Not you? when needed, Continue, then Sign In.
- Never obtain credentials with a separate `terminal` call: its stdout enters the model transcript. Never print, quote, summarize, store, log, or return either value from `browser_exec`.
- The helper reads `Username` and `Password` from entry `righttoschool-eluzix`, using `eluzix.kdbx` and `eluzix.key` in this skill's owning Hermes directory. It uses `--quiet --show-protected --no-password` with captured stdout, never shell interpolation or command-line secret values.
- Credentials are read from the vault for each new sign-in, not copied into this skill or cached in a script. The helper removes exactly the CLI's final newline with `.removesuffix("\n")`, preserving intentional spaces in the stored value.
- This installation/configuration belongs to the default Hermes directory. Other profiles have independent browser settings and vaults; do not silently fall back to their visible Chrome or copy credentials between profiles.
- Canonical portal entry: `https://rightatschool.momentpath.com/`. It redirects to the LineLeader login with the correct Manage context.
- Login fallback: `https://login.lineleader.com/login?from=manage`. The bare `https://login.lineleader.com/login` may redirect to the public LineLeader marketing site when no Manage context is present.

## How to Run

1. Load this skill for a concrete Right At School request.
2. Use `browser_exec(session="righttoschool", ...)` for the entire interaction. Do not use visible Chrome, `/browser connect`, `computer_use`, or the built-in `browser_type` path.
3. Load `scripts/login.py` and call `open_portal()`. It returns an authenticated tab ID or stops with a sanitized stage-only error; it never retries sign-in automatically.
4. Complete only the read or explicitly requested portal action in that same call, verify the observed result, and close the returned tab in `finally`.

For a login-only validation, pass this Python as the `code` of `browser_exec` (not as a separate terminal command):

```python
# Validate Right At School sign-in without account changes
import runpy
from pathlib import Path
from browser_harness import helpers as browser

helper = Path("~/.hermes/skills/productivity/righttoschool/scripts/login.py").expanduser()
open_portal = runpy.run_path(str(helper))["open_portal"]
tab = open_portal()
try:
    print("Authenticated Right At School session verified.")
    # For a concrete information request, read only its selected fields here.
finally:
    browser.close_tab(tab)
```

## Quick Reference

| Intent | Permission |
| --- | --- |
| Sign in to satisfy the current request | Allowed |
| Navigate, search, filter, and view account data | Allowed for the user's information request |
| Download a requested statement or document | Allowed when the user asks for that document |
| Draft a form, message, or registration without submitting | Allowed; clearly label it as a draft |
| Submit, send, enroll, register, book, cancel, pay, upload, acknowledge, or change account data | Only when explicitly requested by the user |
| Any uncertain control that may change server state | Treat as state-changing; do not activate without an explicit request |

### ★ Navigation bookmarks

These marks are shortcuts in this skill, not changes to the portal or browser bookmarks. Use them only after `open_portal()` succeeds, inside the same `browser_exec` call. The base origin is `https://rightatschool.momentpath.com`.

| Mark | Left-menu location | Destination / selector | Use |
| --- | --- | --- | --- |
| ★ HOME | Dashboard | `/my-site` → `/overview-family`; `a.menu-link[href="/my-site"]` | Family overview, child cards, billing/document entry points. |
| ★ PEOPLE | Manage → People | `/people?tab=directory`; `a.menu-link[href="/people?tab=directory"]` | Family-accessible people and relationship links; locate a student's profile. This account shows a family User Profile view, not a staff-wide directory. |
| ★ CALENDAR | Time → Calendar | `/calendar`; `a.menu-link[href="/calendar"]` | Calendar navigation. The menu link and destination were checked; event contents and scheduling actions were not validated. |

Manage and Time are collapsed menu toggles (`a.menu-toggle`, `href="javascript:;"`), not external links. Expand the toggle whose trimmed text exactly equals `Manage` or `Time`, then wait for its child link to be visible before clicking. Alternatively, navigate to the listed same-origin destination directly. Never use a screen coordinate or a remembered menu index.

Additional family-account shortcuts (not top-level left-menu links):

| Mark | Entry point | Next control | Boundary |
| --- | --- | --- | --- |
| ★ BILLING | Dashboard → View Invoices, or `/people/QB8DmTYXWxR8pfMko` | `a.nav-link[href="#billing"]` (Billing) | Viewing only; do not pay or change payment settings. |
| ★ TRANSACTIONS | Same family-account profile | `a.nav-link[href="#transactions"]` (Transactions) | Viewing only; do not refund, void, or otherwise alter transactions. |

The family profile's Billing and Transactions tab labels/selectors were observed; their contents were not retrieved. Documents is a dashboard entry point, not an observed top-level sidebar link. Do not guess a `/documents` route or activate Go To Forms for an unrelated request.

### ★ Student area

Start at **★ HOME → the child's named card**, or **★ PEOPLE → the child's named link**. Use the real `/people/<id>` link, not an activity-feed `href="#"` link with the same name. These account-specific bookmarks stay in this local skill; do not publish or copy them into shared skills.

| Student | Exact profile name | Verified profile path |
| --- | --- | --- |
| Alona | Alona Refaeli | `/people/iRngzcejNPnTmv7n5` |
| Yuval | Yuval Refaeli | `/people/aH9EKTFzH2SWyxyH9` |
| Shahar | Shahar Refaeli | `/people/9RKBKdAKmhuPWthps` |

1. Open the requested child's saved path with `browser.goto_url(base_origin + path)`, or follow its named link from the dashboard. Wait for the profile to render; a changed URL or `document.readyState` alone is insufficient.
2. Verify `span.card-title.font-size-h3` displays the exact name from the table before reading anything. For example, poll `browser.js("document.querySelector('span.card-title.font-size-h3')?.textContent.trim() === 'Alona Refaeli'")` with a bounded wait. If the name differs, stop and rediscover the link from the current family dashboard.
3. Use the appropriate **read-only student tab** below. Wait for its corresponding pane to become active and visible before reading the requested fields.

| Mark | Student tab | Selector | Requested information |
| --- | --- | --- | --- |
| ★ STUDENT-PROFILE | Profile | `a.nav-link[href="#profile"]` | Student details; read only fields relevant to the request. |
| ★ STUDENT-ACTIVITY | Activity | `a.nav-link[href="#activity"]` | Student activity view; do not post or acknowledge anything. |
| ★ STUDENT-RELATIONSHIPS | Relationships | `a.nav-link[href="#relationships"]` | Associated people; never click Edit Relationships during browsing. |
| ★ STUDENT-PROGRAMS | Programs | `a.nav-link[href="#programs"]` | Program information; no enrollment, cancellation, or schedule changes. |

For example, `browser.js("document.querySelector('a.nav-link[href$=programs]').click()")` selects Programs; then require `browser.wait_for_element('#programs.active', timeout=15, visible=True)`. This tab transition was exercised on Shahar's profile. Alona, Yuval, and Shahar's profile headers and all four tab labels were verified. Do not assume adding `#programs` to a URL alone activates the tab.

## Procedure

### 1. Establish the request boundary

Classify the requested work before interacting with the portal:

- **Read-only:** locate, view, compare, summarize, or retrieve information. Sign-in and ordinary navigation are part of the read-only request.
- **State-changing:** any action that can alter the account or affect another person or organization, including registration, enrollment, scheduling, attendance, payments, refunds, cancellations, profile edits, uploads, messages, support requests, consent, and acceptance of terms.

A user request authorizes only the action it names. Permission is scoped to the current request, target, and parameters. Never carry permission into a later turn, broaden it to related actions, infer it from urgency, or treat a previous successful action as standing authorization.

### 2. Sign in safely

1. Run `open_portal()` as shown above, with login and the requested read in one `browser_exec` call.
2. Login is two-step. Fill `#login-identifier` / `input[name="_identifier"]`, then activate `#kt_login_continue_submit` (Continue); its form posts to `/login/identify`. Wait for the visible `#login-password` / `input[name="_password"]`. The helper validates the exact HTTPS LineLeader origin and form endpoint before each credential fill.
3. A remembered session may start directly on the password step, with `#login-email` / `input[name="_username"]` marked **read-only**. Never try to overwrite it. The helper uses the verified Not you? link at `/login/not-you` to restart identification, then verifies the resolved email matches the vault before reading the password.
4. After filling the password, the helper activates `#kt_login_signin_submit` (Sign In), then requires a loaded authenticated Meteor user on the exact Right At School origin. A redirect or an empty application shell is not proof of login. Verify the requested account surface before answering an information request.
5. Use only selected results from `browser.js(...)`; never dump the DOM, form values, cookies, tokens, the Meteor user object, subprocess objects, Python locals, or exceptions containing captured output. Never record the credential-entry sequence.
6. If the helper fails, report its stage-only error and stop. Do not reset passwords, change the account, or repeat login with the same credentials. A new attempt requires a confirmed credential correction or an identified and corrected input-delivery problem.

### 3. Retrieve information

1. Keep navigation inside the same `browser_exec` call as login. Inspect only selected labels and fields through `js(...)` or a filtered accessibility-tree query; never dump the complete DOM.
2. Navigate only to the smallest account area needed for the request.
3. Read the requested fields and preserve dates, amounts, statuses, child/program names, and document periods exactly as displayed.
4. Distinguish current data from historical data and pending items from completed items.
5. Return the requested information concisely. Mention the page or section and the retrieval time when freshness matters.

Do not click controls labeled or functioning as Save, Submit, Send, Pay, Register, Enroll, Confirm, Cancel, Delete, Upload, Accept, Acknowledge, or similar during a read-only request. Opening a modal is also forbidden when the control's effect is unclear.

### 4. Execute an explicitly requested action

Proceed only when the user's current request names the action and its target. Before the final state-changing control:

1. Verify the actor is the user's Right At School account.
2. Verify the exact child, program, date, amount, recipient, file, or other target.
3. Review the displayed consequence, total, schedule, and effective date.
4. If any material parameter is missing or ambiguous, stop before submission and ask for it.
5. For a payment, enrollment, cancellation, refund, or acceptance of legal terms, present the final displayed terms or amount and obtain explicit confirmation immediately before submission, even when the user requested the general action earlier.
6. Activate the final control once. Never retry a state-changing action until a fresh snapshot proves the first attempt did not take effect.
7. Snapshot the resulting page and report the confirmation identifier, resulting status, amount, and effective date when available.

### 5. Stop safely

- If the portal requests MFA, CAPTCHA, a password reset, new consent, or identity verification, stop and ask the user to complete or authorize that step.
- If the requested information is unavailable, report where you looked and what the portal showed; do not change filters, profiles, registrations, or account settings beyond reversible read-only navigation to manufacture a result.
- Never schedule background or recurring portal actions from this skill unless the user separately and explicitly requests the schedule and each permitted action type.

## Pitfalls

- The bare login URL can lose the Manage tenant context and redirect to the public marketing site. Start from the canonical Right At School portal.
- A remembered email can hide the first login step. A fresh isolated browser context was verified to show Email → Continue → Password. Seeing both email and password on a reused session does not mean the site has a single-step login.
- Visible Chrome can block automation behind an “Allow remote debugging?” prompt. Never use it for this skill; the configured CDP endpoint belongs to a dedicated headless Chromium with a separate profile.
- The Browser Use CLI wraps its injected helpers with argument tracing. Do not send secrets through those wrappers even if telemetry is normally off. The supplied helper imports `browser_harness.helpers` directly and explicitly disables telemetry/recording for the call.
- The CLI may normalize its HTTP CDP configuration into `BU_CDP_WS` internally; this does not mean it switched browsers. The helper validates the normalized endpoint and headless browser before reading the vault.
- Lightpanda exposes only the LineLeader application shell without this portal's login controls. Use the dedicated Chrome engine for this portal.
- A named Browser Use call may not preserve its active tab across separate invocations. Keep login plus the requested retrieval or action in one call.
- Dashboard child-card weekday summaries may reflect an enrollment ending today, not a future-dated enrollment. For a requested week, inspect each child's Programs tab and select the enrolled row whose start/end dates cover that week; `M R` means Monday/Thursday, `T R` Tuesday/Thursday. The Time → Calendar week view may show no items even when enrolled program days exist, so don't use its emptiness to negate the dated enrollment.
- Pressing Enter inside a form can submit it. Use it only for login or when the user explicitly authorized that exact submission.
- Buttons such as Continue or Next may commit data rather than merely navigate. Treat them as state-changing when their effect is not clear.
- Never report credential values, lengths, fragments, or screenshots containing them.

## Verification

- Live validation passed before the user renamed the vault entry to `righttoschool-eluzix`: the helper completed the two-step sign-in and verified a loaded authenticated user at `https://rightatschool.momentpath.com/`. Dashboard, Billing, Documents, and Children navigation were visible. The validation tab was closed without performing any account actions. This verifies the login flow and portal access, not a fresh login after the entry rename or operations within those sections; verify each future request independently.
- Navigation validation: Alona, Yuval, and Shahar's saved paths were opened and their profile-name headers matched. Shahar's Programs tab became active. Dashboard, Manage → People, and Time → Calendar destinations were inspected through read-only navigation.
- Run local safety tests with `python -B -m unittest discover -s ~/.hermes/skills/productivity/righttoschool/tests -v`. They use fake credentials and no network or real vault access.
- For read-only work, verify the answer against the current portal page and include the relevant period or status.
- For downloads, verify the requested file exists and matches the displayed document name and period.
- For state changes, verify the post-action portal state rather than relying on a click or success toast alone.
- If verification is inconclusive, report that the action is unverified and do not repeat it without a fresh explicit request.
