# Coaching Interaction

## Status

This document defines the target interaction for a trustworthy Agentic Engineering
Coach. It is a delivery contract, not a claim that every box is implemented.

AEC already provides deterministic resolution, mentoring-card data, material-decision
support, local outcome evaluation, and fail-closed consumer validation. The remaining
productization work is called out in the gap map below.

## Successful workflow

```text
+============================================================================+
|                    AGENTIC ENGINEERING COACH WORKFLOW                      |
+============================================================================+

     CONSUMING PROJECT                                      AEC FRAMEWORK
  GitHub issue, local repo,                              Read-only, deterministic,
  task authority, evidence                              non-authoritative mentor
             |                                                     |
             v                                                     |
+---------------------------+                                      |
| 1. START THE TASK         |                                      |
|                           |                                      |
| - Read project rules      |                                      |
| - Confirm task authority  |                                      |
| - Inspect current state   |                                      |
| - Identify task identity  |                                      |
+-------------+-------------+                                      |
              |                                                    |
              v                                                    |
+---------------------------+       validate pin and contract       |
| 2. AEC PREFLIGHT          +-------------------------------------> |
|                           |                                      v
| - AEC revision is pinned  |                         +-------------------------+
| - Consumer profile exists |                         | PIN AND CONTRACT VALID? |
| - Checkout is clean       |                         +------------+------------+
| - Both card paths work    |                                      |
+---------------------------+                          +-----------+-----------+
                                                     NO                       YES
                                                      |                        |
                                                      v                        v
                                           +--------------------+  +----------------------+
                                           | [AEC] STOP         |  | 3. BUILD CURRENT     |
                                           |                    |  |    TASK STATE        |
                                           | Pin or contract    |  |                      |
                                           | mismatch detected |  | - Lane and Phase     |
                                           | No advice trusted |  | - Exact revision     |
                                           +--------------------+  | - Environment        |
                                                                   | - Evidence           |
                                                                   | - Active blockers    |
                                                                   | - Freshness window   |
                                                                   +----------+-----------+
                                                                              |
                                                                              v
                                                                   +----------------------+
                                                                   | STATE VALID?         |
                                                                   +----------+-----------+
                                                                              |
                                                              +---------------+--------------+
                                                             NO                             YES
                                                              |                               |
                                                              v                               v
                                                   +--------------------+        +-----------------------+
                                                   | [AEC] BLOCKED      |        | 4. RESOLVE POSITION   |
                                                   |                    |        |                       |
                                                   | Name the exact     |        | Earliest unmet gate   |
                                                   | missing, stale, or |        | controls the advice   |
                                                   | invalid fact       |        +-----------+-----------+
                                                   | Return no card     |                    |
                                                   +--------------------+                    v
                                                                                +-----------------------+
                                                                                | UNDERSTAND            |
                                                                                | [Intake] [Framing]    |
                                                                                |          |            |
                                                                                | DESIGN   v            |
                                                                                | [Spec] [Plan]         |
                                                                                |          |            |
                                                                                | EXECUTE  v            |
                                                                                | [Build] [Verify]      |
                                                                                |          |            |
                                                                                | ASSURE & RELEASE      |
                                                                                | [Review] [PR] [Deploy]|
                                                                                +-----------+-----------+
                                                                                            |
                                                                                            v
                                                                                +-----------------------+
                                                                                | MATERIAL DECISION?    |
                                                                                +-----------+-----------+
                                                                                            |
                                                                         +------------------+------------------+
                                                                        NO                                    YES
                                                                         |                                      |
                                                                         v                                      v
                                                          +--------------------------+           +--------------------------+
                                                          | ROUTINE GUIDANCE         |           | DECISION GUIDANCE        |
                                                          |                          |           |                          |
                                                          | No artificial choices    |           | Present 2-3 real options |
                                                          | Next procedure           |           | Compare each option on:  |
                                                          | Required evidence        |           | quality, risk,           |
                                                          | Finished condition       |           | reversibility,           |
                                                          | Recognition heuristic    |           | maintainability, scope   |
                                                          +------------+-------------+           |                          |
                                                                       |                         | Recommend one option     |
                                                                       |                         | State confidence         |
                                                                       |                         | State uncertainty        |
                                                                       |                         | State expected result    |
                                                                       |                         | Name decision owner      |
                                                                       |                         | Say when to reconsider   |
                                                                       |                         +------------+-------------+
                                                                       |                                      |
                                                                       +------------------+-------------------+
                                                                                          |
                                                                                          v
                                                                      +------------------------------------------+
                                                                      | 5. RENDER HUMAN COACHING                 |
                                                                      |                                          |
                                                                      | [AEC: Project Guidance] action and proof |
                                                                      | [AEC: Mentoring] lesson and recognition  |
                                                                      | Machine JSON only by explicit request    |
                                                                      +-------------------+----------------------+
                                                                                          |
                                                                                          v
+---------------------------+       project executes       +-----------------------------+
| 6. CONSUMER DECIDES       +----------------------------->| 7. PERFORM THE WORK         |
|                           |                              |                             |
| - Accept recommendation   |                              | - Implement                 |
| - Choose another option   |                              | - Test                      |
| - Escalate to owner       |                              | - Review                    |
|                           |                              | - Collect evidence          |
| AEC never decides or acts |                              | - Update project state      |
+---------------------------+                              +--------------+--------------+
                                                                          |
                                                                          v
                                                               +-------------------------+
                                                               | CANDIDATE HEAD CHANGED? |
                                                               +------------+------------+
                                                                            |
                                                               +------------+------------+
                                                              YES                       NO
                                                               |                         |
                                                               v                         |
                                                    +----------------------+              |
                                                    | Refresh task state   |              |
                                                    | Re-run checkpoint    |              |
                                                    | Re-run affected proof|              |
                                                    +----------+-----------+              |
                                                               |                          |
                                                               +------------+-------------+
                                                                            |
                                                                            v
                                                               +-------------------------+
                                                               | REQUIRED EVIDENCE       |
                                                               | ACCEPTED?               |
                                                               +------------+------------+
                                                                            |
                                                               +------------+------------+
                                                              NO                       YES
                                                               |                         |
                                                               v                         v
                                                    +----------------------+   +----------------------+
                                                    | [AEC] REMAIN AT GATE |   | ADVANCE ONE PHASE    |
                                                    |                      |   |                      |
                                                    | Explain missing or   |   | Never skip phases    |
                                                    | rejected evidence    |   | Re-render checkpoint |
                                                    +----------------------+   +----------+-----------+
                                                                                         |
                                                                                         v
                                                                          +-------------------------+
                                                                          | DEPLOY PROVEN?          |
                                                                          +------------+------------+
                                                                                       |
                                                                          +------------+------------+
                                                                         NO                       YES
                                                                          |                         |
                                                                          v                         v
                                                               +----------------------+  +----------------------+
                                                               | Continue lifecycle   |  | 8. TASK FINISHED     |
                                                               | and evidence loop    |  |                      |
                                                               +----------------------+  | Exact revision is    |
                                                                                         | deployed and proven   |
                                                                                         +----------+-----------+
                                                                                                    |
                                                                                                    v
                                                                                         +----------------------+
                                                                                         | 9. OUTCOME RECEIPT   |
                                                                                         |                      |
                                                                                         | Expected vs observed |
                                                                                         | Coaching transfer    |
                                                                                         | Engineering burden   |
                                                                                         | Derived verdict      |
                                                                                         +----------+-----------+
                                                                                                    |
                                                                                                    v
                                                                                         +----------------------+
                                                                                         | 10. LOCAL EVALUATION |
                                                                                         |                      |
                                                                                         | Project impact       |
                                                                                         | Coaching value       |
                                                                                         | No causal claim      |
                                                                                         | No policy mutation   |
                                                                                         +----------------------+
```

