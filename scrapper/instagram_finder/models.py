from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class InstagramUser:
    username: str
    profile_url: str
    country: Optional[str] = None
    source: Optional[str] = None
    discovered_by: Optional[str] = None
    name: Optional[str] = None
    bio: Optional[str] = None
    pic: Optional[str] = None
    followers: Optional[int] = None
    category: Optional[list[str]] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self):
        return {
            "username": self.username.lower(),
            "profile_url": self.profile_url,
            "country": self.country,
            "source": self.source,
            "discovered_by": self.discovered_by,
            "name": self.name,
            "bio": self.bio,
            "pic": self.pic,
            "followers": self.followers,
            "category": self.category or [],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
