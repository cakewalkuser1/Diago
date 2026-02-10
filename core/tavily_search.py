"""
Tavily Web Search Integration
Provides real-time web search for TSBs, recalls, vehicle-specific issues,
and repair information for the ASE Mechanic Agent.

Requires: TAVILY_API_KEY environment variable set.
Install: pip install tavily-python
"""

import os
from dataclasses import dataclass


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    score: float = 0.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")


def is_available() -> bool:
    """Check if Tavily search is configured."""
    return bool(TAVILY_API_KEY)


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def search_automotive(
    query: str,
    vehicle_info: str = "",
    max_results: int = 5,
) -> list[SearchResult]:
    """
    Search the web for automotive diagnostic information.

    Automatically appends automotive context to improve relevance.
    Prefers sources like NHTSA, manufacturer TSBs, and reputable
    automotive forums.

    Args:
        query: The search query.
        vehicle_info: Optional "YYYY Make Model" to focus results.
        max_results: Maximum number of results.

    Returns:
        List of SearchResult objects.
    """
    if not TAVILY_API_KEY:
        return [SearchResult(
            title="Tavily API Key Not Set",
            url="",
            snippet=(
                "Set the TAVILY_API_KEY environment variable to enable "
                "web search. Get a key at https://tavily.com"
            ),
        )]

    # Build enhanced query
    enhanced_query = query
    if vehicle_info:
        enhanced_query = f"{vehicle_info} {query}"

    # Add automotive context if not already present
    auto_terms = ["car", "vehicle", "engine", "automotive", "tsb", "recall"]
    if not any(term in query.lower() for term in auto_terms):
        enhanced_query += " automotive diagnosis"

    try:
        return _search_with_tavily(enhanced_query, max_results)
    except ImportError:
        return _search_with_urllib(enhanced_query, max_results)


def search_tsb(
    vehicle_info: str,
    symptom: str = "",
    max_results: int = 5,
) -> list[SearchResult]:
    """
    Search specifically for Technical Service Bulletins.

    Args:
        vehicle_info: "YYYY Make Model" format.
        symptom: Optional symptom description.
        max_results: Maximum results.

    Returns:
        List of SearchResult objects.
    """
    query = f"{vehicle_info} TSB technical service bulletin"
    if symptom:
        query += f" {symptom}"
    return search_automotive(query, max_results=max_results)


def search_recalls(
    vehicle_info: str,
    max_results: int = 5,
) -> list[SearchResult]:
    """
    Search for NHTSA recalls for a specific vehicle.

    Args:
        vehicle_info: "YYYY Make Model" format.
        max_results: Maximum results.

    Returns:
        List of SearchResult objects.
    """
    query = f"{vehicle_info} NHTSA recall safety"
    return search_automotive(query, max_results=max_results)


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

def _search_with_tavily(query: str, max_results: int) -> list[SearchResult]:
    """Use the official Tavily Python client."""
    from tavily import TavilyClient

    client = TavilyClient(api_key=TAVILY_API_KEY)

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_domains=[
            "nhtsa.gov",
            "alldata.com",
            "mitchelldata.com",
            "repairpal.com",
            "cars.com",
            "edmunds.com",
            "carcomplaints.com",
        ],
    )

    results = []
    for item in response.get("results", []):
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", "")[:300],
            score=item.get("score", 0.0),
        ))

    return results


def _search_with_urllib(query: str, max_results: int) -> list[SearchResult]:
    """Fallback: Use Tavily REST API directly via urllib."""
    import json
    import urllib.request
    import urllib.error

    url = "https://api.tavily.com/search"
    payload = json.dumps({
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "")[:300],
                    score=item.get("score", 0.0),
                ))
            return results
    except urllib.error.URLError as e:
        return [SearchResult(
            title="Search Error",
            url="",
            snippet=f"Web search failed: {e}",
        )]
