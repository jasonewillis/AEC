# Deterministic Resolver

Slice 2 uses one project-neutral procedure catalog for all nine lifecycle phases. Each
golden request proves the complete in-memory path from normalized facts and that catalog
to one immutable mentoring decision.

## Public interface

```python
from aec.resolver import ResolutionRejection, resolve

result = resolve(normalized_request, procedure_catalog)
if isinstance(result, ResolutionRejection):
    rejection = result.to_dict()
else:
    decision = result.to_dict()
```

The caller owns loading, discovery, normalization, and consumer policy. The resolver
accepts only in-memory objects. It does not read files, call GitHub, discover agent
skills, execute a procedure, or mutate lifecycle state. `to_dict()` returns a detached
copy so callers cannot mutate the stored canonical decision.

Both public inputs are validated before resolution. Normalized requests conform to
`resolution-request.schema.json`, and procedure catalogs conform to
`procedure-catalog.schema.json`. Catalogs require schema version `2.0.0`, one or more
fully shaped procedures with AEC-authored mentoring, and the currently supported
`ACCEPTANCE_EVIDENCE_INCOMPLETE` catalog reason code.

The procedure-catalog JSON Schema is the structural boundary. It rejects malformed
fields and exact duplicate objects. The standard-library Python validator is the
documented semantic superset: it also rejects different procedure objects that reuse
the same identity and revision pair, and it requires each revision to begin with its
procedure identity. Tests assert shared structural behavior and these additional
semantic rules separately; they do not claim full schema-validator parity where JSON
Schema cannot encode cross-field identity relationships.

Every normalized request identifies one `required_procedure` by identity and pinned
revision. `available_procedures` contains the complete caller-observed availability
set. The resolver sorts that set before including it in the hashed decision. It never
infers a required procedure from phase alone and never selects a same-phase substitute.

The normalized request uses schema version `2.0.0`. This version is intentionally a
breaking change from the first tracer: `consumer_profile` now uses the exact public
project-profile contract with `project` and `profile_version`. The resolver does not
accept or translate the former `identity` and `version` aliases. The embedded profile
keeps its own schema version `1.0.0`.

The output decision schema is deliberately versioned `4.0.0`. Every accepted decision,
including a blocked unavailable-procedure decision, contains exactly one primary
subject. A successful or evidence-needed decision contains a `primary_procedure` and a
null `primary_blocker`. A blocked unavailable-procedure decision contains a null
`primary_procedure` and a structured `primary_blocker` with the required procedure
identity and `SKILL_UNAVAILABLE` reason code.

Every accepted decision also contains two SHA-256 input bindings:

- `resolution_request` binds the complete validated request;
- `procedure_catalog` binds the complete validated procedure catalog.

Both bindings are part of the canonical decision payload and therefore part of the
decision hash. A material change to either accepted input changes its binding and the
decision hash, even when the selected mentoring card remains the same.
The primary subject is also part of the canonical payload, so changing a procedure or
blocker changes the decision hash. Recomputing that hash cannot legitimize a decision
with both primary subjects, neither primary subject, or a blocker for another required
procedure.

The JSON Schema enforces the closed blocker shape and exactly-one primary-subject
choice. Standard JSON Schema cannot compare two sibling string values, so the Python
validator is the documented semantic superset that requires `primary_blocker.identity`
to equal `required_procedure.identity`.

Collections whose order has no contract meaning are normalized before binding. These
are request procedure availability, blockers, capabilities, agent adapters, evidence,
catalog procedures, rationale principle identifiers, and required evidence. Reordering
only those collections leaves both canonical decision bytes and hash unchanged. Good,
Finished, and other presentation sequences remain ordered because their sequence can
carry meaning.

Every procedure supplies one closed `mentoring` record with a transferable lesson, an
explanation of why the phase gate exists, and a recognition heuristic. This content is
AEC-authored and remains available even when the gate is blocked.

The request may also include `decision_context` as null or a closed material-decision
brief at `schema_version: 2.0.0`. The brief contains two or three choices, five explicit
tradeoff dimensions per choice, the revision and evidence quality the decision was formed
from, one recommendation with its confidence, principal uncertainty, and expected
measurable result, evidence that would justify revisiting it, and the decision authority
owner. The resolver validates it against the request revision, binds it into the request
hash, and returns it as `decision_support`. The resolver does not invent choices, select
an authority, or execute the recommendation. See
[decision outcomes](decision-outcomes.md) for the local receipt that later compares that
recommendation with an observed result.

