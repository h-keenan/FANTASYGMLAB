"""Shared card hierarchy: titles high-emphasis, muted metadata only."""

from modules.semantic_glyphs import KIND_CONCEPT, normalize_concept


def test_power_and_franchise_use_distinct_glyphs():
    assert normalize_concept("power") == "rankings"
    assert normalize_concept("franchise") == "draft"
    assert KIND_CONCEPT["power"] != KIND_CONCEPT["franchise"]
