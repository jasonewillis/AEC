# Consumer install kit: register the AEC prompt hook

Copy the snippets on this page. Do not rewrite them from the architecture prose.
Nothing here grants AEC any authority in your repository: the hook reads state
and prints coaching text. It never edits files, moves issues, or merges anything.

AEC ships the framework half only. Installing a pinned AEC checkout does not
register a hook and does not create state. Those two steps are yours, and this
page is the whole of them.

## Step 1 — Pin AEC and prove the pin

Vendor AEC at one exact commit, then prove that commit before you trust a card:

```bash
git clone https://github.com/jasonewillis/AEC .local/aec
git -C .local/aec checkout <full-40-character-commit>
(cd .local/aec && python3 -m tools.aec_coach doctor)
```

`doctor` exits `0` and prints four lines: `PIN`, `CONTRACT`, `ROUTINE`, and
`MATERIAL`. A nonzero exit means this pin is not usable from your project yet;
the failure names the exact contract fields you must add or change. Do not
continue past a red `doctor`. Re-run it after every pin bump — a pin bump that
only tightens `decision_context` breaks material-decision consumers while every
routine check still passes, which is the incident this command exists to catch.

## Step 2 — Produce state

Copy `state_producer_template.py` into your repository (for example
`scripts/aec_state.py`), fill in the three marked constants, and run it before
each coaching interaction. It writes an ignored local file, by convention
`tmp/aec-state.json`. That file is yours; AEC never writes it.

```bash
echo "tmp/" >> .gitignore
python3 scripts/aec_state.py --task myrepo#12 --phase Framing --lane FEATURE
```

## Step 3 — Register the hook

AEC reads a Claude-compatible `UserPromptSubmit` payload from standard input,
discards the prompt text, and binds the state to your repository's exact `HEAD`.

Add this to your project's `.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.local/aec/tools/aec_prompt_hook.py\" --state \"$CLAUDE_PROJECT_DIR/tmp/aec-state.json\" --project-root \"$CLAUDE_PROJECT_DIR\" --environment \"${AEC_ENVIRONMENT:-local}\""
          }
        ]
      }
    ]
  }
}
```

`--state` may be omitted if you export `AEC_STATE_PATH`; `--environment` may be
omitted if you export `AEC_ENVIRONMENT`. Both default in favour of the explicit
flag, so prefer the flags above when the value is fixed for the repository.

## Step 4 — Choose a trigger per interaction

Without a trigger the hook emits one compact routine-progress line. That is the
correct default: AEC does not read your prompt text and will not guess a
lifecycle phase from prose.

For a full `[AEC: Project Guidance]` / `[AEC: Mentoring]` card, your own adapter
adds one closed `aec_trigger` value to the per-interaction JSON payload:

```text
status-request  task-intake      phase-transition  gate-transition
gate-failure    review-finding   pr-created        deploy-observe
```

Selecting that value is a consumer-owned decision. A static command-line
argument cannot do it, because it would pick the same output for every prompt.

## Step 5 — Verify the install

```bash
(cd .local/aec && python3 -m tools.aec_coach doctor)
python3 scripts/aec_state.py --task myrepo#12 --phase Framing --lane FEATURE
(cd .local/aec && python3 -m tools.aec_coach checkpoint "$PWD/../../tmp/aec-state.json")
```

The third command prints the human card. If it prints
`[AEC: Integration Blocked]`, your state was missing or rejected — that is the
designed failure, not a bug. AEC never renders a workflow rail it cannot prove.

## What stays yours

| AEC owns | You own |
| --- | --- |
| Workflow vocabulary, guidance, card contract | Task authority and source changes |
| Choice and tradeoff validation | GitHub and project state, branches, merges |
| Evidence requirements, finished conditions | Testing and evidence production |
| Outcome evaluation, recognition heuristics | Hook registration, state file, secrets |

See `docs/consumer-contract.md` for the full contract and
`docs/architecture/coaching-interaction.md` for the trust boundary.
