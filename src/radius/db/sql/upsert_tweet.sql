INSERT INTO tweets (id, author_id, content, created_at, in_reply_to_id, quoted_tweet_id, embedding)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    content = excluded.content,
    in_reply_to_id = excluded.in_reply_to_id,
    embedding = excluded.embedding;
