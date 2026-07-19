# Deterministic Resolver

Slice 2 begins with one Verify-phase tracer. It proves the complete in-memory path
from a normalized request and procedure catalog to one immutable mentoring decision.

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
`procedure-catalog.schema.json`. Catalogs require schema version `1.0.0`, one or more
fully shaped procedures, and unique procedure identity and revision pairs.

Every normalized request identifies one `required_procedure` by identity and pinned
revision. `available_procedures` contains the complete caller-observed availability
set. The resolver sorts that set before including it in the hashed decision. It never
infers a required procedure from phase alone and never selects a same-phase substitute.

The normalized request uses schema version `2.0.0`. This version is intentionally a
breaking change from the first tracer: `consumer_profile` now uses the exact public
project-profile contract with `project` and `profile_version`. The resolver does not
accept or translate the former `identity` and `version` aliases. The embedded profile
keeps its own schema version `1.0.0`, and the output decision schema stays at `1.0.0`
because its field structure did not change.

## First tracer

The golden Verify request selects `verify-evidence` at Gate `Evidence needed`. The
decision includes structured rationale, requested evidence, Good, Finished, one
anti-example, all source revisions, and a SHA-256 hash over canonical JSON bytes.
Running the same request twice must produce identical bytes and hash.

Good:

- exactly one phase, gate, and procedure are selected;
- evidence is bound to the requested revision and environment;
- source identities and revisions are copied into the hashed decision; and
- the request, catalog, and stored decision remain unchanged.

Finished for this tracer:

- the focused resolver test passes twice with identical canonical bytes and hash;
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
revision, while `primary_procedure` is null because nothing was selected. The decision
requests `procedure-availability` evidence and includes the normalized availability
set in its hash. Adding an unrelated procedure therefore changes the decision hash but
cannot satisfy the requirement or become a silent substitute.

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
  least one required evidence kind; and
- `Blocked` currently permits only `SKILL_UNAVAILABLE`, `allowed=false`, no selected
  procedure, and exactly `procedure-availability` evidence.

Reason codes are a closed schema enum. Callers cannot turn a valid decision green by
changing the gate or inventing an uppercase reason code and recomputing the hash.

## Verification

```bash
python3 -m unittest tests.test_resolver -v
python3 tools/validate_foundation.py
python3 -m unittest discover -s tests -p "test_*.py" -v
```
