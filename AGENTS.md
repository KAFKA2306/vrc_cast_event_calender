# AGENTS.md — vrc_cast_event_calender Agent Operating Contract

This file is the canonical operating contract for coding and repository agents working in `KAFKA2306/vrc_cast_event_calender`.

## 1. Mission

Keep the public VRChat event calendar as a truthful, reproducible projection of the canonical snapshot produced by `KAFKA2306/cast_event_cal`.

Optimize for:

1. projection integrity over feature count;
2. source-commit and artifact-hash traceability;
3. fail-closed publication;
4. one canonical workline per outcome;
5. production verification after build/deploy;
6. durable continuation after interruption;
7. cleanup at the fixed point.

A 200 response, successful build, deployment dispatch, or visible page is not sufficient evidence of correct publication.

## 2. Source-of-truth precedence

When information conflicts, use this order:

1. current user request and explicit acceptance criteria;
2. canonical snapshot, source commit, hashes, and health produced by `KAFKA2306/cast_event_cal`;
3. this repository's projection manifest, verification scripts, workflows, and generated public artifacts;
4. exact-head CI and production HTTP/read-back evidence;
5. current repository documentation;
6. Issue/PR prose and historical reports;
7. previous conversation context, memory, or inference.

Do not let stale prose, a previous deployment, or an older local artifact override the current canonical snapshot contract.

## 3. Contract before change

For non-trivial work define:

- **Goal** — observable projection/delivery outcome;
- **Contract** — what may change and what must remain unchanged;
- **Acceptance Criteria** — deterministic conditions that can falsify completion;
- **Evidence** — source commit, manifest, hashes, tests, workflow runs, HTTP/read-back receipts;
- **Stopping Condition** — the fixed point after which further work is a separate outcome.

The Contract is both the minimum required result and the maximum allowed scope.

## 4. Projection-only boundary

This repository owns:

- receiving the canonical `public/` snapshot;
- validating snapshot completeness and health;
- recording source commit and deterministic snapshot/artifact hashes;
- generating/maintaining projection metadata;
- static delivery through GitHub Pages / Cloudflare Pages where configured;
- production HTTP/read-back verification.

It does **not** own:

- event collection;
- event classification;
- organizer/source interpretation;
- ontology truth;
- an independent canonical event database.

Do not add a second collector, classifier, ontology authority, or source-of-truth store here. When canonical content is wrong, repair `cast_event_cal`; when projection/parity/delivery is wrong, repair this repository.

## 5. Goal-driven execution loop

For multi-step work, keep one Goal active and iterate:

```text
inspect source + projection state
  -> define smallest change
  -> implement
  -> run cheapest relevant verifier
  -> inspect parity / production evidence
  -> repair if falsified
  -> escalate verification only as needed
  -> stop at the fixed point
```

A failed parity, health, hash, deployment, or production check is input to repair. Never convert it into success by weakening the gate or by reporting only the successful earlier stage.

## 6. Durable continuation and canonical workline

Before editing:

1. inspect current `main`, relevant Issues, open PRs, branches, workflows, `projection-manifest.json`, and production verification artifacts;
2. continue the existing canonical Issue/branch/PR when it already owns the same Goal;
3. otherwise create one bounded workline;
4. do not create competing manifests, parallel deployment pipelines, duplicate source stores, or replacement branches for the same outcome.

When work is blocked, preserve a resumable checkpoint in the owning Issue/PR or existing repository evidence surface: last verified source revision, current projection revision, failing stage, exact mismatch/blocker, and next action. Do not invent a second state database for agent memory.

## 7. Evidence-driven completion

Material operational claims must be treated as one of:

- **VERIFIED** — directly supported by current source/repository/test/CI/production evidence;
- **OBSERVED** — explicitly supplied observation;
- **INFERRED** — derived from evidence and reported as inference;
- **UNVERIFIED** — not inspected and never stated as fact;
- **FABRICATED** — forbidden.

Do not infer freshness from file modification time or deploy time. Keep source snapshot generation time, receive time, and deploy time distinct.

Do not claim parity from filenames or counts alone when the contract requires bytes/SHA-256/source revision equality.

## 8. Fail-closed publication boundary

Publication must fail when required evidence is missing or contradictory, including as applicable:

- malformed or incomplete canonical snapshot;
- `health.status != ok`;
- nonzero failed-source state where the current contract forbids it;
- source commit mismatch;
- snapshot digest mismatch;
- artifact byte/hash mismatch;
- generated manifest inconsistency;
- production HTTP/read-back mismatch.

Never publish a partial or stale snapshot as the newest healthy state merely because deployment infrastructure is available.

## 9. Verification ladder

Use the cheapest relevant verifier first, then escalate.

Current canonical local checks include:

```bash
python scripts/verify_public_snapshot.py
python -m unittest tests.test_projection_manifest -v
```

For workflow/deployment changes, verify exact-head CI and then the applicable production URLs/artifacts. Inspect the deployed `projection-manifest.json` and source revision relationship when that is the owning postcondition.

A build is not deployment proof. A deployment is not parity proof. A 200 response is not content-integrity proof.

## 10. Source/projection handshake

For every canonical refresh, preserve the ability to answer:

- which `cast_event_cal` commit produced this projection;
- which canonical snapshot digest was received;
- which artifact paths/bytes/SHA-256 values were published;
- when the source snapshot was generated;
- when this repository received and deployed it;
- whether health/parity/production verification passed.

Do not hand-edit projected event content to repair an upstream factual problem.

## 11. Builder / Auditor separation

Treat implementation and acceptance as separate phases even when one agent performs both sequentially.

### Builder

May change projection scripts, tests, manifests, workflows, UI/static delivery files, and docs within the bounded Contract.

### Auditor

Independently verifies:

- projection-only responsibility was preserved;
- source commit and snapshot identity are correct;
- hashes/counts/health satisfy the current contract;
- exact-head CI belongs to the reviewed revision;
- production read-back matches the intended projection;
- no failed stage is hidden by a later success claim;
- task-created residue and duplicate worklines are removed.

Implementation intent is never acceptance evidence.

## 12. Fixed point

Stop when all are true:

- the requested projection/delivery Goal exists;
- required local tests/audits pass;
- source revision and projection manifest are consistent;
- exact-head CI is verified when applicable;
- required deployment has completed when in scope;
- production read-back proves the intended postcondition;
- owning Issue/PR state is correct;
- temporary files, stale branches/PRs created by the task, and duplicate artifacts are gone;
- remaining ideas are separate outcomes, not required repairs.

## 13. Final report

Report only verified state relevant to the task:

- Issue/PR/commit URL;
- source commit and projection revision when relevant;
- tests/CI results;
- parity/manifest result;
- production verification result;
- cleanup result;
- blocker and exact next action when unfinished.

Never claim canonical correctness, deployment, production parity, or freshness without inspecting the corresponding evidence.