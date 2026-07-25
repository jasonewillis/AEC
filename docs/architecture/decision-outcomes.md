# Decision Outcomes

AEC leads material decisions and then lets the consumer check whether that leadership
helped. The loop is proposal, card, selection, observed result, verdict. It is local,
deterministic, and read-only. Nothing in it uploads, stores, schedules, or mutates
anything.

```text
decision_context (2.0.0) -> resolver -> decision -> card (3.0.0) -> outcome record (1.0.0)
        proposal                brief   authority   decision_support        verdict
```

`decision_context 2.0.0` and `outcome-receipt 1.0.0` reached their current shape before
either was published, so both were completed in place rather than versioned again. The
public card is `3.0.0` because `card_hash` became a required field on a shape that had
already been published at `2.0.0`.

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
| `recommendation.expected_result` | One `measure` identity, a `unit` identity, a canonical integer `baseline` and `target`, a `direction`, and a human-readable `threshold`. Without exact numbers there is nothing to compare against later. |
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

## Canonical integer encoding

`baseline`, `target`, and the observed `value` are exact integers, and all three cross the
contract as canonical signed decimal strings such as `"0"`, `"7"`, and `"-7"`.

They are strings because a JSON number cannot carry the rule. JSON Schema draft 2020-12
defines `"type": "integer"` as any number with a zero fractional part, so `1.0` is a valid
integer to a schema validator while exact-type validation in Python rejects it. That gap
is a real disagreement between two validators of the same document, so both sides now
state one closed pattern instead:

```text
^(?:0|-?[1-9][0-9]*)$
```

No plus sign, no surrounding or embedded whitespace, no exponent, no decimal point, no
leading zero except `"0"` itself, and no negative zero. `"1.0"`, numeric `1.0`, `true`,
`"+1"`, `"01"`, `"-0"`, `" 1"`, and `"1e3"` all fail on both sides. A value is parsed with
`int()` only after that closed validation accepts it, so comparison never sees an
unvalidated number.

`high` confidence requires `direct-verified` evidence, and `medium` rejects `assumed`
evidence. That rule is what "insufficient current context" means here: an unsupported
confidence claim is rejected before any card is rendered.

## Public card integrity

Every rendered card carries `card_hash`, computed at render time over the complete card
with only `card_hash` itself excluded. One closed validator covers every required card
field and its internal agreement: the rail position must match the rendered phase, the
draft transition must request the rendered gate and stay non-authoritative, and the
decision context must bind the card's own revision. The validator then recomputes
`card_hash` from the card's bytes.

A card that is missing, malformed, incomplete, internally inconsistent, or edited after
rendering is rejected as `OUTCOME_RECEIPT_CARD_INVALID`, so no decision binding, observed
result, or verdict is read from a card that failed.

`card_hash` alone is local structural and tamper integrity, not proof of origin. It
detects a card that was truncated, edited, or reassembled, but anyone who can rewrite a
card can also recompute the hash. AEC adds no signing keys, secrets, trusted ledger, or
trusted storage boundary, so it makes no claim about who authored a local record.

## Record consistency and exact snapshot binding

A recomputed hash proves nothing on its own, because whoever changed the card can
recompute it. So an outcome record carries the complete normalized decision that produced
the card:

```json
{"card": {...}, "decision": {...}, "receipt": {...}}
```

Verification checks the record's internal consistency before it reads a single receipt
fact:

1. the decision is validated by the independent decision validator, the same one the
   foundation gate runs, so a fabricated decision must satisfy the entire closed decision
   contract, including gate, reason code, procedure, and evidence coherence;
2. `compute_resolution_hash` is recomputed over the decision and must equal the
   `resolution_hash` the decision declares;
3. the card must equal `project_card(decision)` exactly, field for field, including
   `card_hash`.

`project_card` is the single deterministic projection. The consumer renderer calls it to
render a card and the outcome verifier calls it to reproduce one, so there is one
implementation and no second opinion about what a decision renders. It reads an already
resolved decision and holds no resolver, policy, or lifecycle authority.

These checks prove that the carried card is the exact projection of the carried decision
snapshot. They do not prove that a trusted actor or process created either value. A
coherent local record can be self-authored and have all of its hashes recomputed. Trusted
origin would require an external signature, ledger, or storage boundary, which is outside
AEC's local, read-only, non-authoritative contract.

| Failure | Code |
| --- | --- |
| Record shape, or a value that is not exact JSON | `OUTCOME_RECORD_INVALID` |
| Decision rejected by the decision contract, or a hash that does not recompute | `OUTCOME_RECORD_DECISION_INVALID` |
| Card is not the exact projection of its own decision | `OUTCOME_RECORD_CARD_NOT_PROJECTED` |

Editing the card and recomputing `card_hash` now fails, because the card no longer equals
the projection. Editing the decision and recomputing `resolution_hash` also fails, because
an edited decision has to survive the decision contract. Editing both to agree still fails
unless the result is a complete, coherent decision that genuinely projects to that card.

The record stays local. It is never uploaded, aggregated remotely, or fed back into
policy, and the evaluator's report carries counts, codes, and indexes only, never the
decision's content.

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

Every receipt value is a closed enumeration, a lowercase hyphenated identity, a canonical
integer string, a boolean, a 40-character revision, or a SHA-256 binding. A receipt
contains no free text, so it cannot carry prompts, model output, code, diffs, evidence
bodies, paths, repository identities, issue titles, user identity, secrets, or health
data. Prohibited field names and unknown fields fail closed before any value is read.

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
