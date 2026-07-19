# Factual Course Provenance

AEC records private course sources for provenance auditing only. The machine-readable
record is [`provenance/course-inventory.json`](../../provenance/course-inventory.json),
validated against a closed factual schema and semantic checks.

## Source sets

| Source set | Primary records | Hash status | Supplemental records |
| --- | ---: | --- | ---: |
| AI Engineer | 13 numbered RTF lessons | Exact SHA-256 recorded for all 13 | One gateway PDF with an exact SHA-256 |
| AIA Week 5 Evals & Monitoring | Eight lessons | `null` until source files are verified | None |

The gateway PDF is supplemental to AI Engineer. It is not lesson 14. Other PDFs and
web links in the private education folder are not part of the numbered inventory.

## Allowed metadata

Each source record may contain only:

- a stable factual identifier;
- the exact title;
- a source filename when verified; and
- a lowercase SHA-256 value when verified, otherwise `null`.

Source sets also record a factual identity, title, private visibility, and the fixed
`factual-provenance-only` relationship.

## No-adoption boundary

AEC does not store copied, adapted, paraphrased, rewritten, or summarized private
course expression. The inventory cannot contain principles, summaries, operational
effects, guidance, prompts, phase mappings, or lesson-to-policy mappings. Private
storage does not make those forms safe to adopt.

Runtime procedures reference only identities from the independently authored
[`config/principles/aec-engineering.json`](../../config/principles/aec-engineering.json)
registry. The foundation validator scans mapped runtime authority and fails if a
private course identity appears there.
