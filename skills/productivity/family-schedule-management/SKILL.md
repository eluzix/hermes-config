---
name: family-schedule-management
description: "Use when managing family schedules, tasks, and reminders."
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [family, schedules, tasks, reminders, profiles, cron]
    category: productivity
---

# Family Schedule Management

Manage structured family events, tasks, things to bring, and reminders. Prefer the `family_tasks_ingest` and `family_tasks` plugin tools over free-form memory so dates, children, status, and locations remain queryable.

## Core workflow

1. Preserve the user's wording for titles, dates, times, children, locations, and details.
2. Ingest one message containing several child-specific items together when the source groups them; the plugin should create distinct entries.
3. Read back the created entries and verify every named child and time. Do not claim success from intent alone.
4. For queries such as “all back-to-school nights,” search broadly enough to catch punctuation variants such as `Back to School` and `Back-to-School`; if one search is incomplete, retry with a stable shared phrase such as `School Night`.
5. Present results chronologically, grouped by date, with each child on a separate line.

## Today's school briefing

1. Resolve today with the live clock in America/New_York, then query the shared family agenda for that exact date.
2. Refresh and check all connected calendars, including iCloud and Google; supplement them with recent school announcements and newsletters from Gmail and iCloud email. If a source fails, state the coverage gap rather than interpreting it as an empty schedule.
3. Search Gmail's `[Gmail]/All Mail` when Inbox searches are sparse; archived school notices still contain current spirit-day and activity instructions. Inspect installed Himalaya help before using search syntax: newer versions use `himalaya --account gmail --json envelope search --mailbox '[Gmail]/All Mail' 'after YYYY-MM-DD and (from tenafly.k12.nj.us or from membershiptoolkit.com)'`.
4. Match each item to today's date or an explicit recurring weekday. Keep optional programs separate from confirmed attendance, include permission-slip requirements, and do not label yesterday's picture day or next week's event as happening today.
5. Lead with what each child needs to wear or bring, grouped by school, followed by today's timed activities. Add only immediately actionable operational notices, such as cancelled lunch-vendor orders requiring replacements; omit the rest of the newsletter.

## Full weekly agenda and email reconciliation

1. Resolve the requested week from the live America/New_York clock and state the exact Monday–Sunday range. On a Sunday, interpret an upcoming-school-week request as the following Monday–Friday, including the weekend when the user requests all activities.
2. Query dated shared-family entries and refresh all connected calendars. Inspect undated tasks separately; do not attach stale pickup instructions, old appointments, or an undated obligation to the coming week. A birthday without a party time, venue, or child association is a family note, not a confirmed child's appointment.
3. Check the email accounts the user authorized. An explicit request for both parents' or all their emails includes Shuki's mailbox for that request; ordinary "my email" does not. Search both recent school/activity senders and date/event terms, then inspect recent envelope subjects to catch image-heavy notices and non-school activities. Read actual notices and newer corrections, not search snippets alone.
4. Reconcile candidates by child, title, date, and time before ingesting missing events or tasks into the shared family schedule. Preserve source provenance and distinguish booked attendance, optional opportunities, deadlines, and things to bring. Read back every addition; permission to update the shared schedule is not permission to purchase, register, or independently modify Apple/Google calendars.
5. Present a chronological day-by-day agenda with each child's activities, exact known times, clothing/supplies, deadlines, and relevant lunch coverage. Use the verified School Bitez orders rather than the general menu; flag unfilled meal days without interpreting a closure as a missing order. Keep optional programs and undated outstanding tasks in separate sections.
6. Disclose inaccessible calendars or mailboxes in the agenda itself; a failed authorization is not an empty calendar, and a partial scan must not be labeled complete.
7. Resolve every requested delivery destination before sending. If the user requests their and Shuki's WhatsApps, deliver to both WhatsApps rather than substituting the current Telegram chat. Discover targets with `hermes send --list whatsapp` and `hermes -p shuki send --list whatsapp`; use each profile's `hermes send --json --to <discovered-target> --file <agenda-file>`. Preserve the same reconciled message for both recipients, record returned message identifiers, and distinguish provider acceptance from recipient receipt or read confirmation. Never retry an ambiguous send blindly.

