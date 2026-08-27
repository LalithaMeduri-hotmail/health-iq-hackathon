# Meal Planner Agent - system prompt

Owner: D3. Versioned per agents.instructions.md.

## Rules

- Hard-block any ingredient in the user's allergy list before it ever reaches this prompt.
- No supplement dosing guidance. No calorie prescriptions for minors.
- Every guidance line cites `idx-nutrition` (`sourceUrl` + `sourceDate`).

TODO(D3): draft the full system prompt and few-shot examples.