Steps 1 through 4 and steps 6 through 10 describe behavior AEC provides today. The
human renderer for step 5 is also shipped. Consumer prompt-hook adoption remains a
separate boundary: the consumer must provide revision-bound state and configure its
agent harness to invoke the renderer. Skill discovery alone is not interaction parity.

## Human interaction

Normal use must render both project guidance and student mentoring from the same
validated card.

```text
+-------------------------------------+  +-------------------------------------+
| [AEC: Project Guidance]             |  | [AEC: Mentoring]                    |
|                                     |  |                                     |
| Position and workflow rail          |  | Transferable concept                |
| Earliest unmet gate                 |  | Why the gate exists                 |
| Recommended next procedure          |  | Recognition heuristic               |
| Required proof                      |  | Material tradeoff                   |
| Exact finished condition            |  | One optional reflection question    |
| Consumer authority boundary*        |  | Learner-appropriate explanation     |
+------------------+------------------+  +------------------+------------------+
                   |                                        |
                   +------------------+---------------------+
                                      |
                                      v
                         One deterministic coaching response
```

Every row above is card-derived and always rendered, with one exception: the consumer
authority boundary is invariant text, so it is orientation chrome and appears only on
the three orienting triggers (see the human-render interaction contract below). The
lesson, the reason the gate exists, and the recognition heuristic are never chrome and
are never suppressed.

