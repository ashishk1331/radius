"""Scoring helpers registered as SQLite user functions."""

from rapidfuzz import fuzz


def fuzzy_score(content: str, query: str) -> float:
    """Partial-ratio similarity in 0..100, exposed to SQL as FUZZY_SCORE."""
    if not content or not query:
        return 0.0
    return float(fuzz.partial_ratio(query.lower(), content.lower()))
