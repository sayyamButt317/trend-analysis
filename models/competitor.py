from typing import List, Optional

from pydantic import BaseModel


class SocialProfiles(BaseModel):
    instagram: Optional[str] = None

    linkedin: Optional[str] = None

    reddit: Optional[str] = None

    x: Optional[str] = None

    youtube: Optional[str] = None


class CompetitorCandidate(BaseModel):

    name: str

    website: Optional[str] = None

    description: Optional[str] = None

    industry: Optional[str] = None

    socials: SocialProfiles = SocialProfiles()

    source: str

    confidence: float = 0.0

    reasoning: Optional[str] = None