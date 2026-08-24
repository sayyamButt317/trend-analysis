from __future__ import annotations
from typing import Any, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class ContentRecommendationRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "company_id": "550e8400-e29b-41d4-a716-446655440000",
                "company": {
                    "name": "Techtimize",
                    "industry": "AI software development",
                    "services": ["AI agents", "custom software", "cloud"],
                    "target_audience": ["SME founders", "CTOs"],
                },
                "business_goals": ["Generate qualified B2B leads", "Build AI authority"],
                "platforms": ["linkedin", "instagram"],
                "content_intelligence": {
                    "top_topics": [{"topic": "AI", "competitor_usage_pct": 40}],
                    "top_formats": [{"format": "Reels", "competitor_usage_pct": 35}],
                    "content_opportunities": [{"topic": "AI Agents", "priority": "high"}],
                },
                "ninety_day_action_plan": {
                    "summary": "4 immediate actions, 4 mid-term, 4 longer-term",
                    "days_0_30": [{"title": "Sharpen positioning", "priority": "high"}],
                    "days_31_60": [{"title": "Increase content velocity", "priority": "medium"}],
                    "days_61_90": [{"title": "Build proof assets", "priority": "medium"}],
                },
                "calendar_days": 90,
                "idea_count": 10,
            }
        },
    )

    company_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("company_id", "companyId"),
        serialization_alias="company_id",
        description="External company identifier to link this recommendation run.",
        examples=["550e8400-e29b-41d4-a716-446655440000", "org_12345"],
    )
    company: dict[str, Any] = Field(default_factory=dict)
    company_dna: dict[str, Any] = Field(default_factory=dict)
    company_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional analyze-company / competitor handoff payload.",
    )
    competitor_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional competitor analysis response (or subset).",
    )
    content_intelligence: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional content_intelligence block from competitor analysis.",
    )
    ninety_day_action_plan: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("ninety_day_action_plan", "90_day_action_plan"),
        description="90-day action plan provided in the request payload.",
    )
    business_goals: list[str] = Field(
        default_factory=lambda: ["Generate qualified B2B leads"],
    )
    platforms: list[str] = Field(default_factory=lambda: ["linkedin", "instagram"])
    calendar_days: int = Field(default=90, ge=3, le=90)
    idea_count: int = Field(default=10, ge=3, le=30)

    @field_validator("company_id")
    @classmethod
    def _strip_company_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def to_agent_config(self) -> dict[str, Any]:
        company = dict(self.company or {})
        competitor = dict(self.competitor_analysis or {})
        content_intel = dict(self.content_intelligence or {})
        if not content_intel:
            content_intel = dict(competitor.get("content_intelligence") or {})

        company_id = self.company_id or company.get("id") or company.get("company_id")
        if company_id:
            company.setdefault("id", company_id)
            company.setdefault("company_id", company_id)

        return {
            "agent_mode": "content_recommendation",
            "company_id": company_id,
            "company": company,
            "company_dna": dict(self.company_dna or company.get("company_dna") or {}),
            "company_analysis": dict(self.company_analysis or {}),
            "competitor_analysis": competitor,
            "content_intelligence": content_intel,
            "ninety_day_action_plan": dict(self.ninety_day_action_plan or {}),
            "business_goals": [
                str(g).strip() for g in (self.business_goals or []) if str(g).strip()
            ],
            "platforms": [
                str(p).strip().lower() for p in (self.platforms or []) if str(p).strip()
            ],
            "calendar_days": int(self.calendar_days),
            "idea_count": int(self.idea_count),
        }
