from typing import Optional

from pydantic import BaseModel, Field


class GlobalTrendRequest(BaseModel):
    region: Optional[str] = Field(
        default=None,
        description="Optional region hint for Google Trends geos (e.g. GCC, US, Pakistan).",
        examples=["GCC", "United States", "Pakistan"],
    )
    min_engagement_rate: float = Field(default=1.0, ge=0)
    include_web_trends: bool = Field(
        default=True,
        description="Crawl web sources (SocialBee, Metricool, Reddit, X, LinkedIn, Google Trends).",
    )

    def to_agent_config(self) -> dict:
        return {
            "agent_mode": "global_trend",
            "platform": "instagram",
            "include_web_trends": self.include_web_trends,
            "min_engagement_rate": self.min_engagement_rate,
            "region": self.region,
        }


# Backward-compatible alias for global trend runs
TrendDiscoveryRequest = GlobalTrendRequest
