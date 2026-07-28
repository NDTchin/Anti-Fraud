from scripts.prepare_neo4j_import import normalize


def test_normalize_address_text() -> None:
    assert normalize("  Quan   1  ") == "quan 1"


def test_normalize_null() -> None:
    assert normalize(None) == ""

