-- FTS5 bm25 ranks negative-first (more negative = better match), so it is
-- negated here to keep `score` higher-is-better across both search modes.
SELECT
    t.id,
    a.display_name,
    a.handle,
    t.content,
    t.created_at,
    -fts.rank AS score
FROM tweets t
JOIN tweets_fts fts ON CAST(t.id AS INTEGER) = fts.rowid
JOIN authors a ON t.author_id = a.id
WHERE tweets_fts MATCH ?
ORDER BY score DESC
LIMIT ?;
