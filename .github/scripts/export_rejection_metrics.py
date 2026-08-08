#!/usr/bin/env python3
"""Export and regression-check Yahoo rejection reason metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"


class MetricsError(ValueError):
    """Raised when source or metrics data violates the contract."""


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MetricsError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MetricsError(f"{path}: top-level JSON must be an object")
    return payload, raw


def _non_negative_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MetricsError(f"{key} must be a non-negative integer")
    return value


def build_snapshot(source: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    candidate_count = _non_negative_int(source, "candidate_count")
    accepted_count = _non_negative_int(source, "production_accepted_count")
    if accepted_count > candidate_count:
        raise MetricsError("production_accepted_count cannot exceed candidate_count")

    counts = source.get("rejection_reason_counts")
    if not isinstance(counts, dict) or not counts:
        raise MetricsError("rejection_reason_counts must be a non-empty object")

    normalized_counts: dict[str, int] = {}
    for reason, count in counts.items():
        if not isinstance(reason, str) or not reason.strip():
            raise MetricsError("rejection reason keys must be non-empty strings")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise MetricsError(
                f"rejection count for {reason!r} must be a non-negative integer"
            )
        normalized_counts[reason] = count

    rejected_count = candidate_count - accepted_count
    counted_rejections = sum(normalized_counts.values())
    if counted_rejections != rejected_count:
        raise MetricsError(
            "sum(rejection_reason_counts) must equal "
            "candidate_count - production_accepted_count "
            f"({counted_rejections} != {rejected_count})"
        )

    shares = {
        reason: (round(count / rejected_count, 8) if rejected_count else 0.0)
        for reason, count in sorted(normalized_counts.items())
    }

    for key in ("generated_at", "classifier_version", "strategy_version"):
        value = source.get(key)
        if not isinstance(value, str) or not value:
            raise MetricsError(f"{key} must be a non-empty string")

    return {
        "schema_version": SCHEMA_VERSION,
        "source_generated_at": source["generated_at"],
        "classifier_version": source["classifier_version"],
        "strategy_version": source["strategy_version"],
        "candidate_count": candidate_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "rejection_reason_counts": dict(sorted(normalized_counts.items())),
        "rejection_reason_shares": shares,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
    }


def _validate_snapshot(snapshot: dict[str, Any], label: str) -> None:
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise MetricsError(f"{label}: unsupported schema_version")
    rejected_count = _non_negative_int(snapshot, "rejected_count")
    counts = snapshot.get("rejection_reason_counts")
    shares = snapshot.get("rejection_reason_shares")
    if not isinstance(counts, dict) or not isinstance(shares, dict):
        raise MetricsError(f"{label}: rejection counts and shares must be objects")
    if any(
        isinstance(count, bool) or not isinstance(count, int) or count < 0
        for count in counts.values()
    ):
        raise MetricsError(f"{label}: rejection counts must be non-negative integers")
    if sum(counts.values()) != rejected_count:
        raise MetricsError(f"{label}: rejection counts do not sum to rejected_count")
    for reason, share in shares.items():
        if reason not in counts:
            raise MetricsError(f"{label}: share without count for {reason!r}")
        if (
            isinstance(share, bool)
            or not isinstance(share, (int, float))
            or not math.isfinite(share)
        ):
            raise MetricsError(f"{label}: invalid share for {reason!r}")
        if share < 0 or share > 1:
            raise MetricsError(f"{label}: share outside [0, 1] for {reason!r}")


def compare_distribution(
    current: dict[str, Any],
    baseline: dict[str, Any],
    max_share_shift: float,
) -> list[str]:
    if max_share_shift < 0 or max_share_shift > 1:
        raise MetricsError("max_share_shift must be between 0 and 1")
    _validate_snapshot(current, "current")
    _validate_snapshot(baseline, "baseline")

    current_shares = current["rejection_reason_shares"]
    baseline_shares = baseline["rejection_reason_shares"]
    reasons = sorted(set(current_shares) | set(baseline_shares))

    failures = []
    for reason in reasons:
        before = float(baseline_shares.get(reason, 0.0))
        after = float(current_shares.get(reason, 0.0))
        shift = abs(after - before)
        if shift > max_share_shift:
            failures.append(
                f"{reason}: rejection share shifted by {shift:.4f} "
                f"({before:.4f} -> {after:.4f}), limit={max_share_shift:.4f}"
            )
    return failures


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--max-share-shift", type=float, default=0.15)
    args = parser.parse_args()

    try:
        source, source_bytes = _read_json(args.input)
        current = build_snapshot(source, source_bytes)
        if args.baseline:
            baseline, _ = _read_json(args.baseline)
            failures = compare_distribution(current, baseline, args.max_share_shift)
            if failures:
                joined = "\n".join(f"- {failure}" for failure in failures)
                raise MetricsError(
                    f"rejection distribution regression detected:\n{joined}"
                )
        write_json_atomic(args.output, current)
    except (OSError, MetricsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"wrote {args.output}: rejected={current['rejected_count']} "
        f"reasons={len(current['rejection_reason_counts'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
