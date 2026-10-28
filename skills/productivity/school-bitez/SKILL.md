---
name: school-bitez
description: Manage the girls' School Bitez lunch accounts.
version: 0.2.0
author: Eluzix, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [School Bitez, school lunch, Alona, Shahar, Yuval]
    category: productivity
---

# School Bitez

Read and, only on an explicit request, manage Alona, Shahar, and Yuval's school lunch orders at J. Spencer Smith Elementary School. Never place, modify, cancel, or pay for an order merely to inspect it.

## When to Use

- Questions about the girls' School Bitez lunch menus, schedules, orders, receipts, or meal plans.
- Explicit requests to change a named child's lunch orders or account.

## Prerequisites

- Login URL: `https://smithschool.schoolbitez.com/#/login`.
- KeePassXC entry `schoolbitez-eluzix` in `~/.hermes/eluzix.kdbx`, unlocked with `~/.hermes/eluzix.key`. The configured `vault.keepassxc` backend exposes it to `browser_vault_list` as a `kpxc:` handle bound to the exact origin `https://smithschool.schoolbitez.com`. Its `origin_overrides` handles an entry without a saved URL. Do not use 1Password or copy the password to another vault.
- Use `browser_exec` in the default browser session for login. The vault fill targets the supervised browser's matching-origin tab, so close only extraneous School Bitez tabs you created and retain exactly one login tab before filling. A named `browser_exec(session="schoolbitez")` did not reliably receive the vault fill when other matching tabs were open. Never close unrelated tabs.
- Passwords and verification codes may only be entered with `browser_vault_fill` and `browser_vault_enter_code`; never read or type them through `terminal`, `browser_exec`, a custom helper, or chat. Do not print form values, cookies, or session tokens.

## How to Run

1. In the default `browser_exec` session, open `https://smithschool.schoolbitez.com/#/login` with `new_tab(...)`, then `wait_for_load()`. Check the exact origin, visible `#username`, visible `input[name="password"][type="password"]`, and Login button. If multiple School Bitez tabs are open, close only your own extras before opening a fresh single login tab.
2. Call `browser_vault_list`; find the `keepassxc` login labeled `schoolbitez-eluzix` with the exact bound origin. Type its returned identifier into `#username` using `browser_exec` (the identifier is non-secret metadata). Call `browser_vault_fill(handle=...)`. Do not use a remembered handle without listing it again.
3. In the same default browser session, verify only the **presence**, not the value, of the visible password field's content. A successful vault result may have filled a different same-origin tab; if the field is empty, do not submit. Require the expected username and exact origin before clicking the unique Login button once.
4. Wait for `#/parentDashboard` and verify both `Welcome Uzi Refaeli` and the read-only `My Children` area with all three girls. A redirect or app shell alone is insufficient. If login fails, stop without automatic retries. If MFA appears, use `browser_vault_enter_code`.
5. For later calls, first check whether the current browser is still authenticated; if not, repeat the safe login. Do not assume the active tab persists between calls.

## Quick Reference

All destinations are same-origin hash routes. Prefer links discovered on the current page, rather than guessing IDs or reusing session-bearing URLs.

| Area | Observed route/link | Use |
| --- | --- | --- |
| Home | `#/parentDashboard` | Order Calendar, My Children, Family Balance; read-only navigation. |
| Children | `#/children` | One card per child; named profile, Favorites, Order Schedule, New Order, Modify Orders. |
| Orders | `#/orders` | Order Date, Order Id, Child, Order Amount; link to each order detail and receipt. |
| Order detail | Follow an `#/viewOrder?orderId=...` link from Orders | Items, dates, prices, child, and total. |
| Receipt | Follow the matching `#/viewOrderReceipt?orderGroupId=...` from Orders | Inspect a requested receipt only; grouped orders may share a receipt. |
| Order Schedule | Follow the target child's `Order Schedule` link on Children (`#/order?studentId=...`) | Monthly calendar with tabs for Alona, Shahar, and Yuval; verify heading `Month, Year - <child>` after selection. |
| Meal Plans | `#/mealPlans` | Active-plan status per child. Purchase Meal Plan is state-changing. |
| Account | `#/account` | Account Details, Security, Account Balance, Settings; never activate Save Account during browsing. |

