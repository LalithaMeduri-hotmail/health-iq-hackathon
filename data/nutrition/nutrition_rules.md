# Nutrition rules (seed source for `idx-nutrition`)

Owner: D2. Ingested by `backend/app/rag/ingest.py` - one chunk per rule entry below.

Each entry should define: `condition`, `cuisine`, `mealType`, `guidance`, `avoidList`,
`sourceName`, `sourceUrl`, `sourceDate`. Ranges/guidance are educational, never a prescription.

## Example entry format

```markdown
### Type 2 diabetes - Indian cuisine - dinner

- **guidance**: Prefer whole grains (millets, brown rice) over refined flour; pair carbs with
  protein/fiber to blunt post-meal glucose spikes.
- **avoidList**: sugary desserts, deep-fried snacks, sweetened beverages
- **source**: `sourceName`, `sourceUrl`, `sourceDate`
```

TODO(D2): add real entries for the demo conditions (diabetes, hypertension, high cholesterol,
thyroid) across at least 2 cuisines and 3 meal types.
