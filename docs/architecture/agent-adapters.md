# Agent Adapter Parity

AEC adapters translate real runtime loader evidence into one normalized,
metadata-only receipt. They do not ask Claude or Codex to decide policy. Both agents
receive the same caller-owned request and the same AEC procedure catalog, so the
deterministic resolver remains the only mentoring-decision authority.

## Proof boundary

Codex provides a model-free `debug prompt-input` JSON view. A preflight identifies any
same-name user skill outside the project root. The proof reruns Codex with exact-path,
session-only `skills.config` exclusions for those conflicts, without changing user or
project configuration. The final loader evidence must expose each of the seven pinned
project skills exactly once, and the receipt reports the number of suppressed conflicts.

Claude provides loader metadata in its debug log. The proof runner starts the real CLI
in a pseudo-terminal, waits for the project-loader summary, and stops it before any
prompt is submitted. The run must report seven project skills, zero user or managed
skills, zero plugin skills, and zero duplicate or skipped entries. The existing
Blueprint installation validator separately proves that `.claude/skills` contains the
seven exact symlinks to the hashed canonical files.

The two receipts must bind:

- the runtime identity and version;
- exactly seven discovered project skills;
- the canonical Blueprint manifest hash;
- the normalized resolution-request hash; and
- the same authoritative AEC decision hash.

Every receipt also declares `executes: false` and `mutates: false`. The receipt is
evidence that two adapters rendered the same recommendation, never execution authority.

Run the live local proof:

```bash
python3 tools/prove_agent_adapter_parity.py
```

The proof output contains metadata only. It contains no course text, skill content,
prompt content, consumer secrets, or model response.

## Fail-closed behavior

Missing, duplicated, stale, malformed, or mismatched loader evidence returns one exact
rejection code and no decision hash. If AEC is unavailable, the adapter returns
`AEC_UNAVAILABLE` with `status: degraded`, `authoritative: false`, and no request,
manifest, or decision hash. Degraded mode never reuses a cached decision and never
authorizes execution.
