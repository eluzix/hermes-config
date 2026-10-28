"""CLI and slash-command surfaces for family-tasks."""

from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path

from . import extraction, service


def _settings(ctx) -> tuple[str, str]:
    return (
        str(ctx.get_config("timezone", "America/New_York")),
        str(ctx.get_config("date_order", "MDY")).upper(),
    )


def setup_parser(parser: argparse.ArgumentParser, ctx) -> None:
    subs = parser.add_subparsers(dest="family_tasks_command")

    kids = subs.add_parser("kids", help="List configured children")
    kids.set_defaults(func=lambda args: _cmd_kids(ctx, args))

    agenda = subs.add_parser("agenda", help="Show an agenda")
    agenda.add_argument("--kid")
    agenda.add_argument("--from", dest="date_from", default="today")
    agenda.add_argument("--to", dest="date_to", default="today")
    agenda.add_argument("--kind", dest="kinds", action="append")
    agenda.add_argument("--status", default="open")
    agenda.add_argument("--include-undated", action="store_true")
    agenda.add_argument("--json", action="store_true")
    agenda.set_defaults(func=lambda args: _cmd_agenda(ctx, args))

    ingest = subs.add_parser("ingest", help="Extract and save text or an image")
    ingest.add_argument("--kid", dest="kids", action="append", required=True)
    source = ingest.add_mutually_exclusive_group(required=True)
    source.add_argument("--text")
    source.add_argument("--file")
    ingest.add_argument("--caption", default="")
    ingest.add_argument("--source-type", choices=["text", "image", "email", "whatsapp", "telegram", "manual"])
    ingest.add_argument("--platform")
    ingest.add_argument("--message-id")
    ingest.add_argument("--sender")
    ingest.add_argument("--received-at")
    ingest.set_defaults(func=lambda args: _cmd_ingest(ctx, args))

    complete = subs.add_parser("complete", help="Mark an entry completed")
    complete.add_argument("id")
    complete.set_defaults(func=lambda args: _cmd_status(ctx, args, "completed"))

    reopen = subs.add_parser("reopen", help="Reopen an entry")
    reopen.add_argument("id")
    reopen.set_defaults(func=lambda args: _cmd_status(ctx, args, "open"))

    show = subs.add_parser("show", help="Show one entry")
    show.add_argument("id")
    show.set_defaults(func=lambda args: _cmd_show(ctx, args))

    delete = subs.add_parser("delete", help="Permanently delete one entry")
    delete.add_argument("id")
    delete.set_defaults(func=lambda args: _cmd_delete(ctx, args))

    cron = subs.add_parser("cron-install", help="Install daily and weekly digest jobs")
    cron.add_argument("--deliver", required=True, help="Hermes delivery target, e.g. telegram")
    cron.add_argument("--daily-schedule", default="0 7 * * *")
    cron.add_argument("--weekly-schedule", default="0 18 * * 0")
    cron.set_defaults(func=lambda args: _cmd_cron_install(ctx, args))


def cli_default(_args) -> int:
    print("Usage: hermes family-tasks <kids|agenda|ingest|show|complete|reopen|delete|cron-install>")
    return 1


def _cmd_kids(_ctx, _args) -> int:
    for kid in service.list_kids():
        print(kid["name"])
    return 0


def _cmd_agenda(ctx, args) -> int:
    timezone_name, _ = _settings(ctx)
    entries = service.query_entries(
        timezone_name=timezone_name,
        kid=args.kid,
        date_from=args.date_from,
        date_to=args.date_to,
        kinds=args.kinds,
        status=args.status,
        include_undated=args.include_undated,
    )
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        print(service.format_agenda(entries))
    return 0


def _cmd_ingest(ctx, args) -> int:
    timezone_name, date_order = _settings(ctx)
    image_path = None
    content = args.text or args.caption or ""
    source_type = args.source_type
    if args.file:
        path = Path(args.file).expanduser().resolve()
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
            image_path = str(path)
            source_type = source_type or "image"
        else:
            content = path.read_text(encoding="utf-8")
            source_type = source_type or "text"
    extracted = extraction.extract(
        ctx,
        content=content,
        kids=args.kids,
        timezone_name=timezone_name,
        date_order=date_order,
        received_at=args.received_at,
        image_path=image_path,
    )
    result = service.save_extraction(
        source_type=source_type or "text",
        content=(
            str(extracted.get("source_text") or "").strip()
            if (source_type or "text") == "image"
            else content
        ),
        extracted=extracted,
        explicit_kids=args.kids,
        timezone_name=timezone_name,
        platform=args.platform,
        external_message_id=args.message_id,
        sender=args.sender,
        received_at=args.received_at,
    )
    print(result["message"])
    print(service.format_agenda(result["created"]))
    return 0


