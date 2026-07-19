# Course Traceability

AEC integrates course learning as independently authored operational principles. It
does not distribute source lessons or inject transcripts into agent prompts.

The machine-readable inventory is
[`provenance/course-guidance.json`](../../provenance/course-guidance.json). Validation
requires all 13 AI Engineer lessons and all eight AIA Week 5 Evals & Monitoring lessons.

## AI Engineer effects

| Lessons | Operational effect |
| --- | --- |
| 1-3 | The engineer owns outcomes, context, harness quality, and explicit checkpoints. |
| 4-6 | Agent selection, repository foundations, and procedures are deliberate contracts. |
| 7-8 | Specs and plans resolve ambiguity before shared mutation. |
| 9-11 | Build, verification, review, and deploy require exact evidence at their real boundary. |
| 12-13 | Parallel work needs isolated ownership, budgets, stop rules, and serialized integration. |

## Evals and monitoring effects

| Lessons | Operational effect |
| --- | --- |
| 1-3 | Instrument explicit boundaries and retain structured traces, errors, latency, and cost where applicable. |
| 4-5 | Evaluate probabilistic behavior and enforce deterministic constraints. |
| 6-7 | Human judgment defines quality; model judges require measured human alignment. |
| 8 | Keep evaluation evidence portable across vendors and tools. |

## Procedure rule

Every local procedure must define entry evidence, exit evidence, stop conditions,
blocker handling, literal verification, handoff, a good example, a finished condition,
and an anti-example. A procedure name without those contracts is not operational.

## Source handling

The private source material remains outside this repository in the education workspace.
Only lesson identifiers, titles, and original summaries needed for traceability are
stored here. This keeps learning provenance visible without turning education content
into copied runtime policy.
