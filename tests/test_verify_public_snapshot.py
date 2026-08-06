from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_public_snapshot import verify_snapshot, write_report


class VerifyPublicSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.events = [{"title": "A"}, {"title": "B"}]
        self.health = {
            "schema_version": "1.0",
            "generated_at": "2026-08-07T00:00:00Z",
            "status": "ok",
            "enabled_sources": 2,
            "successful_sources": 2,
            "failed_sources": 0,
            "event_count": 2,
            "sources": [
                {"name": "manual", "status": "ok", "count": 1, "duration_ms": 0},
                {"name": "external", "status": "ok", "count": 1, "duration_ms": 3},
            ],
            "ontology": {
                "matched_events": 1,
                "unmatched_events": 1,
            },
            "category_classification": {
                "event_count": 2,
                "category_breakdown": {"community": 1, "music": 1},
                "event_mode_breakdown": {"in_world": 2},
                "classification_source_breakdown": {"curated": 1, "fallback": 1},
            },
        }
        self._write_snapshot()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_json(self, name: str, payload: object) -> None:
        (self.root / name).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def _write_snapshot(self) -> None:
        self._write_json("events.json", self.events)
        self._write_json("health.json", self.health)
        self._write_json("event-ontology.json", {"source_event_count": 2})
        self._write_json(
            "ontology-match-audit.json",
            {
                "event_count": 2,
                "ontology_entries": 1,
                "matched_events": 1,
                "ambiguous_events": 0,
            },
        )

    def test_valid_snapshot_records_all_input_hashes(self) -> None:
        metrics = verify_snapshot(self.root)
        self.assertEqual(metrics["events_count"], 2)
        self.assertEqual(
            set(metrics["files"]),
            {
                "events.json",
                "health.json",
                "event-ontology.json",
                "ontology-match-audit.json",
            },
        )
        self.assertTrue(all(len(value) == 64 for value in metrics["files"].values()))

    def test_failed_source_rejects_snapshot(self) -> None:
        self.health["successful_sources"] = 1
        self.health["failed_sources"] = 1
        self.health["sources"][1]["status"] = "failed"
        self._write_json("health.json", self.health)
        with self.assertRaisesRegex(ValueError, "failed source"):
            verify_snapshot(self.root)

    def test_breakdown_count_mismatch_rejects_snapshot(self) -> None:
        self.health["category_classification"]["category_breakdown"] = {
            "community": 1
        }
        self._write_json("health.json", self.health)
        with self.assertRaisesRegex(ValueError, "category_breakdown total mismatch"):
            verify_snapshot(self.root)

    def test_non_object_event_rejects_snapshot(self) -> None:
        self._write_json("events.json", [{"title": "A"}, "broken"])
        with self.assertRaisesRegex(ValueError, "non-object events"):
            verify_snapshot(self.root)

    def test_report_is_replaced_atomically(self) -> None:
        report = self.root / "build" / "snapshot-audit.json"
        write_report(report, {"ok": True})
        self.assertEqual(json.loads(report.read_text(encoding="utf-8")), {"ok": True})
        self.assertFalse((report.parent / ".snapshot-audit.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
