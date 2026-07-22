# Consumer Contract

AEC is reusable only when consumer-specific state stays in the consumer. AEC ships
no populated consumer profile; a consumer produces its own, shaped to the contract
validated by `tools/validate_foundation.py`.

The public state-provider boundary is the closed, versioned
[`consumer-state.schema.json`](../schemas/consumer-state.schema.json) contract. A caller
supplies one in-memory record plus the expected revision, expected environment, current
time, and AEC-owned procedure catalog. AEC performs no discovery or I/O at this seam.

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

## Reference example

Consumer profiles live in consumer repositories, not in AEC. A reference
profile follows the shape validated by `tools/validate_foundation.py`: fields
`schema_version`, `project`, `profile_version`, `workflow`,
`lifecycle_authority: consumer-owned`, `aec_mode: read-only-mentor`, and
`agent_adapters: [...]` (non-empty list). AEC ships no populated profile. A
consumer produces its own and the AEC contract validates it in-place.

The resolver consumes that same profile object directly under `consumer_profile`.
Consumers must not translate it to an alternate `identity` and `version` shape.
The project value is the hashed consumer-profile identity, and `profile_version` is
the hashed consumer-profile revision.

Consumers must not vendor private course sources, infer a general Blueprint license
from AEC's recorded direct permission, create agent-specific policy forks, or let AEC
write their lifecycle state. Consumers may discover AEC's exact installed Blueprint
skills through the canonical `.agents/skills/` root or its Claude symlinks; they must
not silently fork or adapt those files.

## Pure consumer adapter

```python
from aec.consumer import ConsumerStateRejection, resolve_consumer_state

result = resolve_consumer_state(
    caller_state,
    procedure_catalog,
    current_time="2026-01-01T00:30:00Z",
    expected_environment="test",
    expected_revision="0123456789abcdef0123456789abcdef01234567",
)
if isinstance(result, ConsumerStateRejection):
    rejection = result.to_dict()  # card is always null
else:
    card = result.to_dict()
```

The record contains only project-neutral task, revision, environment, workflow
position, evidence, capability, procedure, policy, blocker, provider, freshness, and
read-only effect facts. Its `effects` object must declare `executes=false` and
`mutates=false`. The adapter rejects malformed or unknown fields, stale freshness
windows, revision or environment mismatches, effectful declarations, and local private
paths before invoking the resolver.

An accepted record is translated into the existing normalized resolver request. The
resulting card contains Lane, Phase, the stage and nine-phase rail position, Gate,
rationale, required proof, Good, Finished, and one anti-example. Its transition request
is a draft with `authoritative=false`, `executes=false`, and `mutates=false`. AEC never
submits that draft.

## Conformance exit gate

The consumer integration is ready for a bounded pilot only when:

1. both real agent loaders discover the intended local procedure set exactly once;
2. the same input produces the same normalized AEC decision and hash;
3. missing, stale, malformed, duplicate, and effectful inputs fail closed;
4. one real issue traverses the nine phases with exact evidence; and
5. the authoritative record and visible project projection reconcile.

The consumer integration and ownership disposition for the first FedJobAdvisor
consumer is recorded in the
[FedJobAdvisor migration map](fedjobadvisor-migration-map.md). That map is evidence and
does not import its transport, Project, label, writer, or deployment implementation
into AEC.
