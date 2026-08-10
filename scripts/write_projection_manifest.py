#!/usr/bin/env python3
"""Create the provenance contract for one canonical public snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "cast-event.projection-manifest.v2"
SOURCE_REPOSITORY = "KAFKA2306/cast_event_cal"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain an object")
    return payload


def canonical_assets(canonical_root: Path) -> dict[str, dict[str, Any]]:
    assets: dict[str, dict[str, Any]] = {}
    for path in sorted(p for p in canonical_root.rglob("*") if p.is_file()):
        relative = path.relative_to(canonical_root).as_posix()
        assets[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    if not assets:
        raise ValueError("canonical snapshot contains no files")
    return assets


def snapshot_digest(assets: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for name, metadata in sorted(assets.items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(metadata["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(metadata["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(canonical_root: Path, source_commit: str, timestamp: str | None = None) -> dict[str, Any]:
    if len(source_commit) != 40 or any(ch not in "0123456789abcdef" for ch in source_commit.lower()):
        raise ValueError("source_commit must be a 40-character git SHA")

    events = read_json(canonical_root / "events.json")
    health = read_json(canonical_root / "health.json")
    ontology = read_json(canonical_root / "event-ontology.json")
    rows = events.get("events", [])
    if not isinstance(rows, list):
        raise ValueError("events.json has no event list")
    if events.get("count") != len(rows):
        raise ValueError("events.json count does not match event list")
    if health.get("status") != "ok" or health.get("failed_sources") != 0:
        raise ValueError("canonical health must be ok with zero failed sources")
    if health.get("event_count") != len(rows):
        raise ValueError("health event count does not match events.json")

    assets = canonical_assets(canonical_root)
    created = timestamp or utc_now()
    collection_counts = {
        "event_count": len(rows),
        "enabled_sources": health.get("enabled_sources"),
        "successful_sources": health.get("successful_sources"),
        "failed_sources": health.get("failed_sources"),
    }
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in collection_counts.values()):
        raise ValueError("collection counts must be non-negative integers")

    return {
        "schema_version": SCHEMA_VERSION,
        "role": "projection_only",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit_sha": source_commit.lower(),
        "source_snapshot_sha256": snapshot_digest(assets),
        "source_snapshot_generated_at": events.get("generated_at"),
        "generated_at": created,
        "received_at": created,
        "deployed_at": created,
        "collection_counts": collection_counts,
        "event_count": len(rows),
        "ontology_version": ontology.get("schema_version"),
        "validation_status": "validated",
        "assets": assets,
        "data_contract": {
            "canonical_ingestion": SOURCE_REPOSITORY,
            "classification_logic_in_this_repo": False,
            "independent_collection_in_this_repo": False,
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
