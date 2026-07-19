# Deterministic Resolver

Slice 2 begins with one Verify-phase tracer. It proves the complete in-memory path
from a normalized request and procedure catalog to one immutable mentoring decision.

## Public interface

```python
from aec.resolver import resolve

decision = resolve(normalized_request, procedure_catalog)
payload = decision.to_dict()
```

The caller owns loading, discovery, normalization, and consumer policy. The resolver
accepts only in-memory objects. It does not read files, call GitHub, discover agent
skills, execute a procedure, or mutate lifecycle state. `to_dict()` returns a detached
copy so callers cannot mutate the stored canonical decision.

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

## Verification

```bash
python3 -m unittest tests.test_resolver -v
python3 tools/validate_foundation.py
python3 -m unittest discover -s tests -p "test_*.py" -v
```
