# Architecture

AEC separates reusable policy from project-owned authority.

```text
Course principles       Upstream capability references
        |                            |
        +------> AEC foundation <----+
                        |
                        v
Consumer record -> deterministic resolver -> mentoring card -> host agent
       ^                                                       |
       |                                                       v
single consumer writer <- typed observable evidence <- authorized procedure
```

## Ownership

| Layer | Owns | Must not own |
| --- | --- | --- |
| AEC foundation | Lifecycle vocabulary, resolver schema, procedure selection rules, evidence requirements, presentation contract | Consumer state, credentials, execution, merge, deploy |
| AEC mentor | Current position, earliest unmet gate, one procedure recommendation, rationale, required evidence | Procedure invocation or state transition |
| Consumer adapter | Reading local records and rendering the normalized card | New policy or a second resolver |
| Consumer writer | Authenticated, compare-and-swap lifecycle mutation and audit trail | Mentoring or task execution |
| Host agent | Separately authorized procedure execution and evidence production | Implicit lifecycle or release authority |

## Deterministic decision

The normalized input conforms to
[`resolution-request.schema.json`](../../schemas/resolution-request.schema.json).
The procedure registry conforms to
[`procedure-catalog.schema.json`](../../schemas/procedure-catalog.schema.json).
The schema is the portable structural contract. The Python catalog validator is an
intentional semantic superset because JSON Schema cannot express uniqueness by a
compound identity and revision key.
Malformed input returns the non-decision shape in
[`resolution-rejection.schema.json`](../../schemas/resolution-rejection.schema.json).
Accepted resolver output conforms to
[`resolution-decision.schema.json`](../../schemas/resolution-decision.schema.json).
Its `resolution_hash` is SHA-256 over UTF-8 JSON with sorted keys and compact
separators, excluding only `resolution_hash`. This binds the recommendation to the
task, project profile, capability profile, policy, workflow position, revision,
environment, gate, and evidence request.

The decision always contains `executes=false` and `mutates=false`. Any other value is
a contract failure.

## Failure behavior

AEC fails closed when input is missing, stale, malformed, unpinned, inconsistent, or
effectful. Malformed normalized requests return `RESOLUTION_REQUEST_INVALID`, while
malformed procedure catalogs return `PROCEDURE_CATALOG_INVALID`. Both include an
ordered error list and `accepted=false`, and neither returns a decision. A trusted
request and catalog whose pinned procedure is unavailable return a hashed blocked decision
instead of silently substituting an upstream role or guessing from chat. A blocker
must name a concrete reason and the evidence needed to resolve it.
