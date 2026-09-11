# Sample fixtures

Owner: D2 (with OCR fixtures from D1 in `backend/tests/fixtures/ocr/`).

Place the 5 demo prescriptions and 6 demo lab reports (3 before/after pairs) here per
docs/team-plan.md Day 4 ("expand fixtures to 5 prescriptions + 3 report pairs"). Use synthetic or
properly de-identified demo data only - never real patient data - and mark each file
`isDemoData: true` wherever that field is tracked.

Current structured fixtures:

- `demo_profiles.json`: synthetic `demo-user` profile, preferences, consent, and latest report ID.
- `demo_lab_reports.json`: synthetic report history available to the report picker in demo mode.
