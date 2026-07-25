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