## Lifecycle golden catalog

The golden catalog contains one explicit procedure for Intake, Framing, Spec, Plan,
Build, Verify, Review, PR, and Deploy. Every procedure contains a phase-specific
rationale, evidence request, Good, Finished, one anti-example, and mentoring. Each golden request
selects its pinned procedure at Gate `Evidence needed` and maps to the lifecycle stage
defined by the workflow registry.

The catalog is the single runtime source of procedure facts. Golden requests contain
only normalized caller-owned facts and a pinned procedure reference. A contract test
requires exact phase coverage, one golden request per phase, stable canonical bytes,
and a fixed SHA-256 hash across two consecutive resolutions.
All nine requests share one caller-fact baseline. They vary only by phase, task,
workflow stage, and the required and available pinned procedure reference.

New phase procedures use only the neutral `aec-ticket-to-pr-*` identities documented
in the independently authored workflow contract. They add no private-course text or
lesson-to-policy mapping.

Good:

- exactly one phase, gate, and procedure are selected;
- evidence is bound to the requested revision and environment;
- source identities and revisions are copied into the hashed decision; and
- normalized request and catalog bindings are copied into the hashed decision; and
- the request, catalog, and stored decision remain unchanged.

Finished for the lifecycle goldens:

- all nine focused resolver cases pass twice with identical canonical bytes and hash;
- the expanded decision schema and validator accept the generated decision; and
- the complete Slice 1 foundation gate remains green.

Not wanted:

- Claude or Codex loaders;
- filesystem or network discovery inside the resolver;
- consumer repository, label, Project, or lifecycle-writer vocabulary; or
- a claim that Slice 2 is complete before the remaining phases and red canaries pass.

## Unavailable procedure tracer

If the required procedure is absent from `available_procedures`, the resolver returns
a hashed decision with Gate `Blocked`, `allowed=false`, and reason code
`SKILL_UNAVAILABLE`. `required_procedure` preserves the unavailable identity and
revision. `primary_procedure` is null because nothing was selected, while
`primary_blocker` repeats the required identity and the exact unavailable reason. The
decision requests `procedure-availability` evidence and includes the normalized
availability set in its hash. Adding an unrelated procedure therefore changes the
decision hash but cannot satisfy the requirement or become a silent substitute.

## Invalid input and tampered decision tracer

Missing fields, unknown fields, malformed nested values, and partial procedure
references return one immutable `ResolutionRejection`. Its schema has exactly
`accepted=false`, one exact rejection code, and an ordered non-empty error list.
Malformed requests use `RESOLUTION_REQUEST_INVALID`; malformed catalogs use
`PROCEDURE_CATALOG_INVALID`. Missing catalogs, non-list procedure collections,
malformed entries, and duplicate procedure references all fail before selection. No
accepted mentoring decision is returned, and untrusted public input data cannot leak
`KeyError`, `TypeError`, or `ValueError` from the public resolver.

This rejection is distinct from the hashed `SKILL_UNAVAILABLE` blocked decision.
A recomputed hash does not legitimize a tampered blocked decision: the decision
validator rejects `SKILL_UNAVAILABLE` whenever `allowed` is not false.

The current decision contract also enforces these cross-field invariants after hash
verification:

- `Ready` requires `allowed=true`, `ACCEPTANCE_EVIDENCE_COMPLETE`, and no required
  evidence;
- `Evidence needed` requires `allowed=true`, `ACCEPTANCE_EVIDENCE_INCOMPLETE`, and at
  least one required evidence kind;
- every Ready or Evidence needed decision has one exact primary procedure and no
  primary blocker; and
- `Blocked` currently permits only `SKILL_UNAVAILABLE`, `allowed=false`, no selected
  procedure, one exact primary blocker, and exactly `procedure-availability` evidence.

The completeness matrix runs all nine lifecycle goldens and the unavailable-procedure
tracer through the same invariant checks for rationale, evidence request, Good,
Finished, anti-example, and exactly one primary subject.

Reason codes are a closed schema enum. Callers cannot turn a valid decision green by
changing the gate or inventing an uppercase reason code and recomputing the hash.

## Verification

```bash
python3 -m unittest tests.test_resolver -v
python3 tools/validate_foundation.py
python3 -m unittest discover -s tests -p "test_*.py" -v
```
