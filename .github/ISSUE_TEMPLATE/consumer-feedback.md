---
name: Consumer feedback
about: Report an integration problem or observation as a consumer of AEC
title: "[CONSUMER] "
labels: consumer-feedback
assignees: ""
---

<!--
This template is for consumers integrating with AEC (e.g. pilots pulling AEC
into their own repo) to report feedback in a comparable, structured shape.
Filing an issue without this template is still fine for non-consumer issues
(bugs in AEC itself, feature requests, internal maintenance, etc.) — just
open a blank issue instead.
-->

## Consumer repository and pinned AEC revision

<!-- e.g. jasonewillis/HealthRAG, pinned to the full 40-character AEC commit SHA
     (not a tag or abbreviated hash — tags can move and short hashes can become
     ambiguous, e.g. abc1234567890abc1234567890abc1234567890) -->

## What was attempted

<!-- The exact command(s) you ran, verbatim. -->

```
<command here>
```

## Observed output

<!-- Paste the actual output verbatim. No paraphrasing. If it contains tokens,
     credentials, private repository details, user data, or other sensitive
     content, redact those values and clearly mark each redaction (e.g.
     [REDACTED: api-token]) so the evidence stays useful without disclosing
     secrets. -->

```
<observed output here>
```

## Expected output and why

<!-- What you expected to happen, and the reasoning (spec, docs, prior behavior, etc.) -->

## Evidence: framework file:line references

<!-- Where in AEC source you checked to confirm this is a framework behavior/bug,
     not a misunderstanding on the consumer side. e.g. aec/human_render.py:42 -->

## Workaround

<!-- Did you work around it? If so, how? If not, what's blocked? -->
