# Decision Outcomes

AEC leads material decisions and then lets the consumer check whether that leadership
helped. The loop is proposal, card, selection, observed result, verdict. It is local,
deterministic, and read-only. Nothing in it uploads, stores, schedules, or mutates
anything.

```text
decision_context (2.0.0) -> resolver -> card.decision_support -> outcome receipt (1.0.0)
        proposal                brief             selection              verdict
```

## Material-decision context

`decision_context` is versioned at `2.0.0` and remains optional. Routine work omits it
and the card still renders `decision_support: null`. AEC never manufactures choices.

A supplied context must carry every fact a real recommendation depends on:

| Field | Why it is required |
| --- | --- |
| `context.revision` | Binds the decision to the exact revision it was formed on. A stale or foreign revision fails closed. |
| `context.evidence_quality` | `direct-verified`, `indirect`, or `assumed`. States what the recommendation is actually standing on. |
| `recommendation.confidence` | `high`, `medium`, or `low`. Confidence may never exceed the declared evidence quality. |
| `recommendation.principal_uncertainty` | Names the one thing most likely to make the recommendation wrong. |
| `recommendation.expected_result` | One `measure` identity, a `direction`, and a `threshold`. Without it there is nothing to compare against later. |
| `recommendation.revisit_when` | Observable facts that would justify revisiting the recommendation. |
| `authority.owner` | `agent`, `consumer-owner`, or `external`. AEC is never an authority owner. |

Choice identities and the expected `measure` are lowercase hyphenated identities so a
receipt can cite them exactly. Prose belongs in `summary`, `why`, and `threshold`.

`high` confidence requires `direct-verified` evidence, and `medium` rejects `assumed`
evidence. That rule is what "insufficient current context" means here: an unsupported
confidence claim is rejected before any card is rendered.

## Outcome receipt

An outcome receipt is a local record conforming to
[`outcome-receipt.schema.json`](../../schemas/outcome-receipt.schema.json). It binds the
exact decision it is reporting on and then states what actually happened:

- `decision.resolution_hash` and `decision.revision` must equal the rendered card;
- `decision.selected_choice` must be one declared choice;
- `observed_result.measure` must equal the expected measure;
- `verification` carries evidence kinds, acceptance, and the revision observed;
- `coaching.burden` and `coaching.transfer` record what the mentoring cost and taught;
- `verdict` is one of `supported`, `partially-supported`, `unsupported`, `harmful`, or
  `inconclusive`.

Every receipt value is a closed enumeration, a lowercase hyphenated identity, a
boolean, a 40-character revision, or a SHA-256 binding. A receipt contains no free
text, so it cannot carry prompts, model output, code, diffs, evidence bodies, paths,
repository identities, issue titles, user identity, secrets, or health data. Prohibited
field names and unknown fields fail closed before any value is read.

The verdict is not taken on trust. It is derived from the receipt's own facts and the
declared verdict must equal it:

| Facts | Verdict |
| --- | --- |
| No accepted verification fact at the decision revision | `inconclusive` |
| `expectation: unobserved` | `inconclusive` |
| `expectation: met` | `supported` |
| `expectation: partially-met` | `partially-supported` |
| `expectation: missed` | `unsupported` |
| `expectation: reversed` | `harmful` |

`met` and `partially-met` require the observed direction to match the expected
direction; `reversed` requires that it does not. A summary that flatters the
recommendation is rejected, not recorded.

## Local evaluation

```bash
python3 tools/evaluate_outcomes.py tests/fixtures/outcomes/golden.json
```

The evaluator counts coaching burden and learning transfer beside verdict counts, lists
rejected records by index and code, and exits non-zero when any record fails closed. Its
report never echoes the input location and always declares `authoritative: false` and
`causal_claim: false`. Counts are association only; they never prove that a
recommendation caused an outcome.

`tests/fixtures/outcomes/proposal.json` is the project-neutral worked example. It is the
consumer state that produces the card in `tests/fixtures/outcomes/golden.json`, which the
receipt in the same file reports on.
