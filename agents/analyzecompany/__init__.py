"""Analyze-company agent — website + Instagram + LinkedIn → reusable summary."""

__all__ = ["AnalyzeCompanyRequest", "analyzeCompanyAgent"]


def __getattr__(name: str):
    if name == "AnalyzeCompanyRequest":
        from agents.analyzecompany.schemas.company_request import AnalyzeCompanyRequest

        return AnalyzeCompanyRequest
    if name == "analyzeCompanyAgent":
        from agents.analyzecompany.invoke.company_invoke import analyzeCompanyAgent

        return analyzeCompanyAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
