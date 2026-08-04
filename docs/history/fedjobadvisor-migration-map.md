# FedJobAdvisor Migration Map

> **CLOSED — historical audit artifact, not a live work list.**
> Verified 2026-08-03: all eleven source issues (`#8804 #8805 #8807 #8808 #8809 #8810
> #8815 #8816 #8837 #8841 #8879`) are CLOSED in `JLWAI/fedJobAdvisor`. The snapshot
> below states they "were open and labeled `deferred-to-v2`", which was true at the
> `2026-07-22T01:24:39Z` snapshot and is no longer true. The disposition decisions the
> map records remain valid; its open/closed status does not. Retained for provenance.

This map reconciles the eleven framework-related records exported from
`JLWAI/fedJobAdvisor` into the reusable AEC boundary. It is a read-only audit artifact,
not a second issue tree and not permission for AEC to mutate the consumer repository.

## Snapshot and decision rule

- Live REST and issue-body snapshot: `2026-07-22T01:24:39Z`.
- AEC base revision: `8b263c21dbd2fa335856b71f6ec2980f956f3689`.
- Every listed FedJobAdvisor issue was open and labeled `deferred-to-v2` in the live
  snapshot. Several also retained stale-contract or out-of-repository blockers.
- Reusable schemas, resolver logic, factual course provenance, exact Blueprint skill
  provenance, and agent adapters belong in AEC.
- Project state, GitHub transport, lifecycle mutation, labels, merge, deployment, and
  consumer procedures remain owned by FedJobAdvisor.
- Existing consumer issues are reconciled or closed with evidence. This map creates no
  replacement AEC issues.

## Issue-by-issue disposition

| FedJobAdvisor record | Reusable AEC coverage | Remaining owner and closeout condition |
| --- | --- | --- |
| [#8804](https://github.com/JLWAI/fedJobAdvisor/issues/8804) - integration epic | AEC supplies the nine-phase resolver, factual course inventory, pinned Workflows and Blueprint provenance, real Claude/Codex adapter parity, and this consumer-state interface. | FedJobAdvisor owns the program closeout. Close only after its consumer adapter, one writer, pilot, Project reconciliation, and child dispositions have current evidence. |
| [#8805](https://github.com/JLWAI/fedJobAdvisor/issues/8805) - Blueprint authority | `provenance/upstream-lock.json`, `provenance/blueprint-skills.json`, `THIRD_PARTY_NOTICES.md`, and `docs/provenance.md` record direct-use authority, the exact upstream revision, seven paths and hashes, and distinct license boundaries. | FedJobAdvisor owns its repository-specific policy and provenance record. Resume its preserved reviewed checkpoint after its active owner releases the claim; do not duplicate the AEC installation. |
| [#8807](https://github.com/JLWAI/fedJobAdvisor/issues/8807) - lifecycle writer | The consumer-state contract accepts caller-owned position and evidence, then emits only a non-authoritative transition draft. AEC deliberately provides no writer. | FedJobAdvisor owns the authenticated writer, authority snapshot, idempotency, ledger, and Project projection. Its latest live record is `REASSESS_REQUIRED`; resolve the complete five-field authority abstraction there. |
| [#8808](https://github.com/JLWAI/fedJobAdvisor/issues/8808) - mentoring wrapper | Merged AEC PR [#33](https://github.com/jasonewillis/AEC/pull/33) proves real Claude/Codex loader and decision-hash parity. This Slice 4 interface supplies the pure caller-state adapter and normalized card. | Amend to a thin FedJobAdvisor consumer adapter pinned to one reviewed AEC revision. It must read #8807 state, provide a consumer profile and catalog, and prove real-runtime parity without copying AEC. |
| [#8809](https://github.com/JLWAI/fedJobAdvisor/issues/8809) - course and skill traceability | `provenance/course-inventory.json` records all 13 private course lessons and the gateway PDF as factual metadata. AEC procedures use independently authored principles, while exact Blueprint provenance is separately locked. | FedJobAdvisor owns consumer procedure registration and support-document drift. Reconcile its old lesson-derived runtime mapping with AEC's private-course boundary; private course expression cannot become public runtime authority. |
| [#8810](https://github.com/JLWAI/fedJobAdvisor/issues/8810) - three-issue pilot | AEC supplies deterministic decisions, cards, red rejections, and runtime-parity proof that the pilot may consume. | FedJobAdvisor owns pilot selection, claims, lifecycle evidence, auto-merge receipt, production outcome, retrospective, and Project reconciliation. Existing PRs #9021 and #9022 remain partial evidence only. |
| [#8815](https://github.com/JLWAI/fedJobAdvisor/issues/8815) - non-lifecycle GraphQL removal | No reusable AEC implementation. The AEC interface is transport-free and performs no GitHub calls. | FedJobAdvisor owns REST workflow migration, request ceilings, pagination, production-path evidence, and rate-limit behavior. Do not import this transport policy into AEC. |
| [#8816](https://github.com/JLWAI/fedJobAdvisor/issues/8816) - agent-support REST migration | No reusable AEC implementation. AEC adapters consume in-memory caller state and never discover Project identifiers. | FedJobAdvisor owns support-skill transport migration and production-path proof. The static 33-finding cleanup is evidence, not completion until its real consumer paths pass. |
| [#8837](https://github.com/JLWAI/fedJobAdvisor/issues/8837) - FJA skill pack | AEC owns only the seven exact pinned Blueprint skills and project-neutral resolver procedures. Its real loaders reject duplicate discovery. | FedJobAdvisor owns its named product procedures, canonical runtime pack, and loader proof. Consume AEC rather than copying or renaming its general skills. |
| [#8841](https://github.com/JLWAI/fedJobAdvisor/issues/8841) - mutation-surface lock | AEC decisions and cards are structurally non-executing and non-mutating. The consumer adapter rejects effectful state before resolver invocation. | FedJobAdvisor owns local mutation policy and server-side enforcement around #8807. Reconcile the stale rights blocker against the provisioned writer identity, then prove valid and denied paths there. |
| [#8879](https://github.com/JLWAI/fedJobAdvisor/issues/8879) - no-adoption provenance | AEC already distinguishes exact authorized Blueprint use from any license claim and rejects private course expression as runtime authority. | FedJobAdvisor must supersede the obsolete no-adoption umbrella or amend it to its remaining repository-admission boundary. Do not migrate its six-child archive-forensics tree into AEC. |

## What can close versus what must remain consumer work

AEC completion evidence can satisfy the reusable portions of #8805, #8808, #8809,
#8837, and #8841. It cannot by itself close those consumer issues because each retains
repository-specific acceptance. Issues #8807, #8810, #8815, and #8816 are entirely
consumer execution. Issue #8879 needs an explicit supersession or narrowed consumer
contract because its original no-adoption premise changed after direct-use authority
was recorded. Epic #8804 closes only after these dispositions and the pilot reconcile.

The migration is finished when FedJobAdvisor links one reviewed AEC revision, removes
stale duplicate foundation code, proves the thin adapter against real caller state,
and closes or explicitly supersedes every listed consumer record with its own evidence.
