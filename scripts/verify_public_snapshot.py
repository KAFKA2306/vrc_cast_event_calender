#!/usr/bin/env python3
"""Verify that the deploy repository contains one coherent public snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    raw = path.read_bytes()
    if not raw:
        raise SystemExit(f"{path.name} is empty")
    try:
        return raw, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.name} is not valid JSON: {exc}") from exc


def main() -> None:
    events_raw, events = load_json(ROOT / "events.json")
    _, health = load_json(ROOT / "health.json")
    _, event_ontology = load_json(ROOT / "event-ontology.json")
    _, ontology_audit = load_json(ROOT / "ontology-match-audit.json")

    if not isinstance(events, list):
        raise SystemExit("events.json must contain a JSON array")

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
        "events_sha256": hashlib.sha256(events_raw).hexdigest(),
        "health_generated_at": health.get("generated_at"),
        "ontology_entries": ontology_audit.get("ontology_entries"),
        "matched_events": ontology_audit.get("matched_events"),
        "ambiguous_events": ontology_audit.get("ambiguous_events"),
    }
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
