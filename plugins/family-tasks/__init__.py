"""Family task manager for Hermes."""

from __future__ import annotations

import json

from . import cli, extraction, schemas, service


def _settings(ctx) -> tuple[str, str]:
    return (
        str(ctx.get_config("timezone", "America/New_York")),
        str(ctx.get_config("date_order", "MDY")).upper(),
    )


def _json_result(fn) -> str:
    try:
        return json.dumps({"success": True, **fn()}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def _ingest(ctx, args: dict, **_kwargs) -> str:
    def run():
        timezone_name, date_order = _settings(ctx)
        content = str(args.get("content") or "").strip()
        kids = [str(kid) for kid in args.get("kids") or []]
        extracted = extraction.extract(
            ctx,
            content=content,
            kids=kids,
            timezone_name=timezone_name,
            date_order=date_order,
            received_at=args.get("received_at"),
            image_path=args.get("image_path"),
        )
        stored_content = (
            str(extracted.get("source_text") or "").strip()
            if str(args.get("source_type") or "text") == "image"
            else content
        )
        result = service.save_extraction(
            source_type=str(args.get("source_type") or "text"),
            content=stored_content,
            extracted=extracted,
            explicit_kids=kids,
            timezone_name=timezone_name,
            platform=args.get("platform"),
            external_message_id=args.get("external_message_id"),
            sender=args.get("sender"),
            received_at=args.get("received_at"),
        )
        result["summary"] = service.format_agenda(result["created"])
        return result

    return _json_result(run)


def _manage(ctx, args: dict, **_kwargs) -> str:
    def run():
        timezone_name, _ = _settings(ctx)
        action = str(args.get("action") or "").lower()
        reference = str(args.get("id") or "")
        if action == "kids":
            return {"kids": service.list_kids()}
        if action in {"agenda", "list"}:
            entries = service.query_entries(
                timezone_name=timezone_name,
                kid=args.get("kid"),
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
                kinds=args.get("kinds"),
                status=str(args.get("status") or "open"),
                include_undated=bool(args.get("include_undated", False)),
                search=args.get("search"),
                limit=int(args.get("limit") or 100),
            )
            return {"entries": entries, "summary": service.format_agenda(entries)}
        if action == "show":
            return {"entry": service.get_entry(reference, timezone_name=timezone_name)}
        if action == "complete":
            return {"entry": service.set_status(reference, "completed", timezone_name=timezone_name)}
        if action == "reopen":
            return {"entry": service.set_status(reference, "open", timezone_name=timezone_name)}
        if action == "delete":
            return service.delete_entry(reference)
        if action == "edit":
            return {
                "entry": service.edit_entry(
                    reference,
                    args.get("changes") if isinstance(args.get("changes"), dict) else {},
                    timezone_name=timezone_name,
                )
            }
        raise ValueError(f"Unsupported action: {action}")

    return _json_result(run)


def register(ctx) -> None:
    # Initialize and seed the database while registration is still easy to diagnose.
    service.list_kids()
    ctx.register_auxiliary_task(
        "family_tasks_extraction",
        display_name="Family task extraction",
        description="Extract child tasks and dates from text or images.",
        defaults={"provider": "auto", "timeout": 60},
    )
    ctx.register_tool(
        name="family_tasks_ingest",
        toolset="family_tasks",
        schema=schemas.INGEST_SCHEMA,
        handler=lambda args, **kwargs: _ingest(ctx, args, **kwargs),
        emoji="👨‍👩‍👧‍👦",
    )
    ctx.register_tool(
        name="family_tasks",
        toolset="family_tasks",
        schema=schemas.MANAGE_SCHEMA,
        handler=lambda args, **kwargs: _manage(ctx, args, **kwargs),
        emoji="📋",
    )
    ctx.register_command(
        "kids",
        handler=lambda raw: cli.slash_handler(ctx, raw),
        description="Show or update family tasks.",
        args_hint="[today|tomorrow|week|open] [kid]",
    )
    ctx.register_cli_command(
        name="family-tasks",
        help="Manage tasks and events for your children",
        setup_fn=lambda parser: cli.setup_parser(parser, ctx),
        handler_fn=cli.cli_default,
        description="Ingest notices and query family agendas.",
    )
