"""Domain records mirroring the SQLite schema, plus the MCP-facing result type."""

from dataclasses import dataclass


@dataclass
class Author:
    id: str
    display_name: str
    handle: str
    avatar: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Author":
        return cls(
            id=str(data["id"]),
            display_name=data.get("display_name", ""),
            handle=data["handle"],
            avatar=data.get("avatar"),
        )


@dataclass
class Tweet:
    id: str
    author_id: str
    content: str
    created_at: str
    in_reply_to_id: str | None = None
    quoted_tweet_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Tweet":
        return cls(
            id=data["id"],
            author_id=data["author_id"],
            content=data["content"],
            created_at=data["created_at"],
            in_reply_to_id=data.get("in_reply_to_id"),
            quoted_tweet_id=data.get("quoted_tweet_id"),
        )


@dataclass
class Media:
    id: str
    tweet_id: str
    link: str
    kind: str

    @classmethod
    def from_dict(cls, data: dict) -> "Media":
        return cls(
            id=data["id"],
            tweet_id=data["tweet_id"],
            link=data["link"],
            kind=data["kind"],
        )


@dataclass
class SearchResult:
    """A bookmark as returned to an MCP client — tweet joined with its author.

    ``score`` is higher-is-better in both search modes: relevance for exact
    (FTS5 bm25, negated) and similarity 0..100 for fuzzy.
    """

    id: str
    handle: str
    display_name: str
    content: str
    created_at: str
    score: float

    @classmethod
    def from_row(cls, row) -> "SearchResult":
        return cls(
            id=row["id"],
            handle=row["handle"],
            display_name=row["display_name"],
            content=row["content"],
            created_at=row["created_at"],
            score=float(row["score"]),
        )


@dataclass
class TweetResult:
    id: str
    display_name: str
    handle: str
    content: str
    created_at: str

    @classmethod
    def from_row(cls, row) -> "SearchResult":
        return cls(
            id=row["id"],
            handle=row["handle"],
            display_name=row["display_name"],
            content=row["content"],
            created_at=row["created_at"],
        )