The Children page was observed with three distinct named profile and schedule links. Do not treat the dashboard's abbreviated first names or calendar default selection as proof of which child's order is shown. Load the requested child's named link and verify its header.

## Procedure

### Read-only queries

1. Verify authentication, child name, school, and date period before extraction. For an order lookup, start at Orders, locate the row by displayed child/date/order ID, then follow its observed detail link. For a schedule, start at Children and follow the requested child's Order Schedule link; verify the month/year and selected child in the calendar heading.
2. Wait for the SPA data to populate after each navigation; `wait_for_load()` alone can return before the child cards appear. Recheck the relevant text with a bounded wait.
3. Preserve displayed statuses, dates, quantities, items, and amounts. Distinguish `No Order`, `Confirmed`, school closures, and out-of-scope dates. Avoid interpreting an empty view before data loads.
4. Return only relevant information, with child and displayed period. Do not expose full account details or unrelated children's orders.

### Edits — only when explicitly requested later

- `New Order`, `Modify Orders`, `Purchase Meal Plan`, `Add Child`, `Add Funds`, `Save Account`, and changes to Favorites are state-changing or lead to state-changing flows. Do not click them during read-only browsing; edit routes and final confirmation controls have NOT been exercised.
- For an authorized change, identify exact child, dates, meals/options, quantity, deadline, amount, and consequence. Inspect the flow without final submission; show any payment or cancellation terms and obtain confirmation immediately before the final commit.
- Submit once, then reopen the relevant schedule/order detail and verify the resulting state. Never blindly retry an ambiguous submission.

## Weekly reminder

The Thursday 6pm lunch reminder should not send a bare “go order” nag. First read recent Gmail Order Confirmations from `noreply@schoolbitez.com` (account `gmail` only; search `[Gmail]/All Mail` if Inbox is empty) and compare purchased dates to the coming school week. If those days are already covered, say so and name any uncovered school day. Do not treat a district closure as a missing order. Confirmations through Oct 14, 2026 covered Monday lunch, Thursday breakfast, and Friday lunch plus ice cream, and skipped both Tuesday and Wednesday. Confirm that against the latest receipts before calling either day a gap. The Oct 14 order already included the following Monday and Friday; the immediate next Thursday is the day this reminder exists to catch. Never place, modify, or pay from the reminder.

## Pitfalls

- The password input has hidden text and visible password variants with the same `name` and `id`; check the visible `type=password` input. Do not rely on `#password` alone.
- `browser_vault_fill` can report `filled_fields: 1` while the currently controlled tab remains empty if several same-origin tabs are open. Require one login tab and verify presence in that tab before submitting.
- Hash-route navigation can display an initial shell before API data arrives. Wait for named child/period content, not just a changed URL. On the Home Order Calendar, switching child tabs changes the active tab immediately but its five day cards may initially read `No Order` until the per-child data fetch finishes; wait and re-read the active pane before reporting an empty week.
- On the Order Schedule route, changing `studentId` in the hash may leave Alona selected; click the named child tab and require the visible `September, 2026 - <child>` (or current month) heading. The DOM retains hidden calendars for other children, so scope day/order extraction to the `.sb-calendar` with `checkVisibility()`; the first match can be stale. The `.week-section` containing `Mon 28` has a first `.week.flex` row of date labels and a second row of parallel day containers; index the second row by the date position. Wait after tab selection for that child's calendar data to populate.
- Never screenshot a password form after filling; authenticated dashboard screenshots are okay if they contain only the user's account data and are handled privately.

## Verification

- Live login succeeded using the `keepassxc` browser-vault handle: exact origin, non-secret username metadata, password field populated server-side, Login clicked once, and `https://smithschool.schoolbitez.com/#/parentDashboard` displayed `Welcome Uzi Refaeli`, all three girls, an Order Calendar, and a family balance. A full-page authenticated dashboard screenshot was saved to `~/.hermes/school-bitez-login-proof.png`. No account changes were made.
- Children, Orders, Meal Plans, a named child's Order Schedule, one Order detail, and Account were opened read-only. The displayed routes and fields above were observed; edit flows and receipt contents remain untested.
- Each future query must reverify live authentication, child, and period. Each future edit must verify the post-submit state; prior sign-in does not authorize a change.
