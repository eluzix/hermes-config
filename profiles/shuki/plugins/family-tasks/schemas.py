"""Schemas shown to the Hermes model."""

INGEST_SCHEMA = {
    "name": "family_tasks_ingest",
    "description": (
        "Save tasks, events, things to bring, or facts to remember for Itamar, Alona, "
        "Shahar, or Yuval from a forwarded message, email, pasted text, or image. For "
        "an image attached to the current gateway message, inspect it and pass a faithful "
        "transcription/description in content; do not pass ephemeral image data. The plugin "
        "extracts and saves all distinct entries automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Full original text, or faithful visible-text transcription of an attached image.",
            },
            "kids": {
                "type": "array",
                "items": {"type": "string", "enum": ["Itamar", "Alona", "Shahar", "Yuval"]},
                "description": "Children explicitly associated by the user.",
            },
            "source_type": {
                "type": "string",
                "enum": ["text", "image", "email", "whatsapp", "telegram", "manual"],
                "default": "text",
            },
            "platform": {"type": "string"},
            "external_message_id": {"type": "string"},
            "sender": {"type": "string"},
            "received_at": {
                "type": "string",
                "description": "Optional ISO 8601 receipt timestamp; relative dates are anchored to it.",
            },
            "image_path": {
                "type": "string",
                "description": "Optional durable local image path for manual ingestion. Do not invent a path.",
            },
        },
        "required": ["content", "kids"],
    },
}

MANAGE_SCHEMA = {
    "name": "family_tasks",
    "description": (
        "Query or manage saved family tasks. Use for daily/weekly agendas, one or all "
        "children, things to bring, events, completion, correction, reopening, or deletion."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["agenda", "list", "show", "complete", "reopen", "edit", "delete", "kids"],
            },
            "id": {"type": "string", "description": "Full entry ID or unique prefix."},
            "kid": {"type": "string", "enum": ["Itamar", "Alona", "Shahar", "Yuval"]},
            "date_from": {"type": "string", "description": "ISO date/time, today, or tomorrow."},
            "date_to": {"type": "string", "description": "ISO date/time, today, tomorrow, or week."},
            "kinds": {
                "type": "array",
                "items": {"type": "string", "enum": ["do", "bring", "remember", "event"]},
            },
            "status": {"type": "string", "enum": ["open", "completed", "cancelled", "all"]},
            "include_undated": {"type": "boolean"},
            "search": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            "changes": {
                "type": "object",
                "description": "For edit: any of title, details, kind, starts_at, ends_at, due_at, all_day, location, kids.",
            },
        },
        "required": ["action"],
    },
}
