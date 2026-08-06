# Experiment: can interrogation produce Intake-to-Spec evidence?

## Status

One completed experiment with a negative result, recorded before any skill was
written. The proposal it tested was rejected in the form proposed. Nothing in
`aec/` changed.

## Why this was run

Eight of AEC's required evidence items are elicited rather than measured:

| Phase | Required evidence |
| --- | --- |
| Intake | `outcome-statement`, `owner-and-boundary` |
| Framing | `context-and-constraints`, `authority-and-risks`, `open-questions` |
| Spec | `behavior-and-interface-contract`, `non-goals`, `binary-acceptance-criteria` |

From `Build` onward, evidence is produced by running something. At these three
phases it exists only in an engineer's head. AEC can name which item is missing
and cannot help produce any of it.

An interview technique — sustained questioning that refuses vague answers —
was proposed as the producer, scoped to those three phases plus
`decision_context`. The open question was where such a procedure could live,
and what would tell it to stop.

## The proposal under test

> Terminate the interview when the closed validator returns no errors.

The appeal was that this replaces "relentless until the model gets bored" with
a machine-checkable exit, which is the only form this repository could host.

Its stated falsifier: *if the interview can reach a clean validator pass while
leaving a reader unable to say what would refute the recommendation, the
termination condition is falsified.*

## Method

Three `decision_context` payloads describing the same real fork were submitted
to the production validator, `aec.mentoring.validate_decision_context`, each
bound to the same revision.

- **A, grilled** — `tests/fixtures/decision-context/grilled.json`. Real
  tradeoffs, a falsifier naming an observation, a measure the repository
  already counts. It was authored from repository evidence, not elicited from
  a person; "grilled" names the quality bar it meets, not its provenance. That
  limit does not weaken the result below, which turns on B, but it is the
  reason the elicitation half stays untested.
- **B, hollow** — `tests/fixtures/decision-context/hollow.json`. Every field
  populated, every field restating its own name. Its falsifier is "Option A
  turns out to be the wrong choice." Its measure is `goodness`, in `points`.
- **C, contradictory** — B with `confidence` raised above its declared
  `evidence_quality` and a `direction` that disagrees with its own numbers.

## Result

```text
A grilled     -> VALID    (0 errors)
B hollow      -> VALID    (0 errors)
C contradic   -> REJECTED (2 errors)
    - recommendation.confidence exceeds the declared evidence quality
    - recommendation.expected_result.target contradicts .direction
```

**The proposal is falsified.** A hollow decision and an interrogated one are
indistinguishable to the contract. A clean validator pass is not evidence that
anyone thought.

The two rejections in C mark the boundary precisely: both rules compare two
values *already inside* the contract. That is the whole class of semantic check
available. No rule can reach prose, so no rule can reach quality.

### The hollowness is not caught later either

Before running this, the expected fallback was deferred falsification — that a
hollow `expected_result` becomes undeliverable at outcome time, because
`verify_outcome_receipt` requires the observed measure to equal the expected one
(`aec/outcomes.py:447`).

Reading the receipt contract, that fallback does not exist. `observed_result`
accepts any slug `measure`, any slug `unit`, and any canonical integer `value`
(`aec/outcomes.py:202-213`). For B, an author reporting `goodness = 10 points`
satisfies every check, and `_derived_verdict` (`aec/outcomes.py:267-285`)
compares `value >= target` and returns `supported`.

So a hollow decision produces a valid card, a valid receipt, and a `supported`
verdict, with no contract anywhere in the chain able to object. This step was
established by reading the receipt contract, not by executing a bound receipt.

Note also that `tests/fixtures/decision-context/example.json` — the
repository's own canonical fixture, in use since before this experiment — ships
tradeoffs reading "First choice quality tradeoff." and validates. The gap was
already visible in the fixtures; nobody had named it.

## What this does and does not condemn

It does not condemn the contract. `validate_decision_context` is a completeness
gate and it does that job: it forces a falsifier field to exist, which is the
forcing function `aec/mentoring.py:41-50` describes and defends. Requiring the
field is what makes its absence impossible. Requiring it to be *good* was never
in scope.

It does condemn one specific claim — that a validator pass could serve as an
automatic stopping rule for elicitation. That claim is now known false, and
this record exists so nobody re-derives it.

## Revised position

The finding inverts the argument for the interview rather than defeating it.
Content quality at Intake, Framing, and Spec is the one thing no contract in
this repository checks end to end. That makes interrogation more valuable, not
less — it is the only proposed mechanism aimed at the uncontracted half — and
it means the mechanism cannot be self-certifying.

Three constraints follow:

1. **The stopping rule is a person or an adversary, not a validator.** Whatever
   is built must end in a human accepting the artifact, or in a second pass
   whose job is to attack the falsifier rather than fill it. A validator pass
   may be a precondition for stopping. It may never be the reason.
2. **The producer must stay outside `aec/`.** This was true before the
   experiment, on trust-boundary grounds — an evaluator that authors the
   evidence it grades has no independent failure mode. The experiment sharpens
   it: since no contract can detect hollow evidence, AEC would have no way to
   catch itself producing it.
3. **Nothing generated enters a hash.** `compute_card_hash()` covers every
   public-card field. Interview output is evidence input, never card content.

## Not done

The elicitation half is untested. Whether questioning a person yields better
answers than that person writing unprompted was not measured here, and cannot
be measured without the person. This experiment tested only whether the
proposed stopping rule could tell the difference. It cannot.

## Reproduce

```bash
python3 -m unittest tests.test_elicitation_quality_is_uncontracted -v
```
