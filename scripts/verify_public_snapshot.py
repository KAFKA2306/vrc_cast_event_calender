#!/usr/bin/env python3
"""Verify that the deploy repository contains one coherent public snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> tuple[bytes, Any]:
    raw = path.read_bytes()
    if not raw:
        raise SystemExit(f"{path.name} is empty")
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.name} is not valid JSON: {exc}") from exc


def extract_events(payload: Any) -> tuple[list[dict[str, Any]], str, list[str]]:
    if isinstance(payload, list):
        return payload, "array", []
    if isinstance(payload, dict):
        keys = sorted(str(key) for key in payload)
        for key in ("events", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value, f"object.{key}", keys
        raise SystemExit(
            "events.json is an object but has no supported event array; "
            f"top-level keys={keys}"
        )
    raise SystemExit(
        f"events.json must contain an array or object wrapper, got {type(payload).__name__}"
    )


def main() -> None:
    events_raw, events_payload = load_json(ROOT / "events.json")
    _, health = load_json(ROOT / "health.json")
    _, event_ontology = load_json(ROOT / "event-ontology.json")
    _, ontology_audit = load_json(ROOT / "ontology-match-audit.json")

    events, payload_shape, payload_keys = extract_events(events_payload)
    event_count = len(events)
    expected = {
        "health.json:event_count": health.get("event_count"),
        "event-ontology.json:source_event_count": event_ontology.get(
            "source_event_count"
        ),
        "ontology-match-audit.json:event_count": ontology_audit.get("event_count"),
    }

    mismatches = {
        label: value
        for label, value in expected.items()
        if value is not None and value != event_count
    }
    if mismatches:
        formatted = ", ".join(f"{label}={value}" for label, value in mismatches.items())
        raise SystemExit(f"snapshot event count mismatch: events.json={event_count}, {formatted}")

    metrics = {
        "events_bytes": len(events_raw),
        "events_count": event_count,
        "events_payload_shape": payload_shape,
        "events_payload_keys": payload_keys,
        "events_sha256": hashlib.sha256(events_raw).hexdigest(),
        "health_generated_at": health.get("generated_at"),
        "ontology_entries": ontology_audit.get("ontology_entries"),
        "matched_events": ontology_audit.get("matched_events"),
        "ambiguous_events": ontology_audit.get("ambiguous_events"),
    }
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
