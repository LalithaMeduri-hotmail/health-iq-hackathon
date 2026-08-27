"""`@ai_function` tool definitions (agents.instructions.md). Owner: D3.

Tools are thin adapters that call `services/`, `rag/`, or `repositories/` - no business logic in
the tool body. Give each tool a precise docstring and fully typed parameters/return; the model
routes on these signatures. Tools must be idempotent and side-effect-explicit.

TODO: wrap `services.ocr.extract`, `services.normalize_medicine.normalize`,
`services.normalize_medicine.find_alternatives`, `services.normalize_lab.normalize`,
`services.reference_ranges.get_reference_range`, `rag.retrieve.search`,
`services.comparison.classify_change`, `services.pdf_builder.build`,
`services.share_links.create_share_link` with `@ai_function` (from `agent_framework`).
"""
