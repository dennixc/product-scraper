import asyncio
import logging
from collections import Counter

from app.services.scraper import fetch_with_httpx, fetch_with_firecrawl
from app.services.ai_analyzer import analyze_page_structure

logger = logging.getLogger(__name__)

MAX_URLS = 10


def _majority_vote(values: list[str]) -> str:
    """Return the most common non-empty value, or empty string."""
    filtered = [v for v in values if v]
    if not filtered:
        return ""
    return Counter(filtered).most_common(1)[0][0]


def _majority_vote_bool(values: list[bool]) -> bool:
    """Return the majority boolean value."""
    if not values:
        return False
    return sum(values) > len(values) / 2


def _union_selectors(selector_lists: list[list[str]]) -> list[str]:
    """Union all selectors, preserving order of first appearance, deduped."""
    seen = set()
    result = []
    for selectors in selector_lists:
        for s in selectors:
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result


async def _fetch_url(url: str, firecrawl_api_key: str | None) -> str | None:
    """Fetch a URL, trying Firecrawl first if key provided."""
    if firecrawl_api_key:
        fc_result = await fetch_with_firecrawl(url, firecrawl_api_key)
        if fc_result:
            return fc_result.get("html") or fc_result.get("raw_html")
    return await fetch_with_httpx(url)


async def _analyze_one(
    url: str, api_key: str, ai_model: str | None,
    firecrawl_api_key: str | None,
) -> dict | None:
    """Fetch and analyze a single URL. Returns analysis dict or None."""
    try:
        html = await _fetch_url(url, firecrawl_api_key)
        if not html:
            logger.warning("Brand learn: failed to fetch %s", url)
            return None
        analysis = await analyze_page_structure(html, url, api_key, ai_model)
        if not analysis:
            logger.warning("Brand learn: AI analysis failed for %s", url)
        return analysis
    except Exception as e:
        logger.warning("Brand learn: error analyzing %s: %s", url, e)
        return None


async def learn_brand_profile(
    urls: list[str],
    api_key: str,
    ai_model: str | None = None,
    firecrawl_api_key: str | None = None,
) -> dict:
    """Analyze multiple URLs and aggregate into a brand profile.

    Returns a dict compatible with the analysis dict used throughout the
    scraper pipeline (content_selectors, noise_selectors, etc.).

    Raises ValueError if no URLs could be analyzed.
    """
    urls = urls[:MAX_URLS]

    # Analyze all URLs concurrently
    tasks = [
        _analyze_one(url, api_key, ai_model, firecrawl_api_key)
        for url in urls
    ]
    results = await asyncio.gather(*tasks)
    analyses = [r for r in results if r is not None]

    if not analyses:
        raise ValueError("無法分析任何 URL，請確認連結有效同 API key 正確。")

    # Aggregate by majority vote / union
    profile = {
        "needs_javascript": _majority_vote_bool(
            [a.get("needs_javascript", False) for a in analyses]
        ),
        "extraction_strategy": _majority_vote(
            [a.get("extraction_strategy", "rule_based") for a in analyses]
        ),
        "content_selectors": _union_selectors(
            [a.get("content_selectors", []) for a in analyses]
        ),
        "noise_selectors": _union_selectors(
            [a.get("noise_selectors", []) for a in analyses]
        ),
        "content_structure": _majority_vote(
            [a.get("content_structure", "mixed") for a in analyses]
        ),
        "content_language": _majority_vote(
            [a.get("content_language", "") for a in analyses]
        ),
    }

    urls_analyzed = len(analyses)
    urls_failed = len(urls) - urls_analyzed

    return {
        **profile,
        "urls_analyzed": urls_analyzed,
        "urls_failed": urls_failed,
    }
