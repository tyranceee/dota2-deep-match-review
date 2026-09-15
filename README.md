# Dota 2 Deep Match Review

Evidence-driven Codex skill for professional, single-match Dota 2 reviews.

The skill separates data facts, inferences, and unknowns, then connects player
actions to tactical responsibilities, consequences, and actionable improvements.

## Included workflows

- Root skill: deep, evidence-driven review of a single Dota 2 match.
- `dota2-review-publisher/`: concise, privacy-aware publication of a completed
  review to `https://ashfury.cn/dota/`.

The intended flow is to finish the Markdown in the original review session,
then open a new session with `gpt-5.6-luna` at `max` reasoning and start the
publishing step with `上传复盘` or `更新网页`.
