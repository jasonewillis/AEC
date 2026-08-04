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
printf 'tmp/\n.local/\n' >> .gitignore
git clone https://github.com/jasonewillis/AEC .local/aec
git -C .local/aec checkout <full-40-character-commit>
(cd .local/aec && python3 -m tools.aec_coach doctor)
```

Ignore `.local/` *before* you clone. `.local/aec` is a second Git repository
inside yours; a later `git add -A` with it untracked commits it as an embedded
repository (gitlink) rather than as files, which is both wrong and confusing to
undo. `tmp/` is ignored here for the same reason — step 2 writes state into it.

`doctor` exits `0` and prints four lines: `PIN`, `CONTRACT`, `ROUTINE`, and
`MATERIAL`. A nonzero exit means this pin is not usable from your project yet;
the failure names the exact contract fields you must add or change. Do not
continue past a red `doctor`. Re-run it after every pin bump — a pin bump that
only tightens `decision_context` breaks material-decision consumers while every
routine check still passes, which is the incident this command exists to catch.

## Step 2 — Produce state

Copy `state_producer_template.py` into your repository and run it before each
coaching interaction. It writes an ignored local file, by convention
`tmp/aec-state.json`. That file is yours; AEC never writes it.

```bash
mkdir -p scripts
cp .local/aec/docs/consumer-kit/state_producer_template.py scripts/aec_state.py
```

Now edit the three constants under `CONFIGURE` in your copy. Only
`CONSUMER_PROJECT` is enforced — the template exits `1` while it still holds the
placeholder — but the other two are wrong for your repository until you set
them:

| Constant | Set it to |
| --- | --- |
| `AEC_CHECKOUT` | Where you vendored AEC. `.local/aec` if you followed step 1. |
| `CONSUMER_PROJECT` | Your repository as `owner/repository`. **Required.** Leaving the placeholder exits `1` with `aec state: FAIL: set CONSUMER_PROJECT before using this template`. |
| `PROFILE_VERSION` | Any string you bump when you edit this file, e.g. `my-repository:1.0.0`. |

The template resolves your repository root as its own parent's parent
(`Path(__file__).resolve().parents[1]`), so `scripts/aec_state.py` works
unchanged. At any other depth, adjust that line — see the comment on it.

```bash
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

Run these from your repository root:

```bash
(cd .local/aec && python3 -m tools.aec_coach doctor)
python3 scripts/aec_state.py --task myrepo#12 --phase Framing --lane FEATURE
python3 .local/aec/tools/aec_coach.py checkpoint \
  --project-root "$PWD" "$PWD/tmp/aec-state.json"
```

`--project-root` is not optional here, and it is the one flag most likely to be
dropped. Your state file binds to *your* `HEAD`; `checkpoint` defaults to
proving the revision of the checkout it runs from, which is AEC's. Two
repositories never share a `HEAD`, so omitting the flag rejects every state
you can possibly produce:

```text
AEC coach checkpoint: FAIL: consumer state rejected:
{"accepted":false,"card":null,"code":"CONSUMER_STATE_MISMATCH",...}
```

The flag supplies the revision to compare against. It does not weaken the
comparison — a state built at a commit you have since moved past is still
rejected, which is the point.

The third command prints the human card and exits `0`. Any rejection exits
nonzero, prints nothing on standard output, and prints one
`AEC coach checkpoint: FAIL: <reason>` line on standard error. That is the
designed failure, not a bug: AEC never renders a workflow rail it cannot prove.

`[AEC: Integration Blocked]` is a *different* signal, and you will not see it
here. Only the registered prompt hook (step 3) emits it, because a hook must
stay non-blocking for the host prompt and so reports failure as visible text
with exit `0`, where `checkpoint` is a command and reports failure as an exit
code.

## What stays yours

| AEC owns | You own |
| --- | --- |
| Workflow vocabulary, guidance, card contract | Task authority and source changes |
| Choice and tradeoff validation | GitHub and project state, branches, merges |
| Evidence requirements, finished conditions | Testing and evidence production |
| Outcome evaluation, recognition heuristics | Hook registration, state file, secrets |

See `docs/architecture/consumer-contract.md` for the full contract and
`docs/architecture/coaching-interaction.md` for the trust boundary.
