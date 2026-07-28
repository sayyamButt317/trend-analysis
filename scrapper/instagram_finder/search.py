import asyncio
from typing import Iterable

from tavily import TavilyClient

from config.credential_config import config
from scrapper.finder_tavily_search import run_limited_searches
from scrapper.instagram_finder.constants import (
    DEFAULT_MAX_RESULTS_PER_QUERY,
    GCC_SEARCH_TERMS,
    filter_search_terms_by_categories,
)
from scrapper.instagram_finder.country_detector import normalize_target_countries
from scrapper.instagram_finder.extractor import extract_username


class InstagramSearch:
    def __init__(
        self,
        *,
        max_results_per_query: int = DEFAULT_MAX_RESULTS_PER_QUERY,
        search_concurrency: int = 2,
    ) -> None:
        self.max_results_per_query = max(1, min(max_results_per_query, 20))
        self.search_concurrency = max(1, min(search_concurrency, 4))
        self.client = (
            TavilyClient(api_key=config.TRAVILY_API_KEY)
            if config.TRAVILY_API_KEY
            else None
        )

    def _search_sync(self, query: str) -> list[str]:
        if not self.client:
            return []

        try:
            response = self.client.search(
                query=f'site:instagram.com "{query}"',
                search_depth="basic",
                topic="general",
                max_results=self.max_results_per_query,
                include_answer=False,
                include_raw_content=False,
                include_images=False,
            )
        except Exception:
            return []

        urls: list[str] = []
        for result in response.get("results", []):
            url = result.get("url") or ""
            username = extract_username(url)
            if username:
                urls.append(f"https://www.instagram.com/{username}/")
        return list(dict.fromkeys(urls))

    async def search(self, query: str) -> list[str]:
        return await asyncio.to_thread(self._search_sync, query)

    def _terms_for_countries(self, countries: Iterable[str]) -> dict[str, list[str]]:
        selected = normalize_target_countries(list(countries))
        return {
            country: GCC_SEARCH_TERMS[country]
            for country in selected
            if country in GCC_SEARCH_TERMS
        }

    async def search_by_countries(
        self,
        countries: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> dict[str, dict[str, list[str]]]:
        grouped_terms = self._terms_for_countries(countries or [])
        if categories:
            grouped_terms = {
                country: filter_search_terms_by_categories(
                    terms,
                    categories,
                    country=country,
                )
                for country, terms in grouped_terms.items()
            }
            grouped_terms = {
                country: terms
                for country, terms in grouped_terms.items()
                if terms
            }

        results: dict[str, dict[str, list[str]]] = {}

        for country, terms in grouped_terms.items():
            results[country] = await run_limited_searches(
                terms,
                self._search_sync,
                concurrency=self.search_concurrency,
            )

        return results
