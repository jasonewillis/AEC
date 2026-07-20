# AEC Milestone Runbook

This runbook turns a milestone or ordered ticket set into one durable goal.
It adapts the sequencing discipline from the pinned, MIT-licensed
[owainlewis/workflows milestone runbook][upstream] without granting AEC any
consumer mutation authority. The verified source revision is
`ce3ff09e27c501e7689fd069ece3aaab63da7e46`.

## Outcome

Every milestone ticket reaches one of two honest states:

- a high-quality pull request with exact-revision evidence
- a documented blocker that names the missing input, right, dependency, or
  decision

The run is complete when every ticket has one of those outcomes. AEC may
recommend the next procedure and evidence. The consumer remains responsible
for claims, execution, state, review, merge, and release.

## 1. Create one goal

Record the milestone name, expected outputs, and stop condition in the agent's
durable goal mechanism. Keep that goal current through compaction, handoff, and
resumed sessions. Do not create a competing goal for each ticket.

## 2. Build the live queue

Read the tracker and record for every issue:

- identifier, title, state, and binary Expected Results
- dependencies and concrete blocker class
- current writer claim, branch, worktree, and exact head when present
- the smallest accepted proof boundary

Mark unclear acceptance criteria as unclear. Ask only for information that
blocks the next useful transition.

Milestones contain owning issues. Pull requests are linked delivery evidence,
not additional milestone tickets. This avoids double-counting one unit of
work.

## 3. Choose the next ticket

Prefer the smallest unblocked ticket that reduces milestone risk. Dependency
unlocks, failing proof, authority foundations, and user-visible correctness
come before polish. Do not combine unrelated tickets in one pull request.

Before implementation, state the ticket, why it is next, the allowed files and
authority surfaces, the line budget, and the binary stop condition.

## 4. Execute with bounded parallelism

Use one active writer per issue in an isolated branch and worktree. Parallelize
independent read-only discovery, isolated implementation, and exact-head
review. Serialize claims, integration, pushes, lifecycle writes, merges, and
releases.

Require the first concrete artifact within:

- 3 minutes for a focused lookup or edit
- 5 minutes for a standard bounded implementation
- 8 minutes for a named complex uncertainty

Allow at most two attempts with one approach. Then preserve artifacts and
change the agent, model, scope, or approach. Reassess immediately when files,
lines, or authority exceed the pre-dispatch budget.

## 5. Finish or block the ticket

A ticket is ready for delivery when it has:

- binary Expected Results and explicit non-goals
- an honest red case followed by focused green proof
- an independently reviewed exact base and head
- current required checks and recorded residual risk
- a reviewable pull request with branch, commit, checks, and evidence

A ticket is blocked only when a named unavailable input, credential, external
system, dependency, or decision prevents the next useful step. Record the
blocker and continue with the next independent ticket. Never call a blocked
ticket done.

## 6. Keep the goal current

After each ticket, update completed, blocked, skipped, and queued work. Route
newly discovered work into the current ticket, a new ticket, or a blocker note.
Do not let the milestone expand silently.

If the queue exceeds one run, stop at a clean boundary and leave a resume note
with exact PRs, checks, blockers, worktrees, and the recommended next ticket.

## 7. Close the run

Review the milestone as a whole. Report:

- goal status and completed pull requests
- blocked tickets with exact causes
- checks and runtime proof
- duplicated or superseded work
- remaining risks and next decision

Do not infer completion from labels, issue closure, an open pull request, or a
merge event. Completion requires the milestone's binary exit evidence at the
correct revision and environment.

[upstream]: https://github.com/owainlewis/workflows
