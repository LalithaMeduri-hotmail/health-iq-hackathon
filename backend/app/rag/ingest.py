"""RAG ingestion pipeline (implementation-plan.md Section 3.2). Owner: D2.

Reads the curated sources under `data/`, turns each row into one retrievable chunk, embeds them
with `text-embedding-3-large`, and uploads in batches. Idempotent via deterministic document ids
(`sha1(index + row_key)`), so re-running replaces rows rather than duplicating them.

Every chunk carries `sourceName`/`sourceUrl`/`sourceDate`, because a chunk without provenance
cannot be cited and would have to be dropped at answer time.
"""

import csv
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.rag import embeddings

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# Search rejects documents larger than its request cap; curated rows are far smaller, but a
# truncated chunk still retrieves usefully whereas a rejected batch loses the whole file.
_MAX_CONTENT_CHARS = 8000

UPLOAD_BATCH = 100


def _doc_id(index: str, row_key: str) -> str:
    return hashlib.sha1(f"{index}:{row_key}".encode()).hexdigest()


def _document(index: str, row_key: str, title: str, content: str, tags: str, source: dict) -> dict:
    return {
        "id": _doc_id(index, row_key),
        "title": title,
        "content": content[:_MAX_CONTENT_CHARS],
        "tags": tags,
        "sourceName": source.get("sourceName", ""),
        "sourceUrl": source.get("sourceUrl", ""),
        "sourceDate": source.get("sourceDate", ""),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build_medicine_docs() -> list[dict]:
    """One chunk per catalog row: brand, ingredient, strength, form and price provenance."""
    docs = []
    for row in _read_csv(_DATA_DIR / "medicines" / "medicine_catalog.csv"):
        strength = f"{row['strengthValue']} {row['strengthUnit']}"
        title = f"{row['brandName']} {strength} {row['dosageForm']}"
        content = (
            f"{row['brandName']} is a {row['dosageForm']} containing {row['activeIngredient']} "
            f"{strength}, marketed by {row['manufacturer']}. Generic name: {row['genericName']}. "
            f"Indicative price INR {row['mrpInr']}."
        )
        tags = f"{row['activeIngredient']}|{row['dosageForm']}".casefold()
        docs.append(
            _document(
                "idx-medicines",
                f"{row['brandName']}-{strength}-{row['dosageForm']}",
                title,
                content,
                tags,
                {
                    "sourceName": row["sourceName"],
                    "sourceUrl": row["sourceUrl"],
                    "sourceDate": row["sourceDate"],
                },
            )
        )
    return docs


def build_reference_range_docs() -> list[dict]:
    """One chunk per reference-range row, carrying the plain-language explanation."""
    docs = []
    for row in _read_csv(_DATA_DIR / "reference_ranges" / "lab_reference_ranges.csv"):
        title = f"{row['canonicalKey']} reference range"
        content = (
            f"{row['canonicalKey']}: typical range {row['refLow']}-{row['refHigh']} {row['unit']} "
            f"for sex {row['sex']}, ages {row['ageMin']}-{row['ageMax']}. {row['plainLanguage']}"
        )
        docs.append(
            _document(
                "idx-reference-ranges",
                f"{row['canonicalKey']}-{row['sex']}-{row['ageMin']}-{row['ageMax']}",
                title,
                content,
                row["canonicalKey"].casefold(),
                {
                    "sourceName": row["sourceName"],
                    "sourceUrl": row["sourceUrl"],
                    "sourceDate": "2026-06-01",
                },
            )
        )
    return docs


def build_specialist_docs() -> list[dict]:
    """One chunk per parameter group -> specialty mapping."""
    docs = []
    for row in _read_csv(_DATA_DIR / "specialists" / "specialist_mapping.csv"):
        title = f"{row['parameterGroup']} -> {row['specialtyCategory']}"
        content = (
            f"Parameters {row['canonicalKeys'].replace('|', ', ')} belong to the "
            f"{row['parameterGroup']} group, usually discussed with a {row['specialtyCategory']}. "
            f"{row['whenToConsult']} {row['disclaimer']}"
        )
        docs.append(
            _document(
                "idx-specialists",
                row["parameterGroup"],
                title,
                content,
                f"{row['parameterGroup']}|{row['canonicalKeys']}".casefold(),
                {
                    "sourceName": row["sourceName"],
                    "sourceUrl": row["sourceUrl"],
                    "sourceDate": "2026-06-01",
                },
            )
        )
    return docs


def build_nutrition_docs() -> list[dict]:
    """One chunk per curated nutrition rule."""
    payload = json.loads((_DATA_DIR / "nutrition" / "nutrition_rules.json").read_text(encoding="utf-8"))
    rules: list[dict[str, Any]] = payload.get("rules", []) if isinstance(payload, dict) else []

    docs = []
    for rule in rules:
        title = f"{rule['mealType']}: {', '.join(rule['items'])}"
        content = (
            f"{rule['guidance']} Suggested for {', '.join(rule['conditionTags'])}. "
            f"Items: {', '.join(rule['items'])}. Avoid: {', '.join(rule.get('avoidList', [])) or 'nothing specific'}."
        )
        tags = "|".join([rule["mealType"], *rule["conditionTags"], *rule.get("cuisines", [])]).casefold()
        docs.append(_document("idx-nutrition", rule["id"], title, content, tags, rule.get("source", {})))
    return docs


_BUILDERS = {
    "idx-medicines": build_medicine_docs,
    "idx-reference-ranges": build_reference_range_docs,
    "idx-specialists": build_specialist_docs,
    "idx-nutrition": build_nutrition_docs,
}


async def ingest_index(index_name: str) -> int:
    """Embed and upload every chunk for one index. Returns the document count."""
    from app.deps import get_search_client

    docs = _BUILDERS[index_name]()
    if not docs:
        return 0

    vectors = await embeddings.embed([doc["content"] for doc in docs])
    for doc, vector in zip(docs, vectors, strict=True):
        doc["contentVector"] = vector

    client = get_search_client(index_name)
    for start in range(0, len(docs), UPLOAD_BATCH):
        await client.upload_documents(documents=docs[start : start + UPLOAD_BATCH])

    logger.info("ingested %d documents into %s", len(docs), index_name)
    return len(docs)


async def ingest_all() -> dict[str, int]:
    """Ingest every source in `data/` into its index. Safe to re-run."""
    return {name: await ingest_index(name) for name in _BUILDERS}
