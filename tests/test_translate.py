from translate import get_supported_languages, SUPPORTED_LANGUAGES


def test_get_supported_languages_returns_copy():
    langs = get_supported_languages()
    assert langs == SUPPORTED_LANGUAGES
    assert langs is not SUPPORTED_LANGUAGES


def test_get_supported_languages_contains_common_entries():
    langs = get_supported_languages()
    assert langs["en"] == "English"
    assert langs["es"] == "Spanish"
    assert langs["fr"] == "French"

