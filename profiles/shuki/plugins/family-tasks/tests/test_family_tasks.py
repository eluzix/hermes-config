from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def load_package():
    name = "family_tasks_test_plugin"
    spec = importlib.util.spec_from_file_location(
        name,
        PLUGIN_DIR / "__init__.py",
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PACKAGE = load_package()


def extracted(*, title="Return permission form", due="2026-08-21", kids=None):
    return {
        "source_text": "Source text",
        "kids": kids or ["Itamar"],
        "needs_clarification": False,
        "clarification_question": None,
        "entries": [
            {
                "kind": "do",
                "title": title,
                "details": None,
                "starts_at": None,
                "ends_at": None,
                "due_at": due,
                "all_day": True,
                "location": "School",
                "kids": kids or ["Itamar"],
                "original_date_text": "Friday",
                "confidence": 0.95,
            }
        ],
    }


class FamilyTasksTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ, {"HERMES_HOME": str(Path(self.tempdir.name) / ".hermes")}
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tempdir.cleanup()

    def test_database_seeds_children(self):
        self.assertEqual(
            {kid["name"] for kid in PACKAGE.service.list_kids()},
            {"Itamar", "Alona", "Shahar", "Yuval"},
        )

    def test_save_query_complete_and_deduplicate(self):
        kwargs = dict(
            source_type="text",
            content="Return Itamar's permission form Friday",
            extracted=extracted(),
            explicit_kids=["Itamar"],
            timezone_name="America/New_York",
            received_at="2026-08-19T10:00:00-04:00",
        )
        first = PACKAGE.service.save_extraction(**kwargs)
        second = PACKAGE.service.save_extraction(**kwargs)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(first["created"]), 1)

        rows = PACKAGE.service.query_entries(
            timezone_name="America/New_York",
            kid="itamar",
            date_from="2026-08-21",
            date_to="2026-08-21",
        )
        self.assertEqual(
            [row["title"] for row in rows], ["Return permission form"]
        )
        completed = PACKAGE.service.set_status(
            rows[0]["id"][:8], "completed", timezone_name="America/New_York"
        )
        self.assertEqual(completed["status"], "completed")

    def test_image_source_keeps_extracted_text_only(self):
        result = PACKAGE.service.save_extraction(
            source_type="image",
            content="Visible notice text",
            extracted=extracted(title="Bring sneakers", kids=["Yuval"]),
            explicit_kids=["Yuval"],
            timezone_name="America/New_York",
        )
        conn = PACKAGE.db.connect()
        try:
            row = conn.execute(
                "SELECT raw_text, extracted_text FROM sources WHERE id=?",
                (result["created"][0]["source_id"],),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row["raw_text"])
        self.assertEqual(row["extracted_text"], "Visible notice text")

    def test_unknown_child_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown kid"):
            PACKAGE.service.save_extraction(
                source_type="text",
                content="Notice",
                extracted=extracted(kids=["Someone"]),
                explicit_kids=["Someone"],
                timezone_name="America/New_York",
            )

    def test_dst_conversion_uses_eastern(self):
        result = PACKAGE.service.save_extraction(
            source_type="text",
            content="Alona event",
            extracted=extracted(
                title="Practice",
                due="2026-11-02T17:00:00-05:00",
                kids=["Alona"],
            ),
            explicit_kids=["Alona"],
            timezone_name="America/New_York",
        )
        self.assertTrue(
            result["created"][0]["due_at"].startswith("2026-11-02T17:00-05:00")
        )

    def test_structured_extraction_uses_registered_auxiliary_task(self):
        expected = extracted()

        class Result:
            parsed = expected
            text = ""

        class Llm:
            def __init__(self):
                self.kwargs = None

            def complete_structured(self, **kwargs):
                self.kwargs = kwargs
                return Result()

        class Context:
            llm = Llm()

        ctx = Context()
        actual = PACKAGE.extraction.extract(
            ctx,
            content="Return the form Friday",
            kids=["Itamar"],
            timezone_name="America/New_York",
            date_order="MDY",
            received_at="2026-08-19T10:00:00-04:00",
        )
        self.assertEqual(actual, expected)
        self.assertEqual(ctx.llm.kwargs["task"], "family_tasks_extraction")
        self.assertEqual(
            ctx.llm.kwargs["input"],
            [{"type": "text", "text": "Return the form Friday"}],
        )


if __name__ == "__main__":
    unittest.main()
