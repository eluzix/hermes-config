"""Structured LLM extraction for text and image notices."""

from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from .service import timezone_for

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "source_text": {
            "type": "string",
            "description": "Full text of the source; transcribe all relevant visible text from images.",
        },
        "kids": {"type": "array", "items": {"type": "string"}},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["do", "bring", "remember", "event"]},
                    "title": {"type": "string"},
                    "details": {"type": ["string", "null"]},
                    "starts_at": {"type": ["string", "null"]},
                    "ends_at": {"type": ["string", "null"]},
                    "due_at": {"type": ["string", "null"]},
                    "all_day": {"type": "boolean"},
                    "location": {"type": ["string", "null"]},
                    "kids": {"type": "array", "items": {"type": "string"}},
                    "original_date_text": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "kind", "title", "details", "starts_at", "ends_at", "due_at",
                    "all_day", "location", "kids", "original_date_text", "confidence",
                ],
            },
        },
    },
    "required": ["source_text", "kids", "needs_clarification", "clarification_question", "entries"],
}


def extract(
    ctx,
    *,
    content: str,
    kids: Sequence[str],
    timezone_name: str,
    date_order: str,
    received_at: str | None,
    image_path: str | None = None,
) -> dict[str, Any]:
    tz = timezone_for(timezone_name)
    reference = (
        datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received_at
        else datetime.now(tz)
    )
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=tz)
    reference = reference.astimezone(tz)
    explicit = ", ".join(kids) if kids else "none"
    instructions = f"""
Extract family obligations from a message or image into structured entries.
Known children: Itamar, Alona, Shahar, Yuval. Explicitly selected children: {explicit}.
Reference local datetime: {reference.isoformat(timespec='minutes')}.
Timezone: {timezone_name}. Numeric date order: {date_order}.

Rules:
- Put the complete original text in source_text. For images, transcribe all relevant visible text;
  do not merely summarize it. For supplied text, copy it faithfully.
- Preserve the source language in titles and details.
- Make one entry per independently useful fact.
- kind=do for an action the parent must perform; bring for an item a child must bring;
  remember for important non-action information; event for an appointment or activity.
- An event plus a related form/item normally creates separate entries.
- Explicitly selected children are authoritative unless the source clearly assigns an entry differently.
- Resolve relative dates from the reference datetime. Return ISO 8601 values with UTC offset.
- For a date with no time, return YYYY-MM-DD and set all_day=true.
- Never invent a child, date, time, location, deadline, or action.
- Missing dates are allowed and must be null.
- Ask for clarification only when no known child can be associated or the source is internally
  contradictory. Use needs_clarification and one concise clarification_question.
- If there is nothing useful to do, bring, remember, or attend, return an empty entries list.
""".strip()
    inputs: list[dict[str, Any]] = []
    if content.strip():
        inputs.append({"type": "text", "text": content.strip()})
    if image_path:
        path = Path(image_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Image file does not exist: {path}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if not mime.startswith("image/"):
            raise ValueError(f"File is not a supported image: {path}")
        inputs.append({"type": "image", "data": path.read_bytes(), "mime_type": mime})
    if not inputs:
        raise ValueError("Provide message text or an image file")
    result = ctx.llm.complete_structured(
        instructions=instructions,
        input=inputs,
        json_schema=EXTRACTION_SCHEMA,
        schema_name="family_tasks.extraction",
        purpose="family-tasks.ingest",
        task="family_tasks_extraction",
        temperature=0.0,
        max_tokens=1800,
    )
    if result.parsed is None:
        raise ValueError(f"Could not parse the extraction result: {result.text[:500]}")
    if not isinstance(result.parsed, dict):
        raise ValueError("Extraction result was not an object")
    return result.parsed
