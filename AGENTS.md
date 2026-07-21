# Agent Instructions

These rules apply to every agent working in this repository.

## Authority

- AEC is read-only mentoring logic. It must never execute a recommended procedure or
  mutate lifecycle, project, review, merge, or deployment state.
- Consumer projects own their state, evidence, permissions, and releases.
- Keep one authoritative lifecycle writer per consumer. Do not create a competing
  ledger or infer movement from narration, labels, issue closure, or merge events.

## Delivery method

- Work from an issue with binary Expected Results, Good, Finished, and Not wanted.
- Reproduce defects at the closest practical user boundary before changing code.
- Add an honest red test or fixture, make the smallest coherent change, then prove
  green on the exact revision.
- Parallelize independent read-only work and isolated implementation. Serialize
  claims, integration, pushes, state changes, merges, and releases.
- Treat `Blocked`, `Needs review`, `Evidence needed`, and `Ready` as exclusive gate
  states with fail-closed precedence.

## Source and licensing boundaries

- Do not copy or adapt Blueprint expressive content unless a compatible license or
  direct authorization is verified and recorded. The seven pinned Blueprint skills
  are installed byte-for-byte under the repository owner's attestation of direct
  permission from Owain Lewis. That permission is not an upstream MIT license claim.
- Keep Blueprint skills under `.agents/skills/` as the canonical Codex-discoverable
  source and `.claude/skills/` as relative symlinks to that source. Hash, provenance,
  and parity validation must pass before those files are trusted.
- Do not copy course transcripts, recordings, slides, or proprietary lesson text.
- Keep private course provenance factual-only: stable source-set identities, exact
  titles, source filenames, and verified hashes. Do not store summaries, mappings,
  effects, guidance, or prompt text derived from private lessons.
- Define runtime principles independently under AEC-owned identities. Private course
  identifiers must never become procedure or policy authority.
- Pin every upstream reference to a full Git commit and validate the relationship.

## Quality

- Prefer standard-library, deterministic validation for the portable core.
- Schema, validator, fixtures, and documentation must agree.
- A green-only check is not a proof harness. Every critical gate needs a red canary.
- Do not declare work finished from an open branch, stale check, skipped check, or
  evidence from a different revision.
- Never include agent names as commit co-authors.
