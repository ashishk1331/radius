from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Author:
    id: str
    display_name: str
    handle: str
    avatar: Optional[str] = None

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
    in_reply_to_id: Optional[str] = None
    quoted_tweet_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Tweet":
        return cls(
            id=data["id"],
            author_id=data["id"],
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
