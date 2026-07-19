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
- a reason and course-guidance identifier;
- required proof;
- a good example;
- the exact finished condition; and
- an anti-example that must be rejected.

The earliest unmet gate controls the recommendation. Supporting procedures are allowed,
but later work cannot hide an earlier gap.

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
