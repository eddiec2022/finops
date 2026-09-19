# Standing instructions for this repo

These apply to every task, in addition to whatever `next_task.txt` says for the
current one.

## Always write results.txt

When you finish a task (or stop for any reason - blocked, ambiguous requirement,
partial completion), write your findings/results to `results.txt` at the repo root
before ending the session. Overwrite it each time - it reflects the most recent
task only, not a running log. This is read directly by the Lead Architect (Claude,
via a separate tool) rather than copy-pasted by Edson, so:

- Write it as if it's the primary deliverable, not a chat summary - actual output,
  actual findings, actual data, not "I ran the tests" but the real test results.
- Don't assume anything said earlier in chat will be seen - results.txt is the
  source of truth for what happened in this task.

## Explicit human-decision boundaries are hard stops

If a task says something is "not my call to make," "requires Edson's approval," or
similar - that is a hard stop, not a suggestion. Do not attempt the action, even in
auto/autonomous mode, even if it seems like the obvious next step once
investigation is complete. Report findings in results.txt and stop. This applies
regardless of how confident you are in the recommendation.

## Security-relevant changes

Anything that changes security posture (AV/EDR exclusions, permission scopes,
credential handling, disabling a protection mechanism) always falls under the rule
above, even if not explicitly called out in a given task's text.
