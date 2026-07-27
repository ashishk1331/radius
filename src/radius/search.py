"""Fuzzy scoring, applied in Python rather than inside SQL.

This used to be a SQLite user function registered per connection. libSQL has no
``create_function``, and a hosted database cannot call back into Python anyway,
so scoring moved here — which also means ``fuzzy`` behaves identically against
Turso and against a local file.

The tradeoff is that a fuzzy search pulls every row across the network and
scores it in process, so it costs noticeably more than ``exact``, which ranks
inside the database. That is affordable at the scale a personal bookmark corpus
reaches, and the point at which it stops being affordable is the point to reach
for embeddings instead.
"""

from rapidfuzz import fuzz

# Below this, matches were noise rather than partial credit.
FUZZY_THRESHOLD = 85.0


def fuzzy_score(content: str, query: str) -> float:
    """Partial-ratio similarity in 0..100."""
    if not content or not query:
        return 0.0
    return float(fuzz.partial_ratio(query.lower(), content.lower()))


def rank_fuzzy(
    rows: list[dict],
    query: str,
    top_k: int,
    threshold: float = FUZZY_THRESHOLD,
) -> list[dict]:
    """Score, filter, and order rows by similarity to ``query``."""
    scored = [
        {**row, "score": score}
        for row in rows
        if (score := fuzzy_score(row["content"], query)) >= threshold
    ]
    scored.sort(key=lambda row: row["score"], reverse=True)
    return scored[:top_k]
