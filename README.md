# hermes-config

One-way backup of Hermes settings. Source of truth is `~/.hermes`. This repo is the copy.

```bash
python3 sync-from-hermes.py
```

The script copies an allowlist, then deletes managed files it did not write. It does not commit.

Included: `config.yaml`, `SOUL.md`, skin, theme, local plugins (`family-tasks`, `roku-control`), personal skills, cron job definitions, and the `shuki` profile. Catalog plugins are pins in `plugins.lock.yaml`, not the plugin trees. `.env.example` has names only.

Not included: `.env`, `auth.json`, vault, KeePass, OAuth tokens, WhatsApp sessions, memories, databases, and upstream skills. `.gitignore` blocks those names if they are copied in by hand. The script also refuses secret-shaped file contents.