## Research school celebrations and costume days

1. Search the named school announcements and HSA newsletters in the user's authorized mailboxes, including Gmail All Mail and iCloud Archive when needed. Search both event terms and school senders: image-heavy newsletters may not match a keyword search.
2. Read the newest relevant newsletter and any later standalone update before trusting a calendar entry; postponement notices can supersede both earlier mail and public calendars.
3. Follow the principal's letter, linked PDF, or event notice for exact date/time and instructions. Find the real HSA domain from school mail or official links rather than guessing similar hostnames that may redirect to vendor marketing.
4. Check requested portals and school websites separately. Keep a login-gated HSA calendar or inaccessible portal explicit as a coverage gap; an empty public calendar does not establish that no event exists.
5. Report separately by school, with date/time first, followed by costume arrival/change instructions, restrictions, lunch arrangements, and whether families may attend. Distinguish costume parades from carnivals, class celebrations, and grade hangouts; do not transfer one school's instructions to another or label an unrelated hangout a Halloween party.
6. When an event is unconfirmed, state which sources were checked and what remains inaccessible rather than supplying a likely date. Cite the primary notice for confirmed details.

## Ticket confirmations and event reminders

1. Resolve an ambiguous show from an authorized confirmation email when the user supplies the sender or mailbox. Preserve an earlier request to create a reminder across the follow-up lookup; once the confirmation uniquely identifies the show, finish scheduling rather than asking again for details already retrieved.
2. Extract the event title, local date/time/timezone, venue, ticket quantity, section/row/seats, and any arrival or mobile-entry instructions. Read the actual confirmation, not a promotional or authentication email. For HTML/MIME extraction use [references/email-event-confirmations.md](references/email-event-confirmations.md); never expose ticket barcodes, authentication codes, or ticket-management tokens.
3. Compute the requested offset with timezone-aware code from the event's local start. For a week-before reminder with no other preference, use seven calendar days before at the same local time; account for daylight-saving transitions.
4. Check existing reminders for duplicates, create a one-shot reminder in the requesting chat, and read back its scheduled time and destination. Include self-contained event details in its prompt so it does not depend on this conversation. Do not create a calendar event or transfer tickets unless separately requested.
5. Confirm briefly with the identified show, event date/venue, and reminder date/time/timezone. Distinguish a scheduled reminder from an alert that has already been delivered.
6. If the user reports a cron failure, inspect the current job list and identify the actual failed job before attributing it to the reminder most recently discussed. Explain the recorded failure and any partial success; a future reminder with no run history has not failed merely because another job emitted a notice.

## Event conventions

- A date without a time is an all-day event.
- Keep room/location labels exactly as supplied, even when they are terse identifiers such as “location 4.”
- Keep explanatory details, such as when pictures will be taken, in the event details rather than discarding them.
- Do not invent end times, locations, reminders, or calendar synchronization.

## Live school homework decks

- For a public Google Slides homework calendar, verify that `/presentation/d/<id>/export/txt` returns current nonempty content before scheduling a live check. A cron pre-run script should fail nonzero on fetch/validation errors; never turn a failed fetch into a false “no homework.”
- Date-match the daily slide, not the month overview or yesterday's slide. Skip blank/"none"/"No HW" cells and stale boilerplate. Follow external planner links in a named teacher row and distinguish lesson headings from homework; fail explicitly if a required planner is inaccessible rather than reporting a false no-homework day. Keep teacher-specific rows labeled; for Itamar, track both Language Arts (Snyder and Lyons) and both Math (Lydon and Argerakis), including Argerakis's linked Algebra 7 planner.
- Recover links missing from the Slides text export by downloading `/presentation/d/<id>/export/pptx` and reading the ZIP locally: identify the date-matched `ppt/slides/slideN.xml`, then inspect its `ppt/slides/_rels/slideN.xml.rels` for external hyperlink targets. Follow the actual teacher-planner link rather than guessing a URL; plain-text exports preserve "Click here" labels but omit their destinations.
- Use an agent cron job for interpreting a changing deck; send `[SILENT]` when there is neither actual homework nor an exam reminder. Schedule at the user's requested local time and read back the job's next run/destination.
- Register only explicitly dated quizzes/tests in family tasks, check duplicates, and remind on exactly the 3-day and 1-day offsets. Undated test mentions are not schedulable.

