# AGENTS.md

- Check the current default branch, open Issues, open pull requests, and relevant workflows before changing the repository.
- Keep this repository focused on publishing the snapshot produced by `KAFKA2306/cast_event_cal`; do not add a second event collector, classifier, or source database here.
- Use standard technical terms and plain language. Do not introduce repository-specific process names, maturity levels, or status classifications.
- Prefer updating an existing file over adding a new document, and do not duplicate the same guidance across documents.
- Preserve source commit, snapshot hash, artifact hash, and health checks when changing publication behavior.
- Do not treat a successful build or HTTP 200 response as proof that the deployed content matches the intended snapshot.
- Before completion, run the relevant existing tests or verification scripts and check the actual deployed URL when production behavior changes.
- Do not weaken validation, provenance, security, accessibility, or deployment checks to make a change pass.
- Keep changes as small as practical and avoid new dependencies, configuration, or workflows when existing repository features are sufficient.
- Record remaining unverified behavior explicitly instead of guessing.
