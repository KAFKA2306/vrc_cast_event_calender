# Rejection reason metrics

Issue #25 requires rejection decisions to remain inspectable across CI runs instead of existing only inside one ingestion payload.

## Source contract

The production repository does not reclassify events. It reads the canonical artifact produced by `KAFKA2306/cast_event_cal`:

`public/yahoo-best-1000-audit.json`

The exporter copies `rejection_reason_counts` verbatim and verifies that their sum equals:

`candidate_count - production_accepted_count`

A mismatch fails closed. The output also records the canonical `generated_at`, classifier version, strategy version, accepted/rejected totals, reason shares, and SHA-256 of the exact source bytes.

## Snapshot schema v1.0

`audit/rejection-reasons-current.json` and each uploaded workflow artifact use these fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Metrics artifact schema. Currently `1.0`. |
| `source_generated_at` | `generated_at` copied from the canonical audit payload. |
| `classifier_version` | Canonical classifier version. |
| `strategy_version` | Canonical query/selection strategy version. |
| `candidate_count` | Number of candidates evaluated by the canonical audit. |
| `accepted_count` | Canonical `production_accepted_count`. |
| `rejected_count` | `candidate_count - accepted_count`. |
| `rejection_reason_counts` | Per-reason integer counts copied from the canonical artifact. |
| `rejection_reason_shares` | Each reason count divided by `rejected_count`. |
| `source_sha256` | SHA-256 of the exact canonical JSON bytes used for the run. |

The versioned baseline is `.github/audit/rejection-reasons-baseline.json`. It intentionally records the reviewed distribution and source/classifier versions; it is changed only through a reviewed commit.

## Currently observed rejection identifiers

The 2026-08-03 canonical best-1000 audit contains these identifiers. This repository does not redefine classifier semantics; identifiers are retained verbatim so historical comparisons remain stable.

- `conflicting_date_context`
- `giveaway_only`
- `missing_datetime`
- `missing_event_marker`
- `missing_participation_method`
- `not_vrchat`
- `past_event`
- `past_event_now`
- `product_only`
- `retweet_below_threshold`
- `too_far_future`

New identifiers are allowed by the schema but participate in the same distribution-shift check, with a baseline share of zero.

## Regression gate

CI compares each reason's share of all rejected candidates against the reviewed baseline. The current operational threshold is an absolute shift greater than **0.15 (15 percentage points)** for any reason.

This threshold is an operational regression guard, not a statistical significance claim. A large shift fails CI and requires inspection of the canonical input/classifier before the baseline is deliberately updated.

The test suite also verifies that:

- balanced counts produce deterministic metrics;
- inconsistent accepted/rejected accounting is rejected;
- small share changes pass;
- large share changes fail;
- a newly introduced high-share reason is detected against a zero baseline.

## Persistence

The `Rejection reason metrics` workflow uploads `rejection-reasons-current.json` on every run. On successful non-PR runs it also commits the latest snapshot to `audit/rejection-reasons-current.json`. The workflow is triggered after the canonical production sync completes, so the versioned snapshot is refreshed from the same canonical source used by production.