## Multiple Hermes profiles

Profiles isolate plugins, plugin data, scripts, cron jobs, and delivery settings. Sharing a family agenda therefore requires both capability and data:

- Install and enable the family-tasks plugin in every participating profile.
- Point each profile's family-tasks storage at the same intentional shared store; never point two agents at the same complete `HERMES_HOME`.
- Keep cron jobs per-profile so each agent can deliver to its own home channel.
- Verify the shared data from both profile paths before announcing that sharing works.

See [references/multi-profile-sharing.md](references/multi-profile-sharing.md) for the validated setup and verification sequence.

## Weekly reconciliation and family delivery

- Resolve the upcoming Monday–Sunday dates from the live local clock. Read the shared dated agenda before adding anything; keep stale undated tasks out of the week's commitments.
- When the user explicitly asks for "all our emails," include the authorized spouse mailbox as well as the user's Gmail/iCloud. Otherwise retain normal mailbox ownership boundaries. Scan archived mail and older enrollment receipts: recent newsletters alone miss ongoing clubs and child assignments.
- Verify each enrolled child's activity from an individualized receipt. A family-wide cancellation may omit the child's name; join it to the original receipt before assigning pickup changes. New cancellation and pickup-policy notices supersede old confirmation instructions, but do not cancel unrelated clubs.
- If old afterschool registration and recent attendance disagree, inspect each child's live Programs enrollment covering the target week. Historical checkout times are not next week's promised pickup times; dashboard summaries alone may hide future-dated changes.
- Separate confirmed bookings, schoolwide events, optional invitations, and unresolved items. Prefix saved optional entries OPTIONAL/IF PARTICIPATING, preserve participation prerequisites and conflicts, and never turn a generic invitation into an enrollment. Do not infer a weekly recurrence from a single special-event date or initial meeting notice.
- Follow newsletter links and inspect rendered content when extraction is sparse: a principal newsletter's missing middle can contain project deadlines, and an image-only flyer can contain the only event date. Distinguish simultaneous projects (for example a library pumpkin and a STEAM model) instead of merging their deadlines.
- Ingest only verified new items and corrections into the shared family store, then read back exact children, times, optional labels and date windows. For an inclusive multi-day all-day window use an explicitly documented exclusive end-date boundary. Do not assume a null edit clears a field; inspect the returned record and verify.
- For WhatsApp delivery use the appropriate profile's `hermes send --list whatsapp`, then `hermes [-p <profile>] send --json --to whatsapp:<exact-id> --file <agenda>`. Check the matching bridge health, preserve per-profile channel ownership, and verify both send receipts and exact-message readback in the destination's mirrored conversation. Do not claim the recipient read the message.
- Deliver a day-by-day confirmed agenda with lunch/bring/pickup instructions, followed by clearly separate optional choices and source gaps. A failed calendar authorization is a coverage gap, not an empty calendar. Preserve the complete delivered text as a local artifact.

## Scheduled agendas

For deterministic daily or weekly agendas, use script-only cron jobs:

- The script queries the family-tasks agenda and prints only the formatted result.
- Non-zero query failures must surface as errors.
- Empty stdout should produce no message.
- Create the job inside the destination profile and set delivery to that profile's intended platform/home channel.
- Verify the script manually, confirm the profile gateway is running, then read back the cron list.

## Pitfalls

- A plugin enabled in config but absent from the profile's plugin directory may leave stale toolset metadata while the CLI capability is unavailable. Verify with the profile's plugin listing.
- Copying cron definitions without profile-local scripts produces jobs that exist but cannot run.
- A narrow punctuation-sensitive search can omit valid family entries.
- Profile cloning does not imply ongoing shared data or cloned cron jobs.
