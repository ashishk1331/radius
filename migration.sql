CREATE TABLE IF NOT EXISTS authors (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    handle TEXT UNIQUE NOT NULL,
    avatar TEXT
);

CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL REFERENCES authors (id),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    in_reply_to_id TEXT REFERENCES tweets (id),
    quoted_tweet_id TEXT REFERENCES tweets (id)
);

CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id TEXT NOT NULL REFERENCES tweets (id),
    link TEXT NOT NULL,
    kind TEXT NOT NULL,
    UNIQUE(tweet_id, link)
);

CREATE INDEX IF NOT EXISTS idx_tweets_author ON tweets(author_id);

CREATE INDEX IF NOT EXISTS idx_tweets_media ON media(tweet_id);

CREATE VIRTUAL TABLE IF NOT EXISTS tweets_fts USING fts5(
    content,
    content='tweets',
    content_rowid='id'
);

-- Trigger: Keep FTS updated on INSERT
CREATE TRIGGER IF NOT EXISTS tweets_ai AFTER INSERT ON tweets BEGIN
    INSERT INTO tweets_fts(rowid, content) VALUES (CAST(new.id AS INTEGER), new.content);
END;

-- Trigger: Keep FTS updated after DELETE
CREATE TRIGGER IF NOT EXISTS tweets_ad AFTER DELETE ON tweets BEGIN
    INSERT INTO tweets_fts(tweets_fts, rowid, content) VALUES ('delete', CAST(old.id AS INTEGER), old.content);
END;

-- Trigger: Keep FTS updated on UPDATE
CREATE TRIGGER IF NOT EXISTS tweets_au AFTER UPDATE ON tweets BEGIN
    INSERT INTO tweets_fts(tweets_fts, rowid, content) VALUES ('delete', CAST(old.id AS INTEGER), old.content);
    INSERT INTO tweets_fts(rowid, content) VALUES (CAST(new.id AS INTEGER), new.content);
END;

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,
    client_name TEXT NOT NULL UNIQUE,
    created_at DATE NOT NULL,
    revoked_at DATE
)