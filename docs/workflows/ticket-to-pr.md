# Ticket-to-PR Workflow

The canonical registry is
[`config/workflows/ticket-to-pr.json`](../../config/workflows/ticket-to-pr.json).
This workflow is independently authored and informed by the sequencing discipline in
the MIT-licensed `owainlewis/workflows` project.

| Stage | Phase | Exit question |
| --- | --- | --- |
| Understand | Intake | Is there one observable outcome with an owner and boundary? |
| Understand | Framing | Are context, constraints, risks, authority, and unknowns explicit? |
| Design | Spec | Are behavior, interfaces, non-goals, and binary acceptance criteria resolved? |
| Design | Plan | Are vertical slices, dependencies, ownership, proof, and stop rules defined? |
| Execute | Build | Does the smallest coherent implementation make an honest red case green? |
| Execute | Verify | Does exact-revision evidence prove the expected result at the right boundary? |
| Assure & Release | Review | Has an independent reviewer checked the exact base and head against the spec? |
| Assure & Release | PR | Are findings resolved and required checks current on the merge candidate? |
| Assure & Release | Deploy | Is the intended revision live, observed, and recoverable? |

RESOLVE-004 assigns the new phase procedures stable `aec-ticket-to-pr-*` principle
identities derived only from these independently authored exit contracts. These
identities do not identify or map to private course lessons. Verify retains its existing
tracer contract until the dedicated course-boundary work replaces it.

## Gate decision

Each phase resolves exactly one Gate. Precedence is:

```text
Blocked > Needs review > Evidence needed > Ready
```

- `Blocked` means a concrete dependency, context, contract, authority, or environment
  failure prevents progress.
- `Needs review` means the required independent decision is absent or stale.
- `Evidence needed` means the work may exist but the accepted proof is incomplete.
- `Ready` means the phase contract is satisfied for the exact revision and environment.

Moving a card or applying a label does not create this decision. The consumer writer
accepts typed evidence and projects the resulting state.

## Merge behavior

Automatic merge is safe only when Expected Results are binary, every required gate is
green on the exact candidate revision, independent review is current, no blocking state
exists, and branch protection enforces those facts. AEC may explain readiness but cannot
merge or grant authority.
