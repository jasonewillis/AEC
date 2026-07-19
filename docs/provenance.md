# Provenance and Licensing

The machine-readable lock is
[`provenance/upstream-lock.json`](../provenance/upstream-lock.json). Validation rejects
unpinned revisions and unsafe relationship changes.

| Source | Pinned revision | Relationship | License boundary |
| --- | --- | --- | --- |
| `owainlewis/workflows` | `ce3ff09e27c501e7689fd069ece3aaab63da7e46` | Pattern source | MIT license verified upstream |
| `owainlewis/blueprint` | `1787459f5a9dc5f95b04f156b1b0877696fb81c5` | Reference-only capability index | No adoption license verified for this project |
| AI Engineer course | Private education source | Factual provenance only | Exact source metadata, no protected expression |
| AIA Week 5 Evals & Monitoring | Private education source | Factual provenance only | Exact source metadata, hashes null until verified |

## Workflows boundary

AEC may learn from workflow sequencing patterns under the verified MIT license. Any
copied licensed material would require attribution and preservation of the applicable
license notice. The foundation currently uses independently authored contracts.

## Blueprint boundary

Blueprint helps identify capability categories such as design, planning, testing,
review, improvement, and implementation. Until a compatible adoption license is
verified, AEC must not copy, adapt, install, redistribute, or use Blueprint expressive
skill text as runtime fallback.

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

1. Inspect the upstream repository and license at the proposed revision.
2. Record the full 40-character Git commit and relationship.
3. Add a red test for any changed licensing or provenance invariant.
4. Update original documentation and code without weakening the boundary.
5. Run the full foundation gate on the exact candidate revision.
