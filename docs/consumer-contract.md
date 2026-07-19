# Consumer Contract

AEC is reusable only when consumer-specific state stays in the consumer. The first
profile is
[`config/projects/jwtravelscanner.json`](../config/projects/jwtravelscanner.json).

## AEC provides

- workflow and phase vocabulary;
- a deterministic resolution schema and hash contract;
- procedure-selection and evidence-policy contracts;
- course and upstream provenance;
- normalized mentoring-card data; and
- conformance fixtures and validators.

## The consumer provides

- repository instructions and a local procedure registry;
- current task, revision, environment, Lane, Phase, Gate, and evidence references;
- agent adapters that only read and render the AEC decision;
- an authenticated single lifecycle writer;
- Project or issue projection rules;
- branch protection, review, merge, deployment, and rollback controls; and
- telemetry destinations and retention policy.

## jwTravelScanner pilot

`jasonewillis/jwTravelScanner` is the first consumer, not a copy of AEC. Its adapter
must pin an AEC release, provide a versioned project and capability profile, and prove
that Claude and Codex resolve the same decision from the same fixture.

The consumer must not vendor private course sources, copy Blueprint skill text, create
agent-specific policy forks, or let AEC write its lifecycle state.

## Conformance exit gate

The consumer integration is ready for a bounded pilot only when:

1. both real agent loaders discover the intended local procedure set exactly once;
2. the same input produces the same normalized AEC decision and hash;
3. missing, stale, malformed, duplicate, and effectful inputs fail closed;
4. one real issue traverses the nine phases with exact evidence; and
5. the authoritative record and visible project projection reconcile.
