# Canonical flow

`KAFKA2306/vrc_cast_event_calender` is the **public projection/deploy surface** for VRChat event data. It is not an independent ingestion or classification system.

```text
KAFKA2306/cast_event_cal
  collect -> normalize -> deduplicate -> classify -> audit
  -> canonical public snapshot
        |
        | source commit + artifact hashes
        v
KAFKA2306/vrc_cast_event_calender
  receive -> parity validation -> static projection -> HTTP verification
        |
        +-> GitHub Pages
        +-> Cloudflare Pages
```

## Source-of-truth boundary

The canonical repository is `KAFKA2306/cast_event_cal`.

This projection repository may:

- receive the canonical `public/` snapshot;
- verify byte/hash/count parity and source commit identity;
- render user-facing static views;
- verify deployed HTTP artifacts;
- maintain projection-specific presentation code.

This projection repository must not:

- independently scrape event sources;
- independently classify or deduplicate events;
- maintain a second event identity or acceptance state;
- silently rewrite canonical event facts;
- run unrelated write-capable scheduled research automation.

`projection-manifest.json` is the machine-readable boundary contract. It must keep `role = projection_only`, identify `KAFKA2306/cast_event_cal` as the source repository, and declare both `classification_logic_in_this_repo = false` and `independent_collection_in_this_repo = false`.

## Repository KPIs

Only these three repository-level KPIs are used for this projection boundary:

1. `canonical_snapshot_acceptance_rate` — canonical snapshots that pass projection parity validation / canonical snapshots received.
2. `projection_freshness` — elapsed time between canonical snapshot generation and validated public projection.
3. `public_verification_success_rate` — production HTTP verification successes / production verification attempts.

Unavailable measurements remain unavailable; they are not converted to zero. Event volume is descriptive inventory, not a success KPI.

## Failure ownership

Collection, normalization, source conflicts, classification, event identity, and acceptance/rejection failures belong to `cast_event_cal`. Projection parity, deployment, static rendering, and public HTTP verification failures belong here. The same failure should not be reimplemented as an independent decision system in both repositories.

## CI ratchet

`Verify public snapshot` protects this boundary by validating the current snapshot and projection manifest, rejecting known legacy publisher/collector paths, rejecting the unrelated weekly write-capable research workflow, checking the canonical documentation links, and requiring a clean checkout after tests.

Changing this boundary requires an explicit architecture change in both repositories; adding a new collector or classifier here is not a normal feature addition.
