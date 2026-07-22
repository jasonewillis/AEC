# Private Course Lens

AEC can add owner-authorized private mentoring context after it resolves the
authoritative lifecycle decision. This optional lens is a local teaching layer, not a
policy source.

## Authority boundary

The resolver runs first. It selects the Gate, Phase, procedure, evidence request,
Good, Finished, and anti-example. The private lens receives the immutable
`ResolutionDecision` and may only attach matching guidance and reflective questions.

The mentoring envelope preserves the complete authoritative decision and its original
resolution hash. It always reports `executes=false` and `mutates=false`. A private card
whose phase matches but whose AEC principle does not match the decision is rejected.

Missing context returns the normal decision with no supplement. Malformed, ambiguous,
duplicate, or mismatched context raises a fail-closed lens error. None of these outcomes
blocks the resolver or authorizes work.

## Privacy boundary

Private transcripts, summaries, prompts, and derived mentoring cards stay outside the
tracked repository. A local course lens may contain owner-authorized paraphrased
guidance for personal mentoring, but it must never be committed, placed in fixtures,
printed by metadata proof tooling, or sent to hosted CI. The coach may render selected
paraphrased guidance to the authorized local user.

Tracked schemas, validators, tests, and documentation use synthetic content only.
Public AEC principles remain independently authored and are the only principle
identities allowed to influence the authoritative procedure catalog.

## Local layout

The recommended ignored layout is:

```text
.local/
  course-sources/
    ai-engineer/
      *.txt
      recovery-manifest.json
  mentor-lenses/
    ai-engineer.json
```

Keep `.local/` excluded from Git. Consumers pass the lens path explicitly instead of
relying on a repository default.

## Metadata-only proof

Run the local proof with a normalized request, the public catalog, and the private
lens. The command prints hashes and selected card identities, never guidance text.

```bash
python3 tools/prove_private_mentor_lens.py \
  --request tests/fixtures/resolver/golden/intake.json \
  --lens /absolute/path/to/private-lens.json
```

Good proof reports `decision_unchanged=true`, `executes=false`, `mutates=false`, and
the same authoritative resolution hash produced without the lens.
