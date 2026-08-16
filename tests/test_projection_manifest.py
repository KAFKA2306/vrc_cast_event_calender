from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_projection_manifest import SEARCH_BASE_URL, verify
from scripts.write_projection_manifest import build_manifest


class ProjectionManifestTest(unittest.TestCase):
    def write_fixture(self, root: Path) -> None:
        (root / "events.json").write_text(
            json.dumps({"generated_at": "2026-08-10T00:00:00Z", "count": 1, "events": [{"id": "event-1"}]}) + "\n",
            encoding="utf-8",
        )
        (root / "health.json").write_text(
            json.dumps({"status": "ok", "event_count": 1, "enabled_sources": 2, "successful_sources": 2, "failed_sources": 0}) + "\n",
            encoding="utf-8",
        )
        (root / "event-ontology.json").write_text(
            json.dumps({"schema_version": "3.0", "source_event_count": 1}) + "\n",
            encoding="utf-8",
        )
        (root / "calendar.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n", encoding="utf-8")
        nested = root / "audit"
        nested.mkdir()
        (nested / "proof.json").write_text('{"status":"ok"}\n', encoding="utf-8")

    def write_search_surface(self, root: Path) -> None:
        (root / "analytics.js").write_text("// analytics\n", encoding="utf-8")
        (root / "analytics-config.json").write_text('{"ga4_measurement_id":null}\n', encoding="utf-8")
        pages = {
            "events/event-1/index.html": "events/event-1/",
            "categories/music/index.html": "categories/music/",
            "series/sample/index.html": "series/sample/",
        }
        for name, url in pages.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                f'<!doctype html><link rel="canonical" href="{SEARCH_BASE_URL}{url}">\n',
                encoding="utf-8",
            )
        urls = [SEARCH_BASE_URL, *(SEARCH_BASE_URL + url for url in pages.values())]
        body = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
        (root / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{body}</urlset>",
            encoding="utf-8",
        )

    def test_manifest_tracks_every_canonical_file_and_required_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            timestamp = "2026-08-10T00:01:00Z"
            manifest = build_manifest(root, "a" * 40, timestamp=timestamp)

            self.assertEqual(manifest["schema_version"], "cast-event.projection-manifest.v2")
            self.assertEqual(manifest["source_repository"], "KAFKA2306/cast_event_cal")
            self.assertEqual(manifest["source_commit_sha"], "a" * 40)
            self.assertEqual(manifest["received_at"], timestamp)
            self.assertEqual(manifest["deployed_at"], timestamp)
            self.assertEqual(manifest["validation_status"], "validated")
            self.assertEqual(manifest["ontology_version"], "3.0")
            self.assertEqual(manifest["collection_counts"]["event_count"], 1)
            self.assertEqual(set(manifest["assets"]), {
                "audit/proof.json", "calendar.ics", "event-ontology.json", "events.json", "health.json"
            })
            for name, metadata in manifest["assets"].items():
                raw = (root / name).read_bytes()
                self.assertEqual(metadata["bytes"], len(raw))
                self.assertEqual(metadata["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertRegex(manifest["source_snapshot_sha256"], r"^[0-9a-f]{64}$")
            self.assertFalse(manifest["data_contract"]["classification_logic_in_this_repo"])
            self.assertFalse(manifest["data_contract"]["independent_collection_in_this_repo"])

            manifest_path = root.parent / "projection-manifest-test.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = verify(root, manifest_path)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["asset_count"], 5)

    def test_search_surface_accepts_event_category_and_series_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            self.write_search_surface(root)
            manifest = build_manifest(root, "d" * 40, timestamp="2026-08-10T00:01:00Z")
            manifest_path = root.parent / "projection-manifest-search.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = verify(root, manifest_path)

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["event_count"], 1)

    def test_search_surface_rejects_sitemap_page_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            self.write_search_surface(root)
            sitemap = root / "sitemap.xml"
            sitemap.write_text(
                sitemap.read_text(encoding="utf-8").replace(
                    f"<url><loc>{SEARCH_BASE_URL}categories/music/</loc></url>", ""
                ),
                encoding="utf-8",
            )
            manifest = build_manifest(root, "e" * 40, timestamp="2026-08-10T00:01:00Z")
            manifest_path = root.parent / "projection-manifest-search-drift.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "sitemap/search-page parity mismatch"):
                verify(root, manifest_path)

    def test_tampered_asset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            manifest = build_manifest(root, "c" * 40, timestamp="2026-08-10T00:01:00Z")
            manifest_path = root.parent / "projection-manifest-tamper.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "calendar.ics").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                verify(root, manifest_path)

    def test_failed_canonical_health_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            health = json.loads((root / "health.json").read_text(encoding="utf-8"))
            health["failed_sources"] = 1
            (root / "health.json").write_text(json.dumps(health) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "zero failed sources"):
                build_manifest(root, "b" * 40, timestamp="2026-08-10T00:01:00Z")


if __name__ == "__main__":
    unittest.main()
