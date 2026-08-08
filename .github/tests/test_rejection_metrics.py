from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / ".github" / "scripts"))

from export_rejection_metrics import MetricsError, build_snapshot, compare_distribution  # noqa: E402


def source_payload(counts: dict[str, int], accepted: int = 10) -> dict:
    return {
        "generated_at": "2026-08-03T03:04:32Z",
        "classifier_version": "1.8",
        "strategy_version": "ablation-informed-1.0",
        "candidate_count": accepted + sum(counts.values()),
        "production_accepted_count": accepted,
        "rejection_reason_counts": counts,
    }


class RejectionMetricsTests(unittest.TestCase):
    def test_build_snapshot_is_deterministic_and_balanced(self) -> None:
        source = source_payload({"missing_datetime": 70, "not_vrchat": 20})
        raw = json.dumps(source, sort_keys=True).encode()
        first = build_snapshot(source, raw)
        second = build_snapshot(source, raw)
        self.assertEqual(first, second)
        self.assertEqual(first["rejected_count"], 90)
        self.assertEqual(first["rejection_reason_counts"]["missing_datetime"], 70)
        self.assertAlmostEqual(first["rejection_reason_shares"]["not_vrchat"], 20 / 90)

    def test_rejects_unbalanced_reason_counts(self) -> None:
        source = source_payload({"missing_datetime": 10})
        source["candidate_count"] = 30
        with self.assertRaisesRegex(MetricsError, "must equal"):
            build_snapshot(source, b"{}")

    def test_large_distribution_shift_fails(self) -> None:
        baseline = build_snapshot(
            source_payload({"missing_datetime": 90, "not_vrchat": 10}),
            b"baseline",
        )
        current = build_snapshot(
            source_payload({"missing_datetime": 50, "not_vrchat": 50}),
            b"current",
        )
        failures = compare_distribution(current, baseline, max_share_shift=0.20)
        self.assertTrue(any("missing_datetime" in item for item in failures))
        self.assertTrue(any("not_vrchat" in item for item in failures))

    def test_small_distribution_shift_passes(self) -> None:
        baseline = build_snapshot(
            source_payload({"missing_datetime": 60, "not_vrchat": 40}),
            b"baseline",
        )
        current = build_snapshot(
            source_payload({"missing_datetime": 55, "not_vrchat": 45}),
            b"current",
        )
        self.assertEqual(
            compare_distribution(current, baseline, max_share_shift=0.10), []
        )

    def test_new_reason_is_checked_against_zero_baseline(self) -> None:
        baseline = build_snapshot(source_payload({"missing_datetime": 100}), b"baseline")
        current = build_snapshot(
            source_payload({"missing_datetime": 70, "new_reason": 30}),
            b"current",
        )
        failures = compare_distribution(current, baseline, max_share_shift=0.20)
        self.assertTrue(any("new_reason" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
