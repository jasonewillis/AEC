# Operating Model

AEC is the mentoring interface around a material engineering task. The same normalized
decision must produce equivalent guidance for Claude and Codex.

## Position first

Every card begins with Lane, Phase, stage position, and the full rail.

```text
Lane: TEST | [Phase: Verify] | EXECUTE - Verify (2 of 2)
[ Understand complete ] -> [ Design complete ] -> [ Execute active ] -> [ Assure & Release pending ]
```

Color may supplement the card, but text and markers carry the meaning.

## Card contract

A complete card reports:

- current Lane, Stage, Phase, ordinal, and rail;
- Gate and a concrete blocker when present;
- one primary local procedure and whether it is available;
- a reason and independently authored AEC principle identity;
- required proof;
- a good example;
- the exact finished condition; and
- an anti-example that must be rejected;
- a transferable lesson, why the current gate exists, and a recognition heuristic;
  and
- either no decision support for a routine step or one validated material-decision
  brief.

The earliest unmet gate controls the recommendation. Supporting procedures are allowed,
but later work cannot hide an earlier gap.

## Material decisions

AEC should make the user a better agentic engineer, not merely narrate task status.
When different reasonable choices materially change quality, risk, reversibility,
maintainability, scope, or authority, the consumer may provide a closed decision
context. AEC validates and renders:

- a clear decision question;
- two or three bounded choices;
- the five required tradeoff dimensions for each choice;
- one recommendation and its reason;
- evidence that would change the recommendation; and
- the actor who owns the decision.

Routine execution does not need a menu. If the next action is already determined by an
accepted contract, the decision context is null. This keeps mentoring focused on real
judgment instead of forcing ceremonial choices into every task.

## Evidence and movement

Observable systems produce proof. The consumer-owned writer validates evidence and owns
movement. AEC reads the resulting state and explains it. The host agent may execute a
procedure only through separate task authority.

Issue closure, approval, merge, a reachable URL, a label, or agent confidence is not
sufficient proof by itself. Evidence must name the exact revision and environment when
the claim depends on either.

## Good

- One current phase, one gate, one primary procedure, and one proof gap are visible.
- Claude and Codex resolve the same normalized decision from the same record.
- Failed, stale, skipped, missing, or wrong-revision evidence remains visible.
- User-facing work includes real browser, network, console, accessibility, data, and
  visual checks where applicable.
- Material forks teach the tradeoff, identify the decision owner, and say what evidence
  would change the recommendation.

## Finished

A deployable task is finished only when every required phase has accepted evidence, the
consumer ledger and its projection agree, no pending or failed transition remains, and
Deploy binds the intended revision to production proof. Code completion, tests, review,
merge, or issue closure alone is not finished.

## Not wanted

- Decorative progress inferred from chat or labels
- AEC executing its recommendation
- A second lifecycle ledger
- Duplicate agent-specific policy forks
- Copied Blueprint or course content presented as local policy
- Multiple agents mutating the same branch, record, project item, or release
- Status-only mentoring that reports a phase without teaching why it matters
- Exhaustive choice menus for routine or already-authorized work
- AEC making, executing, or silently escalating a consumer-owned decision
