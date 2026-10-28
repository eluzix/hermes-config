---
name: icloud-calendar
description: "Use when managing Apple iCloud Calendar via CalDAV."
version: 1.0.0
metadata:
  hermes:
    tags: [calendar, icloud, apple, caldav, khal, vdirsyncer]
---

# iCloud Calendar

The user's Apple Calendar account `uzix@me.com` is connected over CalDAV.

## Installed configuration

- Remote: `https://caldav.icloud.com/`
- Sync: `vdirsyncer` using pair `icloud_calendar`
- Calendar CLI: `khal`
- Timezone: `America/New_York`
- Secret: `ICLOUD_CALDAV_APP_PASSWORD` in `~/.hermes/.env`; never print or expose it
- Local calendars: `~/.local/share/vdirsyncer/calendars/`

Discovered calendar names: `איתמר`, `אלונה`, `חוגים`, `Private`.

Apple Reminders and reminder-backed collections are outside this connection’s permitted scope. Do not inspect or access VTODO data unless the user explicitly reconnects Reminders.

## Read workflow

Always refresh before answering:

```bash
vdirsyncer sync icloud_calendar
khal list today 7d
```

Use `khal printformats` before explicit-date queries: this installation's configured date format is `MM/DD/YYYY`, so a week query is `khal list 10/26/2026 11/02/2026`; bare ISO dates may fail to parse. Use the requested week's boundaries and verify which ending date the query includes.

Useful reads:

```bash
khal list today
khal list tomorrow
khal list today 30d
khal search "text"
khal printcalendars
```

Use `khal ... --json` when structured output is useful. Do not expose event contents beyond what the user asks for.

## Create workflow

Before creating, show the user the calendar, title, start/end (with timezone), location, recurrence, and alarms, and get confirmation. Then:

```bash
khal new -a "CALENDAR" "START" "END" "SUMMARY"
vdirsyncer sync icloud_calendar
```

After sync, refresh and search for the exact event to verify it exists.

## Edit/delete workflow

Before editing or deleting, sync, search, and identify the exact event. Show the proposed change and get confirmation. `khal edit` is interactive; for automation, locate the exact local `.ics` by UID, make a backed-up targeted change using Python's `icalendar` package, then run `vdirsyncer sync icloud_calendar`. For deletion, remove only the exact UID file after confirmation, sync, and verify it no longer appears. Never act on an ambiguous title match.

## Safety and reliability

- Reads need no confirmation.
- Creating, editing, or deleting events always requires explicit confirmation.
- Always sync before reads and before selecting an event to change.
- Always sync after local writes and verify the exact result.
- If Apple returns 401, rerun `~/.local/bin/hermes-icloud-calendar-auth`.
- Create new calendar collections through Apple Calendar/iCloud web, not vdirsyncer.
