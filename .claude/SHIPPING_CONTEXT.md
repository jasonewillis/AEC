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

That command lists open issues in GitHub's default order. It is the authority on **what is
open**, not on **what is next** — it carries no priority ordering, dependency ordering, or
release-gate filter. Read the labels (`release-blocker`, `post-review`, `circle-back`) and
the delivery sequence before choosing, and never let its ordering place downstream work
ahead of its blocker.

Secondary, and **treat as a hint rather than truth**:
`docs/architecture/coaching-interaction.md` sections "Gap map", "Delivery sequence", and
"Trustworthy-beta release gate", plus `docs/delivery/roadmap.md`.

Those documents have drifted before, so re-verify against the code before planning a session
from either.

But do not overcorrect, as an earlier draft of this file did: `aec/state_builder.py` and
`tools/validate_consumer_connection.py` **exist**, and that is not the same as the gaps being
closed. `state_builder` provides bounded AEC-self construction and leaves consumer state
production outside AEC; `validate_consumer_connection` runs two fixed built-in probes, not a
consumer's own contract. **File existence is not completed capability.** Check what a module
actually does for a consumer before claiming a Gap map row overstates its gap.

## Escalate Only For

This section **is** AEC's escalation list, in the sense the global contract intends: it is
what `~/.claude/CLAUDE.md` means by a project supplying its own gates. What it does not do is
*drop* any of the portable four — an earlier draft replaced them and silently lost real
gates. All four are restated here so the list is self-contained and can be read alone:

1. Changes **user-visible product scope** — what ships, not how it is built.
2. Involves **pricing, legal, or compliance**.
3. Requires **credentials or authority you do not already hold**.
4. Is **destructive at scale** — bulk deletes, history rewrites, reverting shipped work.

AEC adds five more.

5. **Licensing and provenance.** Anything touching the pinned Blueprint skills,
   `provenance/`, `skills-lock.json`, or the attestation scope. Installing new upstream
   bytes needs a recorded authorization; it is not a version bump.
6. **Relaxing an admission or trust-root check.** Adding checks, canaries, or tests is
   ordinary work. Weakening one, or granting any future revision authority, is not.
7. **Branch-protection changes on `main`.** Removing a required check, even temporarily and
   even to land a fix, is an explicit exception that must be recorded with the SHA.
8. **Publishing a release or moving a consumer-facing contract version.**
9. **A material fork.** Any choice that changes quality, risk, reversibility,
   maintainability, or scope in a way someone would want recorded. `AGENTS.md` requires two
   or three bounded choices with explicit tradeoffs, one named recommendation, the evidence
   quality it stands on, a confidence not exceeding that evidence, the principal
   uncertainty, one expected measurable result, and the named decision owner. Ranking the
   options yourself is not a substitute for presenting the fork.

Everything outside these nine is yours to decide. A routine step is not a material fork — do
not manufacture a choice menu where no real fork exists.

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
- Merge verified by `gh pr view "$PR" --json state,mergedAt` returning `MERGED` with a
  non-null `mergedAt`. Use a quoted variable or a literal number: an unquoted `<N>` is shell
  input redirection, not a placeholder. A green label is not a merge.

## Local traps that waste sessions

- A `.DS_Store` **as an immediate child of `.agents/skills/` or `.claude/skills/`** reds
  `tests/test_blueprint_skills.py` while CI is green on the same SHA, because the validator
  compares the exact children of those two directories against an allowlist of seven. A
  `.DS_Store` elsewhere in the repository does not red that test. `find . -name .DS_Store
  -delete` is still the fastest clear, but the diagnosis is those two directories.
  Gitignore did not close this — the validator walks the filesystem, not the index.
- **Regenerate the source declaration after mutating a validator.** A stale digest
  manufactures unrelated failures and will make a sound guard look broken.
- A mutation result expires when a later guard is added in front of it. Re-run mutations
  after adding any new check.
- **"Only the new test reds" is the wrong bar.** A mutation can legitimately red both a
  focused new test and a broader existing one without the new test being redundant. What
  matters is that the new test reds, and that you read WHICH tests red to confirm it
  exercises the boundary it claims. Sole-failure is evidence of specificity, not a
  requirement for validity.
- `UNSTABLE` is a `mergeStateStatus` value, not a `statusCheckRollup` one — that field is a
  list of check-run and status-context objects. Read the latest conclusion per context at the
  exact head rather than re-querying the wrong primitive.
- Squash-merge rewrites SHAs, so `commits_not_on_main` is noise. Check content or PR state.
