SELECT
    t.id,
    a.display_name,
    a.handle,
    t.content,
    t.created_at
FROM tweets AS t
JOIN authors AS a ON t.author_id = a.id
LIMIT ?;
