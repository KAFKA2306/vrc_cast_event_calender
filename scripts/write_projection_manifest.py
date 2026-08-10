#!/usr/bin/env python3
"""Create a provenance manifest for the deployed cast_event_cal snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

TRACKED = (
    "events.json",
    "health.json",
    "calendar.ics",
    "event-ontology.json",
    "category-ontology.json",
    "ontology-match-audit.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(canonical_root: Path, source_commit: str) -> dict:
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit.lower()):
        raise ValueError("source_commit must be a 40-character git SHA")

    events = json.loads((canonical_root / "events.json").read_text(encoding="utf-8"))
    rows = events.get("events", []) if isinstance(events, dict) else events
    if not isinstance(rows, list):
        raise ValueError("events.json has no event list")

    assets = {}
    for name in TRACKED:
        path = canonical_root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        assets[name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }

    return {
        "schema_version": "cast-event.projection-manifest.v1",
        "role": "projection_only",
        "source_repository": "KAFKA2306/cast_event_cal",
        "source_commit_sha": source_commit,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_snapshot_generated_at": events.get("generated_at") if isinstance(events, dict) else None,
        "event_count": len(rows),
        "assets": assets,
        "data_contract": {
            "canonical_ingestion": "KAFKA2306/cast_event_cal",
            "classification_logic_in_this_repo": False,
            "edinetdb_mode": "not_applicable",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-root", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = build_manifest(Path(args.canonical_root), args.source_commit)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
