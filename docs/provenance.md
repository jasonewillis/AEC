# Provenance and Licensing

The machine-readable lock is
[`provenance/upstream-lock.json`](../provenance/upstream-lock.json). Validation rejects
unpinned revisions and unsafe relationship changes.

| Source | Pinned revision | Relationship | License boundary |
| --- | --- | --- | --- |
| `owainlewis/workflows` | `ce3ff09e27c501e7689fd069ece3aaab63da7e46` | Pattern source | MIT license verified upstream |
| `owainlewis/blueprint` | `3af769db122e3c16f64bb78bcd93eb64d3e541e8` | Authorized exact skill source | No upstream license verified; owner attests course-participant permission from Owain Lewis and directs this AEC install |
| AI Engineer course | Private education source | Factual provenance only | Exact source metadata, no protected expression |
| AIA Week 5 Evals & Monitoring | Private education source | Factual provenance only | Exact source metadata, hashes null until verified |

## Workflows boundary

AEC may learn from workflow sequencing patterns under the verified MIT license. Any
copied licensed material would require attribution and preservation of the applicable
license notice. The foundation currently uses independently authored contracts.

## Blueprint boundary

The seven Blueprint skills are installed byte-for-byte from the pinned revision using
an exact-revision local checkout and version 1.5.19 of the CLI behind the
upstream-documented `npx skills add owainlewis/blueprint` pattern. The CLI cannot use a
raw commit as a branch, so installing from the unpinned shorthand alone is not the
reproducible path. The source pin, install method, file hashes, installer hashes, and
Claude/Codex discovery paths are recorded in
[`blueprint-skills.json`](../provenance/blueprint-skills.json). The canonical copies
live under `.agents/skills/` for Codex. Claude discovers relative symlinks under
`.claude/skills/`, so both runtimes resolve the same bytes.

The authorization basis is the repository owner's attestation that Owain Lewis, the
course creator, directly permitted course participants to use the skills. The
repository owner directed this exact AEC installation under that permission. This is
not evidence that Blueprint is MIT licensed or generally redistributable. AEC does not
adapt the skill text, claim it as AEC-authored policy, or extend that permission to
other Blueprint content. See
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Course boundary

[`course-inventory.json`](../provenance/course-inventory.json) stores only factual
source-set identities, stable record identifiers, exact titles, source filenames, and
SHA-256 values when verified. The gateway PDF is supplemental and is not lesson 14.
Missing hashes remain `null`; they cannot be replaced with summaries.

AEC does not store or derive lesson principles, summaries, operational effects,
guidance, prompt text, or lesson-to-policy mappings. Runtime procedures cite only the
independently authored AEC principle registry. Private storage is not treated as a safe
harbor for copied, adapted, paraphrased, rewritten, or summarized source expression.

## Update procedure

1. Inspect the upstream repository and license or direct authorization at the proposed
   revision.
2. Record the full 40-character Git commit, relationship, authorization basis, and
   exact file hashes.
3. Add a red test for any changed licensing, authorization, hash, or discovery
   invariant.
4. Update original documentation and code without weakening the boundary.
5. Run the full foundation gate on the exact candidate revision.
