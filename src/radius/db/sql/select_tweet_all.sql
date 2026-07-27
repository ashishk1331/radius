-- Candidate rows for fuzzy search. Scoring, filtering, and ordering happen in
-- Python (see radius.search), because libSQL cannot call a Python function
-- mid-query the way a local sqlite3 connection could.
SELECT
    t.id,
    a.display_name,
    a.handle,
    t.content,
    t.created_at
FROM tweets AS t
JOIN authors AS a ON t.author_id = a.id;
