---
name: genesis
description: Checks Tenafly Genesis records and required forms for the children.
version: 1.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [Genesis, Tenafly, parent portal, students, forms]
    category: productivity
---

# Tenafly Genesis

Read Tenafly Parent Access for Itamar, Alona, Shahar, and Yuval. Always check Forms for each requested child. Reading never authorizes signing, acknowledging, submitting forms, paying fees, reporting absences, or changing records.

## Secure login — browser vault only

- Use the dedicated headless browser, not personal visible Chrome. Use the default `browser_exec` session so `browser_vault_fill` targets the same browser/tab.
- Origin: `https://parents.tenafly.k12.nj.us`. Parent-session entry: `/genesis/parents`. Fresh-login entry: `/genesis/sis/view?gohome=true`.
- KeePassXC entry `genesis-eluzix` is exposed through `browser_vault_list`. The default profile has `vault.keepassxc.origin_overrides.genesis-eluzix` bound to the exact Genesis origin. If missing, configure that metadata with `hermes config set vault.keepassxc.origin_overrides.genesis-eluzix https://parents.tenafly.k12.nj.us`, then list again. Never copy a password into another vault or ask for it in chat.
- Do NOT run the old `scripts/login.py` credential-reading helper. Password entry is only through `browser_vault_fill`; do not retrieve or type passwords with subprocess, terminal, browser helpers, or custom code.
- Before navigating a new task tab, read `Browser.getVersion`, then apply a tab-scoped `Network.setUserAgentOverride` replacing only `HeadlessChrome/` with `Chrome/`. Unadjusted headless identity can return HTTP 405. Do not change global browser settings, disable TLS, or switch to personal Chrome.
- Require exact HTTPS origin, visible `#j_username` (email) and `#j_password` (password), and a same-origin POST login form. Observed endpoints are `/genesis/j_security_check?parents=Y` and `/genesis/sis/j_security_check?parents=Y` depending on entry route.
- Call `browser_vault_list` first. Type only the returned non-secret identifier into `#j_username`. Find the fresh `genesis-eluzix` handle bound to Genesis.
- Genesis lacks standard autofill hints. Before vault fill, set `autocomplete=username` on `#j_username` and `autocomplete=current-password` on `#j_password`. This resolves the observed `No fillable login field matched` error without changing form field names or submitting it. Focus the password input if needed.
- Close only duplicate Genesis tabs created by this task; preserve unrelated tabs. Inspect CDP target type/path without printing session-bearing URLs. Require a single task login tab before fill.
- Call `browser_vault_fill`, verify password presence (never value) in the controlled tab and expected identifier, then click the verified Login submit exactly once.
- Authentication requires exact Genesis origin, `/genesis/parents`, no password input, `.selectStudentItem.selected`, and the Forms menu. A redirect alone is insufficient.
- Stop after one failed sign-in. The portal locks after four failures, but that is not a retry allowance. Use `browser_vault_enter_code` for verification codes; never type codes. Stop for CAPTCHA, password reset, or consent.
- Never print form values, credential lengths/fragments, cookies, tokens, complete DOM, or credential-bearing screenshots. Close only the task tab when finished, preserving shared cookies.

## Child selection

The top-right student selector is a custom dropdown, not the language `select`.

1. Click `[onclick="toggleSelectableStudents(this)"]` and confirm `#selectableStudents` is displayed with a real height before clicking a student. A hidden menu makes `a.click()` no-op and leaves the previous child selected.
2. Match exactly one `#selectableStudents .selectStudentItem` by displayed first name, normalizing whitespace/nonbreaking spaces. Click its `a`; never construct student IDs. Do not use coordinate clicks: the default 780px viewport parks this menu off-screen, and the anchors have zero width even after widening, so `click_at_xy` misses.
3. Poll until `.selectStudentItem.selected` matches the requested child and page reload completes. Fixed one-second waits were insufficient; use a bounded wait and verify again after navigation.
4. Re-read the current menu after switching. Opening bare `/genesis/parents` may reset the default child; follow live selected-page links.

## Read-only navigation

Use `.mainMenuTabs a` by exact displayed label and verify its same-origin destination. Do not print full URLs with sensitive query values.

- Summary, Attendance, Grading, Documents, Forms, Letters are available for all four children.
- Itamar also has Fees And Fines, Gradebook, and Athletics. Recheck live availability; never assume menus are identical.
- Forms expands to Forms Library; prefer exact `Forms` label to avoid submenu ambiguity.
- Do not use Contacts, Settings, Logout, parent account controls, or absence-reporting controls to select children.

## Mandatory Forms check

- Verify selected child, open Forms, and scope extraction from `Forms for <child>` to the next sibling heading. All four groups may appear on one page, with selected child first. Select/check each child independently for all-child requests.
- Inspect complete applicable list, filters, pagination, required/optional markers, dates, missing-signature/action messages.
- `Submitted: <date>` is completed even when `Required for Access` remains displayed. `Not Yet Submitted` plus an explicit required marker needs attention.
- Unsubmitted forms without an explicit requirement are **applicability unconfirmed**, not automatically mandatory or optional. Athletic forms may depend on participation.
- Preserve `Fillable Thru` wording; it is an availability end date, not necessarily a participation deadline.
- Never open controls with unclear effects or answer/sign/submit forms just to determine status.
- The School Meals and Summer EBT Apply panel is conditional, not proof of a required outstanding form. Do not click Apply.
- Return one Forms outcome per child: no required form actions shown, action required with names/statuses/dates, or unverified with blocker. Never treat inaccessible/empty filtered results as all clear.

## Other administrative to-dos

For general to-do checks, inspect current-year Documents and Letters lists and Itamar's Fees And Fines in addition to Forms. Require each list header names the correct child and verify the selected year. Signed document dates support completion; blank cells alone do not establish a missing required signature. Report unsigned informational documents separately only when action applicability is clear. Do not open/acknowledge documents or pay fees during reading. Letters with `No records have been found` are empty for the selected year, not all historical years.

For multi-child work, append each child to a workspace JSON file, then aggregate/count with Python and require four unique requested children. Keep explicit findings per child. A forms/documents check is not a homework audit; inspect Gradebook separately only if that is requested.

## Verification and lessons

The secure vault login was exercised against the live portal after configuring the existing entry's origin and adding standard autocomplete hints. Each child's Forms, Documents, and Letters was independently read; Itamar's fee balance was also inspected. No records, signatures, applications, or payments were submitted. Live results are not permanent all-clear facts; recheck each request.
