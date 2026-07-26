SELECT t.id, a.display_name, a.handle, t.content, t.created_at, fts.rank
FROM tweets t
JOIN tweets_fts fts ON CAST(t.id AS INTEGER) = fts.rowid
JOIN authors a ON t.author_id = a.id
WHERE tweets_fts MATCH ?
ORDER BY fts.rank DESC
LIMIT ?;