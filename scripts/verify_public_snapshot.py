#!/usr/bin/env python3
"""Verify that the deploy repository contains one coherent public snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> tuple[bytes, Any]:
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f"{path.name} is empty")
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} is not valid JSON: {exc}") from exc


def extract_events(payload: Any) -> tuple[list[dict[str, Any]], str, list[str]]:
    if isinstance(payload, list):
        events = payload
        shape = "array"
        keys: list[str] = []
    elif isinstance(payload, dict):
        keys = sorted(str(key) for key in payload)
        for key in ("events", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                events = value
                shape = f"object.{key}"
                break
        else:
            raise ValueError(
                "events.json is an object but has no supported event array; "
                f"top-level keys={keys}"
            )
    else:
        raise ValueError(
            "events.json must contain an array or object wrapper, "
            f"got {type(payload).__name__}"
        )

    invalid_indexes = [index for index, event in enumerate(events) if not isinstance(event, dict)]
    if invalid_indexes:
        preview = ", ".join(str(index) for index in invalid_indexes[:10])
        raise ValueError(f"events.json contains non-object events at indexes: {preview}")
    return events, shape, keys


def require_non_negative_int(mapping: dict[str, Any], key: str, label: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}:{key} must be a non-negative integer, got {value!r}")
    return value


def require_utc_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} must be an ISO 8601 UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid ISO 8601 timestamp: {value!r}") from exc
    return value


def verify_health(health: Any, event_count: int) -> dict[str, Any]:
    if not isinstance(health, dict):
        raise ValueError("health.json must contain an object")
    if health.get("status") != "ok":
        raise ValueError(f"health.json:status must be 'ok', got {health.get('status')!r}")

    enabled = require_non_negative_int(health, "enabled_sources", "health.json")
    successful = require_non_negative_int(health, "successful_sources", "health.json")
    failed = require_non_negative_int(health, "failed_sources", "health.json")
    if successful + failed != enabled:
        raise ValueError(
            "health source accounting mismatch: "
            f"successful_sources({successful}) + failed_sources({failed}) "
            f"!= enabled_sources({enabled})"
        )
    if failed:
        raise ValueError(f"health.json reports {failed} failed source(s)")

    health_event_count = require_non_negative_int(health, "event_count", "health.json")
    if health_event_count != event_count:
        raise ValueError(
            f"health event count mismatch: events.json={event_count}, health.json={health_event_count}"
        )

    sources = health.get("sources")
    if not isinstance(sources, list) or len(sources) != enabled:
        raise ValueError(
            "health.json:sources must be a list whose length equals enabled_sources"
        )
    source_names: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise ValueError(f"health.json:sources[{index}] must be an object")
        name = source.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"health.json:sources[{index}].name must be non-empty")
        if name in source_names:
            raise ValueError(f"health.json contains duplicate source name: {name}")
        source_names.add(name)
        if source.get("status") != "ok":
            raise ValueError(f"health source {name!r} is not ok")
        require_non_negative_int(source, "count", f"health.json:sources[{index}]")
        require_non_negative_int(source, "duration_ms", f"health.json:sources[{index}]")

    classification = health.get("category_classification")
    if not isinstance(classification, dict):
        raise ValueError("health.json:category_classification must be an object")
    classification_count = require_non_negative_int(
        classification, "event_count", "health.json:category_classification"
    )
    if classification_count != event_count:
        raise ValueError(
            "category classification event count mismatch: "
            f"events.json={event_count}, classification={classification_count}"
        )
    for field in (
        "category_breakdown",
        "event_mode_breakdown",
        "classification_source_breakdown",
    ):
        breakdown = classification.get(field)
        if not isinstance(breakdown, dict):
            raise ValueError(f"health.json:category_classification.{field} must be an object")
        total = 0
        for key in sorted(breakdown):
            total += require_non_negative_int(
                breakdown, key, f"health.json:category_classification.{field}"
            )
        if total != event_count:
            raise ValueError(
                f"{field} total mismatch: expected {event_count}, got {total}"
            )

    ontology = health.get("ontology")
    if not isinstance(ontology, dict):
        raise ValueError("health.json:ontology must be an object")
    matched = require_non_negative_int(ontology, "matched_events", "health.json:ontology")
    unmatched = require_non_negative_int(ontology, "unmatched_events", "health.json:ontology")
    if matched + unmatched != event_count:
        raise ValueError(
            "ontology coverage mismatch: "
            f"matched_events({matched}) + unmatched_events({unmatched}) != {event_count}"
        )

    return {
        "generated_at": require_utc_timestamp(
            health.get("generated_at"), "health.json:generated_at"
        ),
        "enabled_sources": enabled,
        "successful_sources": successful,
        "failed_sources": failed,
    }


def verify_snapshot(root: Path) -> dict[str, Any]:
    events_raw, events_payload = load_json(root / "events.json")
    health_raw, health = load_json(root / "health.json")
    ontology_raw, event_ontology = load_json(root / "event-ontology.json")
    audit_raw, ontology_audit = load_json(root / "ontology-match-audit.json")

    if not isinstance(event_ontology, dict):
        raise ValueError("event-ontology.json must contain an object")
    if not isinstance(ontology_audit, dict):
        raise ValueError("ontology-match-audit.json must contain an object")

    events, payload_shape, payload_keys = extract_events(events_payload)
    event_count = len(events)
    health_metrics = verify_health(health, event_count)

    expected = {
        "event-ontology.json:source_event_count": event_ontology.get("source_event_count"),
        "ontology-match-audit.json:event_count": ontology_audit.get("event_count"),
    }
    mismatches = {
        label: value
        for label, value in expected.items()
        if value is not None and value != event_count
    }
    if mismatches:
        formatted = ", ".join(f"{label}={value}" for label, value in mismatches.items())
        raise ValueError(f"snapshot event count mismatch: events.json={event_count}, {formatted}")

    return {
        "audit_schema_version": "1.0",
        "events_bytes": len(events_raw),
        "events_count": event_count,
        "events_payload_shape": payload_shape,
        "events_payload_keys": payload_keys,
        "files": {
            "events.json": hashlib.sha256(events_raw).hexdigest(),
            "health.json": hashlib.sha256(health_raw).hexdigest(),
            "event-ontology.json": hashlib.sha256(ontology_raw).hexdigest(),
            "ontology-match-audit.json": hashlib.sha256(audit_raw).hexdigest(),
        },
        "health": health_metrics,
        "ontology_entries": ontology_audit.get("ontology_entries"),
        "matched_events": ontology_audit.get("matched_events"),
        "ambiguous_events": ontology_audit.get("ambiguous_events"),
    }


def write_report(path: Path, metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        metrics = verify_snapshot(args.root)
        if args.report:
            write_report(args.report, metrics)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
