# Shipping Context — AEC

Binds the portable Keep Shipping guidance (`~/.claude/CLAUDE.md`) to this repository.
Distilled rationale in `docs/delivery/keep-shipping.md`. Repository contract in `AGENTS.md`,
which wins on any conflict.

## Shipping Toward

The live command, not a document:

```bash
gh issue list --repo jasonewillis/AEC --state open \
  --json number,title,labels \
  --template '{{range .}}#{{.number}} [{{range .labels}}{{.name}} {{end}}] {{.title}}{{"\n"}}{{end}}'
```

Secondary, and **treat as a hint rather than truth**:
`docs/architecture/coaching-interaction.md` sections "Gap map", "Delivery sequence", and
"Trustworthy-beta release gate", plus `docs/delivery/roadmap.md`.

Those documents have drifted before. On 2026-08-03 the Gap map still described consumer
state construction and pin compatibility as unbuilt when `aec/state_builder.py` and
`tools/validate_consumer_connection.py` already existed. Re-verify against the code before
planning a session from either file.

## Escalate Only For

Replaces the portable standing four. Everything else is yours to decide.

1. **Licensing and provenance.** Anything touching the pinned Blueprint skills,
   `provenance/`, `skills-lock.json`, or the attestation scope. Installing new upstream
   bytes needs a recorded authorization; it is not a version bump.
2. **Relaxing an admission or trust-root check.** Adding checks, canaries, or tests is
   ordinary work. Weakening one, or granting any future revision authority, is not.
3. **Branch-protection changes on `main`.** Removing a required check, even temporarily and
   even to land a fix, is an explicit exception that must be recorded with the SHA.
4. **Publishing a release or moving a consumer-facing contract version.**

Not escalation triggers, despite feeling like them: adding tests, adding red canaries,
filing issues, correcting a factual error in tracked documentation, or fixing a control that
reports success while enforcing nothing.

## Never Do

- Execute a recommended procedure on a consumer's behalf, or mutate lifecycle, project,
  review, merge, or deployment state. AEC is read-only mentoring logic.
- Commit directly to `main`.
- Add an agent as a commit co-author.
- Copy course transcripts, recordings, slides, or course-derived mentoring content into the
  tracked repository. Tracked course provenance stays factual-only.
- Declare work finished from an open branch, a stale check, a skipped check, or evidence
  from a different revision.
- Touch CT 105 (`192.168.0.205`).

## Done Means

A pull request, merged, with every gate satisfied on the exact head:

- `python3 tools/validate_foundation.py` exits 0, red canaries included.
- `python3 -m unittest discover -s tests` green — 353 at `a9a9d00`; the count only rises.
- `python3 tools/generate_source_declaration.py --check` passes, or the declaration is
  regenerated in the same change.
- Required checks `foundation-validate` and `admit` both SUCCESS. **`admit` became required
  on 2026-08-03**; before that it reported without gating.
- PR body carries a populated **Expected Outcomes** section with binary checkboxes, a
  `## Review Evidence` section, and a risk class line (`class: security|structural|additive|content`).
- An adversarial review pass is recorded at
  `~/.claude/codex-findings/jasonewillis-AEC/<pr>.json`, normalized by
  `~/.claude/scripts/codex-findings-normalize.py`. **Required for every PR including
  docs-only** — `.codex-belt-required` applies universally.
- Merge verified by `gh pr view <N> --json state,mergedAt` returning `MERGED` with non-null
  `mergedAt`. A green label is not a merge.

## Local traps that waste sessions

- A stray `.DS_Store` reds `tests/test_blueprint_skills.py` while CI is green on the same
  SHA. Run `find . -name .DS_Store -delete` before believing a local red. Gitignore did not
  close this — the validator walks the filesystem.
- **Regenerate the source declaration after mutating a validator.** A stale digest
  manufactures unrelated failures and will make a sound guard look broken.
- A mutation result expires when a later guard is added in front of it. Re-run mutations
  after adding any new check.
- `statusCheckRollup` reports `UNSTABLE` mid-flight. Re-query before believing it.
- Squash-merge rewrites SHAs, so `commits_not_on_main` is noise. Check content or PR state.
