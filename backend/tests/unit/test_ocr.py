from unittest.mock import AsyncMock

from app.config import get_settings
from app.services import ocr


async def test_demo_mode_replays_fixture_when_live_endpoint_is_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("AZURE_DOCINTEL_ENDPOINT", "https://docintel.example.test/")
    get_settings.cache_clear()
    live_extract = AsyncMock()
    monkeypatch.setattr(ocr, "_extract_live", live_extract)

    result = await ocr.extract(b"not-a-readable-image", mode="layout")

    live_extract.assert_not_awaited()
    assert result.source == "fixture"