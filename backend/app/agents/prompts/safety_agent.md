# Safety Reviewer Agent - system prompt

Owner: D3. Versioned per agents.instructions.md. Mandatory final stage on every response.

## Rules (R1-R6)

See `agents/safety_agent.py` module docstring for the full rule table. Run deterministic checks
first; use the LLM only for judgment calls the regex/rule checks cannot make on their own
(e.g. paraphrased diagnostic language).

TODO(D3): draft the full system prompt and red-team examples (diagnosis, dosage change,
emergency advice attempts - see docs/team-plan.md Day 5).
