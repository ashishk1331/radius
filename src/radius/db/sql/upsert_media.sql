INSERT INTO media (tweet_id, link, kind)
VALUES (?, ?, ?)
ON CONFLICT(tweet_id, link) DO UPDATE SET
    kind = excluded.kind;