The project block is concise and actionable. The mentor block teaches the engineering
judgment behind it. A learner profile may change explanation depth or suppress repeated
lessons, but it must never change the decision hash, gate, procedure, recommendation,
evidence requirement, or authority owner.

**Design boundary: `[AEC: Project Guidance]` does not derive or summarize project
detail.** The word "Project" distinguishes workflow-level coaching (this block) from
student-level mentoring (the `[AEC: Mentoring]` block) — it is not a promise that AEC
computes or contextualizes anything about the consumer's project. AEC is a generic
ticket-to-PR mentor: the validated card the resolver produces contains only
project-invariant inputs (task identity, phase/stage/rail position, lane, evidence
entries, blocker entries), and every card has the same shape across every project. The
rendered block may echo back a `TASK` line and a `REVISION` line, but those are opaque
identity strings the consumer explicitly supplied to the renderer, not project detail
AEC derived — AEC never computes a branch summary, a PR number, test-count context, or
a commit summary on its own. A consumer that wants that kind of derived project context
alongside the coaching card should render its own project banner; AEC's card is not the
place for it.

At a material fork, the same response adds a decision block:

```text
[AEC: Decision]
    |
    +--> Option 1: five tradeoff dimensions
    |
    +--> Option 2: five tradeoff dimensions
    |
    +--> Option 3: five tradeoff dimensions, when genuinely useful
    |
    +--> Recommendation
           |
           +--> confidence
           +--> principal uncertainty
           +--> expected measurable result
           +--> evidence that would change the recommendation
           +--> real decision owner
```

Routine work must not manufacture a menu. Its `decision_support` remains null.

