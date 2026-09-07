import pytest

import supabase_media


def test_extract_total_from_content_range_parses_expected_values():
    assert supabase_media._extract_total_from_content_range("0-49/120") == 120
    assert supabase_media._extract_total_from_content_range("0-49/*") == 0
    assert supabase_media._extract_total_from_content_range("invalid") == 0
    assert supabase_media._extract_total_from_content_range(None) == 0


def test_media_status_value_normalizes_unknown_values():
    assert supabase_media.media_status_value("en_cours") == "en_cours"
    assert supabase_media.media_status_value("termine") == "termine"
    assert supabase_media.media_status_value("other") == "termine"


def test_headers_raise_when_supabase_not_configured(monkeypatch):
    monkeypatch.setattr(supabase_media, "SUPABASE_URL", "")
    monkeypatch.setattr(supabase_media, "SUPABASE_SERVICE_ROLE_KEY", "")

    with pytest.raises(supabase_media.SupabaseNotConfiguredError):
        supabase_media._headers()


