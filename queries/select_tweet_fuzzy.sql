SELECT 
    t.id, 
    a.display_name, 
    a.handle, 
    t.content, 
    t.created_at,
    FUZZY_SCORE(t.content, ?) AS score
FROM tweets AS t
JOIN authors AS a ON t.author_id = a.id
WHERE score >= 85
ORDER BY score DESC
LIMIT ?;