**Design boundary: `[AEC: Decision]` renders `decision_support`, a validated pass-through
of the consumer-supplied `decision_context`, not an AEC-derived recommendation.** The
options, tradeoff dimensions, confidence, principal uncertainty, expected measurable
result, and decision owner shown in the block above are the consumer's own submitted
content, checked for completeness and republished bound to the card hash — AEC does not
select, score, or rank among the choices. See
[consumer-contract.md](consumer-contract.md#the-consumer-provides) for the full
validated-pass-through contract.

## Card language

Card text must read clearly for engineers of mixed experience levels and for
non-native English readers. This section is a **card language style** guide, not a
copy rewrite: it establishes the principles a plain-language rendering must
follow. It does not change any canonical `mentoring` string in
`config/procedures/ticket-to-pr.json` today, and it does not itself add a `plain`
variant field. Applying these principles to the actual card copy is tracked
separately in issue #89.

Principles for any plain-language rendering of a card:

- **Short sentences.** One idea per sentence. Prefer two short sentences over one
  sentence joined with "which" or "that" carrying a second claim.
- **Common vocabulary.** Prefer everyday words over Latinate or academic ones
  where a common word means the same thing (`use` over `utilize`, `show` over
  `demonstrate`).
- **Direct voice.** Prefer concrete verbs and active voice over nominalizations
  ("verification is evidence" reads harder than "you verify by proving").
- **No unexplained jargon.** Domain terms (`base`, `head`, `card_hash`, `pin`)
  are either avoided or expanded on first use in the sentence that introduces
  them. A term is not "explained" by using it again in a later sentence.
- **No idioms or metaphors that do not translate.** Avoid phrases that only
  make sense to a native English reader (for example "in the weeds", "boil the
  ocean"). Say the literal thing instead.
- **One worked example per concept**, where practical, so the abstraction has
  a concrete anchor rather than standing alone.

These principles apply to all human-visible card copy. That copy is drawn
from several public-card fields, including `mentoring`, `anti_example`,
`good`, and `finished`; the renderer also presents rationale and required
proof. Plain-language work must preserve the meaning of the separately
structured policy and authority facts rather than infer or alter them.

There is no separate, unhashed plain-language surface today.
`compute_card_hash()` hashes every public-card field except `card_hash`
itself (`aec/cards.py:120-133`), so editing any hashed copy recomputes the
hash as an ordinary content revision. The rewrite in issue #89 covers six
existing hashed fields. The additive proposal in issue #53 requires an
explicit schema and hash contract before implementation. Neither issue is
implemented by this style guidance. Register and plain-language rendering
remain related to the "Learner adaptation" row in the Gap map below.

## Intended invocation

The target consumer experience is one canonical local command used by people, Claude,
Codex, and future agents:

```text
aec doctor
aec coach checkpoint --task healthrag#33 --phase Framing
aec coach decision --task healthrag#33 --context tmp/decision.json
aec coach verify --task healthrag#33 --evidence tmp/proof.json
aec coach outcome --task healthrag#33 --receipt tmp/outcome.json
```

The complete command family above remains target state. AEC currently ships `doctor`, the
bounded AEC-self `state` and `checkpoint` commands, and a consumer-capable
`UserPromptSubmit` hook renderer:

```text
# Preflight, run from any pinned checkout before trusting a card:
python3 -m tools.aec_coach doctor

# AEC repository self-coaching only:
python3 -m tools.aec_coach state --task aec#81 --phase Framing --lane INFRA
python3 -m tools.aec_coach checkpoint tmp/aec-state.json

# Consumer project, after its state producer writes tmp/aec-state.json and its
# adapter adds "aec_trigger" to the native JSON payload per interaction:
python3 .local/aec/tools/aec_prompt_hook.py \
  --state tmp/aec-state.json \
  --project-root "$CLAUDE_PROJECT_DIR" \
  --environment "$AEC_ENVIRONMENT"
```

The pure adapter remains the policy seam. A consumer-owned launcher may read safe Git
facts and construct ignored local state, but facts that cannot be proven must be supplied
explicitly or rejected. The prompt hook reads the Claude-compatible event from standard
input, discards prompt text, and binds the state to the consumer repository's exact HEAD.
The native hook payload produces the compact routine indicator. A consumer-owned adapter
selects `status-request`, `task-intake`, `phase-transition`, `gate-transition`,
`gate-failure`, `review-finding`, `pr-created`, or `deploy-observe` and adds that closed
value as `aec_trigger` to the per-interaction JSON payload for a full card. The AEC hook
does not infer a trigger or lifecycle phase from prompt prose. A static command argument
is intentionally insufficient because it would choose full or compact output for every
prompt. Structured output remains explicit through
`aec_coach checkpoint --format json`.

`doctor` exits `0` and prints one `PIN`, one `CONTRACT`, one `ROUTINE`, and one `MATERIAL`
line, or exits nonzero and prints no report at all. It resolves both probes through
`tools/validate_consumer_connection.py` rather than constructing its own, and reads the
released contract versions from `config/release/aec-release.json`. It only resolves and
reports: it registers nothing, writes nothing, and mutates nothing.

The copyable install kit for a new consumer is `docs/consumer-kit/register-hook.md`
(pin, hook registration, trigger selection, verification) and
`docs/consumer-kit/state_producer_template.py` (a state producer bound to the consumer's
own `HEAD` and profile). Both are copied into the consumer repository, not invoked from
AEC, because the state file is a claim about the consumer's tree.

The consumer owns hook registration, `AEC_STATE_PATH`, `AEC_ENVIRONMENT`, and production
of the state file. Missing or rejected state emits `[AEC: Integration Blocked]` without
a workflow rail. AEC ships the framework half only: installing this revision does not
register a consumer hook or create consumer state. Skill discovery without consumer
invocation is not coaching interaction.

### Human-render interaction contract

`aec.human_render.HUMAN_RENDER_CONTRACT_VERSION` is `1.5.0`. It retains the stable
`[AEC: Project Guidance]` and `[AEC: Mentoring]` headings while adding a terminal-safe
visual hierarchy. Full cards use compact labels, wrapped context, and only the evidence
categories the card actually claims or requires. Major and supporting rules, the stage
header, the marker legend, and the read-only authority statement are orientation chrome:
rendered for `task-intake`, `status-request`, and `phase-transition`, and suppressed for
the other five full-card triggers. The rail, guidance, evidence, finished
condition, mentoring, and authority boundary still come from one validated card and
exact-bound consumer snapshot. `routine-progress` still emits one deterministic compact
line. The renderer never remembers a prior phase or selects a lifecycle transition; the
consumer adapter owns per-interaction trigger selection, payload augmentation, and state
production.

At `task-intake` only, the prompt hook appends an unhashed agent-guidance contract after
the validated human card. It requires a bounded task brief and tells the host agent not
to manufacture options for routine work. At a material fork it requires 2-3 choices,
the recommendation first, explicit Pros and Cons, the existing five tradeoff dimensions,
and the existing evidence and ownership fields. This instruction does not derive facts,
select an option, validate prose quality, or change `decision_context`; absent consumer
phase or milestone facts remain unverified.

`1.3.0` adds one purely presentational refinement to the rail: stage headers
are bracketed across their exact phase span (`├─── UNDERSTAND ───┤`) instead of
a bare centred label, so a stage's scope is explicit on the same header line.
The change is additive to the header line only; markers, evidence, guidance,
and mentoring sections are unchanged.

`1.4.0` widens `TEXT_WIDTH` from 96 to 104 columns. The default nine-phase
rail's phase line landed exactly at the prior 96-column ceiling with zero
headroom, so a one-character phase display-name change (for example,
lengthening `Deploy/Observe`) could overflow and raise `RenderFailure`. The
wider ceiling restores headroom without changing any other rendering
behavior; all other sections keep wrapping at the same relative width.

`1.5.0` makes invariant chrome conditional rather than unconditional, and
removes three strict duplicates. Half of every card previously carried no
phase-specific information, and one card named its phase five times. No card
field, resolver output, or hashed value changes: `card_hash` and
`resolution_hash` are byte-identical at all nine phases.

- Orientation chrome (heading and section rules, stage header, marker legend,
  and the `AUTHORITY` read-only statement) renders for the three triggers where
  the reader cannot be assumed to hold the frame — `task-intake`,
  `status-request`, `phase-transition` — and is suppressed for the other five.
  `render_human(..., orientation=True)` forces it, and `aec_coach checkpoint`
  defaults to it because a CLI invocation carries no session continuity;
  `--dense` opts out.
- `BLOCKERS` renders only when a blocker exists or the validated gate is
  `Blocked`; `EVIDENCE` renders only when evidence is claimed or required. The
  `EVIDENCE` loop covers every class `evidence_class()` can return, including
  the `project-verified` fallback, so an absent line always means the card had
  nothing to say rather than that the renderer could not say it.
- Removed as strict duplicates: the `CURRENT` line (a subset of the `RAIL`
  summary above it) and the phase prefix on the `GATE` line (the gate is always
  the current phase's gate). The `RAIL` summary keeps naming the phase in words:
  the `◉` marker encodes the same fact, but only for a reader holding the
  legend that the dense render suppresses.

Agents should invoke the same interface automatically at Framing, a material decision,
Verify, Review, PR, Deploy, and outcome reflection. A person may request the same
interaction with phrases such as:

```text
AEC check
What would AEC recommend here?
Show me the tradeoffs.
Teach me why this gate matters.
Record whether that recommendation worked.
```

An agent-specific skill may translate those phrases into the canonical command, but it
must not implement a second resolver or rewrite the coaching response.

## Trust boundary

```text
AEC OWNS                              CONSUMER PROJECT OWNS

- Workflow vocabulary                - Task authority
- Deterministic guidance             - Source-code changes
- Coaching-card contract             - GitHub and project state
- Choice and tradeoff validation     - Branches and worktrees
- Evidence requirements              - Testing and evidence production
- Finished-condition definition      - Review and merge
- Outcome evaluation                 - Deployment and rollback
- Recognition heuristics             - Sensitive project data

AEC advises and evaluates.            The consumer decides and acts.
```

Learner data is local, optional, and user-owned. It may contain competency identities,
explanation preferences, and demonstrated transfer. It must not contain project secrets,
private health data, prompts, source code, or agent reasoning. It must not become resolver
policy or execution authority.

Outcome records remain local and self-reported. Their internal consistency can be
validated, but they do not prove trusted authorship, causation, or that AEC caused a
project result.

## Failure paths

```text
Wrong pin or incompatible contract -> STOP, no trusted coaching
Malformed or stale state           -> BLOCKED, no card
Missing material context           -> ask for facts or abstain
Routine step                       -> no artificial choices
Head changes after proof           -> invalidate and refresh affected evidence
Private or prohibited data         -> reject before resolution
Effectful AEC declaration          -> reject before resolution
Unverified recommendation          -> state evidence quality and lower confidence
Rejected project evidence          -> remain at the current gate
Learner profile unavailable        -> use normal teaching, never change guidance
Outcome cannot be measured         -> inconclusive, never invent a result
```

## Gap map

| Gap | Current evidence | Required exit gate |
| --- | --- | --- |
| Framework admission | Ordinary source-changing PRs now pass `admit`, which became a required check on 2026-08-03; #117, #119, #120, and #121 all merged green. The remaining trap is narrower than this row once claimed: `tools/admission_root_v1.py` and `.github/workflows/candidate-admission.yml` are base-pinned, so a PR that fixes either of them can never satisfy the job that judges it. That is [#65](https://github.com/jasonewillis/AEC/issues/65), and it is what currently blocks [#118](https://github.com/jasonewillis/AEC/pull/118). | A PR that legitimately changes **either** pinned path passes through a recorded exception, and a tampered transition still fails. Exempting only the validator leaves the workflow permanently unfixable. |
| Consumer compatibility | `tools/validate_consumer_connection.py` already resolves a ROUTINE and a MATERIAL probe through the same pure adapter every consumer uses, and `--self-check` proves a pre-`d35f535` fixture is rejected with field-level guidance. `python3 -m tools.aec_coach doctor` now surfaces that proof plus the pin and the released contract versions as one preflight command. Both probes are AEC's own fixed fixtures, not a consumer's own contract, so a consumer-specific incompatibility can still pass them. | Pin validation proves routine and material cards, rejection paths, and the human renderer against a consumer's own contract, not only AEC's built-in probes. |
| State construction | `aec/state_builder.py` already holds general construction logic and takes `profile` as a parameter, defaulting to `AEC_SELF_PROFILE` only when a caller omits it; `docs/consumer-kit/state_producer_template.py` is a copyable producer that supplies a consumer profile and the consumer's own HEAD. The producer is still copied and owned per consumer rather than invoked as a shipped command. | One command builds ignored local state from proven facts and rejects missing facts, without each consumer maintaining its own copied producer. |
| Human coaching | The renderer exists, and `docs/consumer-kit/register-hook.md` now supplies copyable hook registration, trigger selection, and verification steps. The verification step is proven end to end by `tests/test_consumer_install_kit.py`, which walks the documented steps in a throwaway consumer repository rather than asserting the doc reads correctly. A consumer can still discover AEC without invoking it at the prompt boundary, because registration remains consumer-owned by design. | A configured consumer prompt hook renders one complete `[AEC: Project Guidance]` and `[AEC: Mentoring]` card at meaningful triggers, compact state otherwise, and explicit failure without a fabricated rail. |
| Learner adaptation | AEC has static teaching but no local learner profile. | Explanation depth can adapt without changing any engineering decision or authority fact. |
| Reflection | Outcome receipts record closed coaching values, but no normal interaction collects them. | One local command records project impact and coaching value without sensitive content. |
| Agent parity | Claude and Codex bind the same normalized decision. Human coaching parity is not proven. | Both agents render semantically identical project, mentor, and decision blocks. |
| Consumer proof | HealthRAG exposed onboarding and compatibility gaps. A second independent consumer is not proven. | HealthRAG completes one task and a second repo installs in under 30 minutes without copying policy. |

## Delivery sequence

```text
[ Fix pinned-path admission (#65) ]   <-- no longer gates the column below

[ One-command state + coaching renderer ]
            |
            v
[ Pin compatibility + human-output parity ]
            |
            +-------------------+
            |                   |
            v                   v
[ Learner profile ]     [ Outcome interaction ]
            |                   |
            +---------+---------+
                      |
                      v
[ HealthRAG full-task pilot ]
                      |
                      v
[ Second independent consumer ]
                      |
                      v
[ Versioned trustworthy beta ]
```

Each box is one bounded delivery slice. Do not create downstream implementation issues
until the preceding exit gate is merged or the slices are genuinely independent.

**The admission box was detached from the column on 2026-08-03.** It used to sit at the
head of the chain, and while that was true nothing downstream could ship. It is no longer
true: `admit` passes ordinary source PRs, so every box below now depends only on the one
above it. Admission still blocks exactly one thing — a PR that changes
`tools/admission_root_v1.py` or `.github/workflows/candidate-admission.yml`. Treat it as a
release blocker for the beta gate, not as a predecessor edge.

The correction matters more than the fact. A stale blocker at the head of a dependency
graph is the most expensive kind of stale documentation: it is indistinguishable from a
real blocker, so it silently converts every downstream slice into "waiting" and nobody
re-tests the premise, because the graph says not to. Re-verify the head of a chain before
planning from it.

## Trustworthy-beta release gate

AEC is ready to call a trustworthy beta only when:

1. source-changing framework PRs can pass an honest exact-head gate — satisfied for
   ordinary PRs since 2026-08-03, still open for the two base-pinned admission paths
   ([#65](https://github.com/jasonewillis/AEC/issues/65));
2. a consumer detects an incompatible pin before using AEC;
3. one command produces project guidance and student mentoring without hand-written
   state JSON;
4. material choices contain complete tradeoffs, uncertainty, measurable expectations,
   and the real decision owner;
5. routine work does not produce ceremonial decisions;
6. stale, malformed, private, effectful, and wrong-revision inputs fail closed;
7. Claude and Codex render semantically equivalent coaching;
8. learner personalization cannot change engineering guidance;
9. local outcome evaluation reports project impact and coaching value separately,
   without a causal claim; and
10. HealthRAG plus one independent repository complete the adoption proof.