def _cmd_status(ctx, args, status: str) -> int:
    timezone_name, _ = _settings(ctx)
    entry = service.set_status(args.id, status, timezone_name=timezone_name)
    print(service.format_agenda([entry]))
    return 0


def _cmd_show(ctx, args) -> int:
    timezone_name, _ = _settings(ctx)
    print(json.dumps(service.get_entry(args.id, timezone_name=timezone_name), ensure_ascii=False, indent=2))
    return 0


def _cmd_delete(_ctx, args) -> int:
    print(json.dumps(service.delete_entry(args.id)))
    return 0


def _write_cron_script(name: str, *, date_from: str, date_to: str) -> str:
    from hermes_constants import get_hermes_home

    hermes = shutil.which("hermes")
    if not hermes:
        raise RuntimeError("Could not find the hermes executable on PATH")
    scripts = get_hermes_home() / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    path = scripts / name
    body = f"""
        import subprocess

        result = subprocess.run(
            [{hermes!r}, "family-tasks", "agenda", "--from", {date_from!r}, "--to", {date_to!r}],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise SystemExit(result.stderr.strip() or "family-tasks agenda failed")
        output = result.stdout.strip()
        if output:
            print(output)
    """
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path.name


def _cmd_cron_install(_ctx, args) -> int:
    from cron.jobs import list_jobs
    from cron.scheduler import create_job_with_scheduler_registration

    specs = [
        (
            "Family tasks - daily",
            args.daily_schedule,
            _write_cron_script(
                "family_tasks_daily.py", date_from="today", date_to="today"
            ),
        ),
        (
            "Family tasks - weekly",
            args.weekly_schedule,
            _write_cron_script(
                "family_tasks_weekly.py", date_from="today", date_to="week"
            ),
        ),
    ]
    existing = {job.get("name"): job for job in list_jobs(include_disabled=True)}
    for name, schedule, script in specs:
        if name in existing:
            print(f"Already installed: {name} ({existing[name]['id']})")
            continue
        job = create_job_with_scheduler_registration(
            prompt="",
            schedule=schedule,
            name=name,
            deliver=args.deliver,
            script=script,
            no_agent=True,
        )
        print(f"Installed: {name} ({job['id']}) — {job['schedule_display']}")
    return 0


def slash_handler(ctx, raw_args: str) -> str:
    timezone_name, _ = _settings(ctx)
    tokens = raw_args.strip().split()
    if not tokens or tokens[0].lower() in {"today", "week", "tomorrow", "open"}:
        period = tokens[0].lower() if tokens else "today"
        kid = tokens[1] if len(tokens) > 1 else None
        if period == "week":
            date_from, date_to, include_undated = "today", "week", False
        elif period == "tomorrow":
            date_from = date_to = "tomorrow"
            include_undated = False
        elif period == "open":
            date_from = date_to = None
            include_undated = True
        else:
            date_from = date_to = "today"
            include_undated = False
        entries = service.query_entries(
            timezone_name=timezone_name,
            kid=kid,
            date_from=date_from,
            date_to=date_to,
            include_undated=include_undated,
        )
        return service.format_agenda(entries) or "No matching family tasks."
    if tokens[0].lower() == "complete" and len(tokens) == 2:
        entry = service.set_status(tokens[1], "completed", timezone_name=timezone_name)
        return "Completed:\n" + service.format_agenda([entry])
    if tokens[0].lower() == "reopen" and len(tokens) == 2:
        entry = service.set_status(tokens[1], "open", timezone_name=timezone_name)
        return "Reopened:\n" + service.format_agenda([entry])
    return "Usage: /kids [today|tomorrow|week|open] [kid] | complete <id> | reopen <id>"
