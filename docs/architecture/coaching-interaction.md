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
                                                                      +---------------------------------------+
                                                                      | 5. RENDER HUMAN COACHING             |
                                                                      |                                       |
                                                                      | [AEC Project] action and proof        |
                                                                      | [AEC Mentor] lesson and recognition   |
                                                                      | Machine JSON only by explicit request |
                                                                      +-------------------+-------------------+
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

## Human interaction

Normal use must render both project guidance and student mentoring from the same
validated card.

```text
+-------------------------------------+  +-------------------------------------+
| [AEC Project]                       |  | [AEC Mentor]                        |
|                                     |  |                                     |
| Position and workflow rail          |  | Transferable concept                |
| Earliest unmet gate                 |  | Why the gate exists                 |
| Recommended next procedure          |  | Recognition heuristic               |
| Required proof                      |  | Material tradeoff                    |
| Exact finished condition            |  | One optional reflection question    |
| Consumer authority boundary         |  | Learner-appropriate explanation     |
+------------------+------------------+  +------------------+------------------+
                   |                                        |
                   +------------------+---------------------+
                                      |
                                      v
                         One deterministic coaching response
```

The project block is concise and actionable. The mentor block teaches the engineering
judgment behind it. A learner profile may change explanation depth or suppress repeated
lessons, but it must never change the decision hash, gate, procedure, recommendation,
evidence requirement, or authority owner.

At a material fork, the same response adds a decision block:

```text
[AEC Decision]
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

These names describe the target interface. They are not implemented at the time of this
document. The pure adapter remains the policy seam. A consumer-owned launcher may read
safe Git facts and construct ignored local state, but facts that cannot be proven must be
supplied explicitly or rejected. The default output is human coaching. Structured output
requires an explicit `--format json`.

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
| Framework admission | Source-changing PRs cannot currently satisfy the base-owned admission job. | A legitimate source transition passes its own admission and a tampered transition still fails. |
| Consumer compatibility | A routine connection probe can pass while a material-decision consumer test fails. | Pin validation proves routine and material cards, rejection paths, and the human renderer. |
| State construction | Consumers manually assemble a large state document. | One command builds ignored local state from proven facts and rejects missing facts. |
| Human coaching | The public adapter returns structured card data and relies on an agent to teach it back. | Default output contains both `[AEC Project]` and `[AEC Mentor]`; raw JSON is explicit. |
| Learner adaptation | AEC has static teaching but no local learner profile. | Explanation depth can adapt without changing any engineering decision or authority fact. |
| Reflection | Outcome receipts record closed coaching values, but no normal interaction collects them. | One local command records project impact and coaching value without sensitive content. |
| Agent parity | Claude and Codex bind the same normalized decision. Human coaching parity is not proven. | Both agents render semantically identical project, mentor, and decision blocks. |
| Consumer proof | HealthRAG exposed onboarding and compatibility gaps. A second independent consumer is not proven. | HealthRAG completes one task and a second repo installs in under 30 minutes without copying policy. |

## Delivery sequence

```text
[ Fix source admission ]
            |
            v
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

## Trustworthy-beta release gate

AEC is ready to call a trustworthy beta only when:

1. source-changing framework PRs can pass an honest exact-head gate;
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
