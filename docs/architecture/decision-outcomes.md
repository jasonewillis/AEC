# Decision Outcomes

AEC leads material decisions and then lets the consumer check whether that leadership
helped. The loop is proposal, card, selection, observed result, verdict. It is local,
deterministic, and read-only. Nothing in it uploads, stores, schedules, or mutates
anything.

```text
decision_context (2.0.0) -> resolver -> card (3.0.0) -> outcome receipt (1.0.0)
        proposal                brief    decision_support        verdict
```

`decision_context 2.0.0` and `outcome-receipt 1.0.0` are defined on this branch and have
not shipped, so both were completed in place rather than versioned again. The public card
moved from `2.0.0` to `3.0.0` because `card_hash` is a new required field on a shape that
already shipped.

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
| `recommendation.expected_result` | One `measure` identity, a `unit` identity, an exact integer `baseline` and `target`, a `direction`, and a human-readable `threshold`. Without exact numbers there is nothing to compare against later. |
| `recommendation.revisit_when` | Observable facts that would justify revisiting the recommendation. |
| `authority.owner` | `agent`, `consumer-owner`, or `external`. AEC is never an authority owner. |

Choice identities, the expected `measure`, and the expected `unit` are lowercase
hyphenated identities so a receipt can cite them exactly. Prose belongs in `summary`,
`why`, and `threshold`.

`baseline` and `target` are exact integers, and the declared `direction` must agree with
them: `decrease` requires `target < baseline`, `increase` requires `target > baseline`,
and `hold` requires `target == baseline`. A direction that contradicts its own numbers is
rejected before any card is rendered, because no later observation could be scored
against it.

`high` confidence requires `direct-verified` evidence, and `medium` rejects `assumed`
evidence. That rule is what "insufficient current context" means here: an unsupported
confidence claim is rejected before any card is rendered.

## Public card integrity

Every rendered card carries `card_hash`, computed at render time over the complete card
with only `card_hash` itself excluded. One closed validator covers every required card
field, its internal agreement — the rail position must match the rendered phase, the
draft transition must request the rendered gate and stay non-authoritative, and the
decision context must bind the card's own revision — and then recomputes `card_hash`
from the card's bytes.

Outcome verification runs that validator after the receipt's own closed shape and before
it reads any outcome fact. A card that is missing, malformed, incomplete, internally
inconsistent, or edited after rendering is rejected as `OUTCOME_RECEIPT_CARD_INVALID`, so
no decision binding, observed result, or verdict is read from a card that failed.

This is local structural and tamper integrity, not cryptographic proof of external
origin. `card_hash` detects a card that was truncated, edited, or reassembled; it does
not prove who produced the card, because anyone who can rewrite a card can also
recompute the hash. AEC adds no signing keys and no secrets.

## Outcome receipt

An outcome receipt is a local record conforming to
[`outcome-receipt.schema.json`](../../schemas/outcome-receipt.schema.json). It binds the
exact decision it is reporting on and then states what actually happened:

- `decision.resolution_hash` and `decision.revision` must equal the rendered card;
- `decision.selected_choice` must be the recommended choice;
- `observed_result` states the `measure`, the `unit`, and one exact integer `value`;
- `observed_revision` is the revision the result was observed at, after the change;
- `verification` carries evidence kinds, acceptance, and the revision observed;
- `coaching.burden` and `coaching.transfer` record what the mentoring cost and taught;
- `verdict` is one of `supported`, `partially-supported`, `unsupported`, `harmful`, or
  `inconclusive`.

Every receipt value is a closed enumeration, a lowercase hyphenated identity, an exact
integer, a boolean, a 40-character revision, or a SHA-256 binding. A receipt contains no
free text, so it cannot carry prompts, model output, code, diffs, evidence bodies, paths,
repository identities, issue titles, user identity, secrets, or health data. Prohibited
field names and unknown fields fail closed before any value is read.

`observed_result.value` must be an exact integer. A boolean and a fractional number are
both rejected: a boolean cannot be compared against a baseline, and a float cannot be
compared exactly.

### Recommendation only

This contract compares the recommended choice against what it predicted. A receipt whose
`decision.selected_choice` is a declared choice other than
`recommendation.choice` is rejected as `OUTCOME_RECEIPT_CHOICE_NOT_RECOMMENDED`, and a
choice the card never declared is rejected as `OUTCOME_RECEIPT_CHOICE_UNDECLARED`. A
later contract can define expected results per alternative; until then, scoring an
alternative against the recommendation's own numbers would be a false comparison.

### Post-change observation

The recommendation is formed at `decision.revision`. The result appears only after the
change, so `observed_revision` is a separate field and is normally a later revision.
Every accepted verification fact must bind exactly to `observed_revision`. Accepted facts
from a mix of revisions, or from the decision revision alone, are rejected as
`OUTCOME_RECEIPT_VERIFICATION_STALE` rather than counted. Facts recorded as
`accepted: false` constrain nothing.

### Derived verdict

The verdict is not taken on trust. It is derived from the card's expected result and the
receipt's own facts, and the declared verdict must equal it:

| Facts | Verdict |
| --- | --- |
| No accepted verification fact at `observed_revision` | `inconclusive` |
| `decrease` and `value <= target` | `supported` |
| `decrease` and `target < value < baseline` | `partially-supported` |
| `decrease` and `value == baseline` | `unsupported` |
| `decrease` and `value > baseline` | `harmful` |
| `increase` | the exact inverse of `decrease` |
| `hold` and `value == target` | `supported` |
| `hold` and `value != target` | `harmful` |

A declared verdict that flatters the recommendation is rejected, not recorded.

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
