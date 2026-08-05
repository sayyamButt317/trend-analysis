from agents.competitor.state.competitor_state import CompetitorState

from typing import Literal





def _company_handles(state: CompetitorState) -> tuple[str | None, str | None]:
    config = state.get("config") or {}
    company = config.get("company") or {}
    instagram = (
        config.get("company_instagram_username")
        or company.get("instagram_username")
        or ""
    ).strip().lstrip("@").lower() or None
    company_name = (
        config.get("company_name")
        or company.get("name")
        or ""

    ).strip() or None
    return instagram, company_name





def route_after_understand_company(
    state: CompetitorState,
) -> Literal["analyze_user_instagram", "analyze_user_linkedin", "search_intelligence"]:
    instagram, company_name = _company_handles(state)
    if instagram:
        return "analyze_user_instagram"
    if company_name and not (state.get("config") or {}).get("skip_linkedin"):
        return "analyze_user_linkedin"
    return "search_intelligence"





def route_after_user_instagram(

    state: CompetitorState,

) -> Literal["analyze_user_linkedin", "search_intelligence"]:

    config = state.get("config") or {}

    if config.get("skip_linkedin"):

        return "search_intelligence"

    _, company_name = _company_handles(state)

    if company_name:

        return "analyze_user_linkedin"

    return "search_intelligence"

