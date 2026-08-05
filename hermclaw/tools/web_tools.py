"""Web search tool using DuckDuckGo (no API key required).

Falls back to a simple HTTP scraper if the duckduckgo-search library
isn't installed.  Also includes a URL reader tool for fetching and
extracting readable text from web pages.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class WebSearchTool(ToolABC):
    """Search the web using DuckDuckGo (free, no API key)."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="web_search",
            description=(
                "Search the web for information. Returns a list of search results with "
                "titles, URLs, and snippets. Use this when you need current information, "
                "facts, documentation, or anything you don't already know."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                    "num_results": {"type": "integer", "description": "Number of results to return (default 5, max 10)."},
                },
                "required": ["query"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        query = args["query"]
        num = min(args.get("num_results", 5), 10)

        try:
            # Try using duckduckgo-search library first
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=num))
                if not results:
                    return ToolResult(ok=True, output="No results found.")
                output_parts = []
                for i, r in enumerate(results, 1):
                    output_parts.append(
                        f"{i}. **{r.get('title', 'No title')}**\n"
                        f"   URL: {r.get('href', r.get('link', 'N/A'))}\n"
                        f"   {r.get('body', r.get('snippet', 'No description'))}"
                    )
                return ToolResult(ok=True, output="\n\n".join(output_parts))
            except ImportError:
                pass

            # Fallback: scrape DuckDuckGo HTML lite
            url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                resp.raise_for_status()
                text = resp.text

            # Extract results from DuckDuckGo lite HTML
            results = []
            # Find all result links
            link_pattern = re.compile(r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', re.DOTALL)
            snippet_pattern = re.compile(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL)

            links = link_pattern.findall(text)
            snippets = snippet_pattern.findall(text)

            for i, (href, title) in enumerate(links[:num]):
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                results.append(f"{i+1}. **{title_clean}**\n   URL: {href}\n   {snippet}")

            if not results:
                return ToolResult(ok=True, output="No results found. Try a different query.")
            return ToolResult(ok=True, output="\n\n".join(results))

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Search error: {exc}")


class UrlReadTool(ToolABC):
    """Fetch and extract readable text from a URL."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="url_read",
            description=(
                "Fetch a web page and extract its readable text content. "
                "Use this to read documentation, articles, or any web page content. "
                "Returns plain text stripped of HTML tags."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch and read."},
                },
                "required": ["url"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        url = args["url"]
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                resp.raise_for_status()
                html = resp.text

            # Simple HTML to text conversion
            # Remove script and style tags entirely
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            # Convert common elements
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
            text = re.sub(r'</(p|div|h[1-6]|li|tr)>', '\n', text, flags=re.IGNORECASE)
            # Remove remaining tags
            text = re.sub(r'<[^>]+>', '', text)
            # Decode HTML entities
            import html as html_mod
            text = html_mod.unescape(text)
            # Clean whitespace
            lines = [line.strip() for line in text.splitlines()]
            text = "\n".join(line for line in lines if line)

            # Truncate if too long
            if len(text) > 8000:
                text = text[:8000] + "\n\n... [truncated]"

            return ToolResult(ok=True, output=f"[{url}]\n\n{text}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Error fetching URL: {exc}")
