# Nutrition rules

`nutrition_rules.json` is the shared, structured knowledge base used by the local meal-planner
retriever. The same records are the future seed source for Azure AI Search `idx-nutrition`.
Rules are curated once and shared by all users; reports and request preferences select relevant
records, and profile/request allergies remove unsafe candidates.

Each rule defines `conditionTags`, `cuisines`, `budgets`, `mealType`, candidate `items`, general
`guidance`, `avoidList`, `allergens`, and a source with name, URL, and date. Guidance is
educational and is never a diagnosis or prescription.

## Current demo coverage

- Condition tags: `elevated-glucose`, `elevated-ldl`, `low-vitamin-d`, `general-wellness`
- Cuisines: `general`, `south-indian-veg`
- Budgets: `low`, `medium`, `high`
- Meal types: breakfast, lunch, dinner
- Sources: World Health Organization and American Heart Association guidance

## Retrieval behavior

Demo mode ranks exact cuisine matches above `general` fallback records and requires the requested
budget. The deterministic allergen gate runs before plan assembly and validates the final plan
again. Production can replace the local retriever with `idx-nutrition` without changing the API.
