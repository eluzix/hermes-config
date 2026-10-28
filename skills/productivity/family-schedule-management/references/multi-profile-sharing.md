# Sharing Family Tasks Across Hermes Profiles

This pattern was validated with two independently running Hermes profiles that need one shared family-task database and separate delivery channels.

## Preconditions

- Each profile has its own gateway and `HERMES_HOME`.
- The family-tasks plugin is installed and enabled in each profile.
- The chosen source database is healthy.
- The destination profile has no independent family-tasks data that would be lost. If it does, stop and merge or back it up first.

## Shared storage pattern

The plugin's sanctioned storage is:

```text
$HERMES_HOME/plugin-data/family-tasks/data.db
```

Keep one canonical directory and link the other profile's `plugin-data/family-tasks` directory to it. Share only this plugin-data directory—not the whole profile home. SQLite WAL mode supports the plugin's concurrent readers/writers.

Before linking:

1. Stop if the destination directory already contains a database.
2. Create the destination profile's `plugin-data/` parent.
3. Link `family-tasks` to the canonical directory.
4. Resolve both paths and confirm they target the same `data.db`.
5. Open both paths read-only and verify the same entry count.

## Capability verification

Data sharing is insufficient if the destination profile cannot load the plugin:

1. Run the destination profile's compact plugin listing.
2. Require `family-tasks` to appear as an enabled user plugin.
3. Restart that profile's gateway after installing plugin code.
4. Confirm the gateway is running.

## Per-profile agenda delivery

Place the deterministic daily and weekly scripts under the destination profile's `scripts/` directory. Run both manually and require real agenda output before scheduling.

Create separate no-agent jobs in the destination profile, for example:

```text
Daily:  0 7 * * *
Weekly: 0 18 * * 0
```

Set `--deliver whatsapp` (or another platform) only when that profile's home channel is configured for the intended recipient. Finally, list the destination profile's cron jobs and verify names, schedules, scripts, mode, enabled state, and delivery target.

Do not test-deliver a live agenda merely to prove routing unless the user requested a test message; cron configuration plus gateway/home-channel verification is enough for setup, while the first scheduled run confirms end-to-end delivery.
