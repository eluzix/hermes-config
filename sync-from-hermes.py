#!/usr/bin/env python3
"""Copy non-secret Hermes settings from ~/.hermes into this repo.

One direction: home -> repo. Never reads secrets into the destination.
Catalog plugins are recorded as pins; only local plugin source is copied.
Re-run after changing plugins or settings. Does not git commit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser().resolve()

# Skills written for this install. Upstream/catalog skills are reinstalled, not vendored.
PERSONAL_SKILLS = (
    "productivity/family-finance",
    "productivity/family-schedule-management",
    "productivity/genesis",
    "productivity/icloud-calendar",
    "productivity/pseg-account",
    "productivity/righttoschool",
    "productivity/school-bitez",
)

PROFILE_FILES = (
    "config.yaml",
    "SOUL.md",
    "profile.yaml",
    "tui-theme-boot.json",
)

# Job definition fields. Runtime bookkeeping (last_*, fire_claim, snapshots) stays home.
JOB_KEYS = (
    "id",
    "name",
    "enabled",
    "paused_at",
    "paused_reason",
    "schedule",
    "schedule_display",
    "repeat",
    "prompt",
    "deliver",
    "failure_deliver",
    "enabled_toolsets",
    "skill",
    "skills",
    "script",
    "no_agent",
    "model",
    "provider",
    "base_url",
    "origin",
    "workdir",
    "attach_to_session",
    "monitor_script",
    "monitor_url",
)

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}

CREDENTIAL_NAMES = {
    ".env",
    "auth.json",
    "creds.json",
    "vault",
    "vault.key",
    "vault.json.enc",
    "google_token.json",
    "google_client_secret.json",
    "google_oauth_pending.json",
    ".op.env",
    "npmrc",
    "honcho.json",
    "mem0.json",
    "eluzix.kdbx",
    "eluzix.key",
}

SECRET_CONTENT = re.compile(
    r"(sk-[A-Za-z0-9]{16,}"
    r"|ghp_[A-Za-z0-9]{16,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xai-[A-Za-z0-9]{16,}"
    r"|AIza[0-9A-Za-z_-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"
    r"|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)"
)
ASSIGN_LITERAL = re.compile(
    r"(?i)\b(password|passwd|api_key|app_password|client_secret|access_token|refresh_token)"
    r"\b\s*[:=]\s*['\"][^'\"]{8,}['\"]"
)

REFUSED: list[str] = []
WRITTEN: set[Path] = set()


def refuse(rel: str, reason: str) -> None:
    REFUSED.append(f"{rel}: {reason}")


def credential_path(path: Path) -> bool:
    parts = {p.casefold() for p in path.parts}
    if parts & {n.casefold() for n in CREDENTIAL_NAMES}:
        return True
    name = path.name.casefold()
    if name.endswith((".kdbx", ".key", ".pem", ".p12")):
        return True
    if name.startswith(".env") and name != ".env.example":
        return True
    if "session" in parts and name == "creds.json":
        return True
    return False


def looks_secret(text: str) -> bool:
    return bool(SECRET_CONTENT.search(text) or ASSIGN_LITERAL.search(text))


def write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    WRITTEN.add(dest.resolve())


def copy_file(src: Path, dest: Path, label: str) -> None:
    if credential_path(src) or credential_path(dest):
        refuse(label, "credential path")
        return
    data = src.read_bytes()
    if b"\0" in data:
        refuse(label, "binary")
        return
    text = data.decode("utf-8", errors="replace")
    if looks_secret(text):
        refuse(label, "secret-shaped content")
        if dest.exists():
            dest.unlink()
        return
    write_bytes(dest, data)


def copy_tree(src: Path, dest: Path, label: str) -> None:
    if not src.is_dir():
        refuse(label, "missing")
        return
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".lock")]
        for name in filenames:
            src_file = Path(dirpath) / name
            if src_file.suffix in SKIP_SUFFIXES or name.endswith(".lock"):
                continue
            rel = src_file.relative_to(src)
            copy_file(src_file, dest / rel, f"{label}/{rel.as_posix()}")


def env_example(src: Path, dest: Path, label: str) -> None:
    if not src.is_file():
        return
    names: list[str] = []
    for line in src.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if name and name not in names:
            names.append(name)
    body = (
        "# Names only. Values stay in the Hermes home .env and are never copied here.\n"
        + "".join(f"{name}=\n" for name in names)
    )
    if looks_secret(body):
        refuse(label, "secret-shaped env name")
        return
    write_bytes(dest, body.encode())


def plugins_lock(src: Path, dest: Path) -> None:
    if not src.is_file():
        return
    meta = json.loads(src.read_text())
    lines = [
        "# Catalog plugins. Reinstall with `hermes plugins install`; do not vendor the trees.",
        "",
    ]
    for name in sorted(meta):
        entry = meta[name] if isinstance(meta[name], dict) else {}
        catalog = entry.get("catalog") if isinstance(entry.get("catalog"), dict) else {}
        lines.append(f"{name}:")
        for key in ("source", "revision"):
            if entry.get(key):
                lines.append(f"  {key}: {entry[key]}")
        if "pinned" in entry:
            lines.append(f"  pinned: {str(bool(entry['pinned'])).lower()}")
        if catalog:
            lines.append("  catalog:")
            for key in ("name", "repo", "sha", "pin", "tier"):
                if catalog.get(key):
                    lines.append(f"    {key}: {catalog[key]}")
        lines.append("")
    text = "\n".join(lines)
    if looks_secret(text):
        refuse(dest.name, "secret-shaped plugin pin")
        return
    write_bytes(dest, text.encode())


def local_plugins(profile: Path) -> list[Path]:
    plugins = profile / "plugins"
    if not plugins.is_dir():
        return []
    catalog: set[str] = set()
    meta_path = plugins / ".install-metadata.json"
    if meta_path.is_file():
        catalog = set(json.loads(meta_path.read_text()))
    found = []
    for child in sorted(plugins.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in catalog:
            continue
        if (child / "plugin.yaml").is_file():
            found.append(child)
    return found


def cron_jobs(src: Path, dest: Path, label: str) -> None:
    if not src.is_file():
        return
    raw = json.loads(src.read_text())
    jobs = raw.get("jobs", raw if isinstance(raw, list) else [])
    cleaned = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        item = {key: job[key] for key in JOB_KEYS if key in job and job[key] not in (None, "", [], {})}
        blob = json.dumps(item, ensure_ascii=False)
        if looks_secret(blob):
            refuse(f"{label} job {job.get('id', '?')}", "secret-shaped job field")
            continue
        cleaned.append(item)
    text = json.dumps({"jobs": cleaned}, indent=2, ensure_ascii=False) + "\n"
    write_bytes(dest, text.encode())


def sync_profile(profile: Path, dest: Path, label: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in PROFILE_FILES:
        src = profile / name
        if src.is_file():
            copy_file(src, dest / name, f"{label}/{name}")
    skins = profile / "skins"
    if skins.is_dir():
        for skin in sorted(skins.glob("*.yaml")):
            copy_file(skin, dest / "skins" / skin.name, f"{label}/skins/{skin.name}")
    env_example(profile / ".env", dest / ".env.example", f"{label}/.env.example")
    plugins_lock(profile / "plugins" / ".install-metadata.json", dest / "plugins.lock.yaml")
    for plugin in local_plugins(profile):
        copy_tree(plugin, dest / "plugins" / plugin.name, f"{label}/plugins/{plugin.name}")
    for rel in PERSONAL_SKILLS:
        src = profile / "skills" / rel
        if (src / "SKILL.md").is_file():
            copy_tree(src, dest / "skills" / rel, f"{label}/skills/{rel}")
    cron_jobs(profile / "cron" / "jobs.json", dest / "cron" / "jobs.json", f"{label}/cron/jobs.json")


def prune(dest: Path) -> None:
    """Drop managed files this run did not write. Leave the script, gitignore, and .git."""
    keep_root = {"sync-from-hermes.py", ".gitignore"}
    owned_root = {"plugins", "skills", "skins", "cron", "profiles", *PROFILE_FILES, ".env.example", "plugins.lock.yaml"}
    for dirpath, dirnames, filenames in os.walk(dest, topdown=False):
        current = Path(dirpath)
        rel_dir = current.relative_to(dest)
        if rel_dir.parts and rel_dir.parts[0] == ".git":
            continue
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = current / name
            if path.resolve() in WRITTEN or (current == dest and name in keep_root):
                continue
            rel = path.relative_to(dest)
            if rel.parts[0] in owned_root:
                path.unlink()
        if current != dest and not any(current.iterdir()):
            current.rmdir()


def main() -> int:
    if not HOME.is_dir():
        print(f"Hermes home not found: {HOME}", file=sys.stderr)
        return 1
    sync_profile(HOME, REPO, "default")
    profiles = HOME / "profiles"
    if profiles.is_dir():
        for child in sorted(profiles.iterdir()):
            if child.is_dir() and ((child / "config.yaml").is_file() or (child / "SOUL.md").is_file()):
                sync_profile(child, REPO / "profiles" / child.name, child.name)
    prune(REPO)
    copied = sorted(p.relative_to(REPO).as_posix() for p in WRITTEN)
    print(f"home: {HOME}")
    print(f"dest: {REPO}")
    print(f"wrote {len(copied)} files")
    for rel in copied:
        print(f"  {rel}")
    if REFUSED:
        print(f"refused {len(REFUSED)}", file=sys.stderr)
        for item in REFUSED:
            print(f"  {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
