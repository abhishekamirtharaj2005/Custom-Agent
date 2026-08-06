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
    """Search the web (free, no API key required).

    Backends tried in order:
    1. ddgs library (pip install ddgs) — uses DuckDuckGo/Bing
    2. Direct Bing HTML scraping — always available
    3. DuckDuckGo HTML lite — secondary fallback
    """

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

        # Backend 1: ddgs library
        result = await self._try_ddgs(query, num)
        if result:
            return result

        # Backend 2: Direct Bing HTML scraping
        result = await self._try_bing_scrape(query, num)
        if result:
            return result

        # Backend 3: DuckDuckGo HTML lite
        result = await self._try_ddg_lite(query, num)
        if result:
            return result

        return ToolResult(ok=True, output="No search results found. Try rephrasing your query or using url_read to fetch a specific URL.")

    async def _try_ddgs(self, query: str, num: int) -> Optional[ToolResult]:
        """Try the ddgs library (new name for duckduckgo-search)."""
        try:
            # Try new 'ddgs' package first
            try:
                from ddgs import DDGS
            except ImportError:
                try:
                    from duckduckgo_search import DDGS
                except ImportError:
                    return None

            import asyncio
            # Run in thread since DDGS is synchronous and may block
            def _search():
                try:
                    return list(DDGS().text(query, max_results=num))
                except Exception:
                    return []

            results = await asyncio.get_event_loop().run_in_executor(None, _search)
            if not results:
                return None

            return self._format_results(results, key_title="title",
                                         key_url=["href", "link"],
                                         key_snippet=["body", "snippet"])
        except Exception as exc:
            logger.debug("web_search.ddgs_failed", error=str(exc)[:100])
            return None

    async def _try_bing_scrape(self, query: str, num: int) -> Optional[ToolResult]:
        """Scrape Bing search results directly."""
        try:
            url = f"https://www.bing.com/search?q={quote_plus(query)}&count={num}"
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                })
                resp.raise_for_status()
                html = resp.text

            results = []
            # Bing results are in <li class="b_algo"> blocks
            algo_pattern = re.compile(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', re.DOTALL)
            title_link_pattern = re.compile(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
            snippet_pattern = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)

            blocks = algo_pattern.findall(html)
            for i, block in enumerate(blocks[:num]):
                title_match = title_link_pattern.search(block)
                snippet_match = snippet_pattern.search(block)
                if title_match:
                    href = title_match.group(1)
                    title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
                    snippet = ""
                    if snippet_match:
                        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                    results.append(f"{i+1}. **{title}**\n   URL: {href}\n   {snippet}")

            if not results:
                # Try alternative Bing result format
                alt_pattern = re.compile(
                    r'<h2[^>]*>\s*<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.DOTALL
                )
                matches = alt_pattern.findall(html)
                for i, (href, title) in enumerate(matches[:num]):
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    if title_clean and not href.startswith("https://www.bing.com"):
                        results.append(f"{i+1}. **{title_clean}**\n   URL: {href}")

            if not results:
                return None
            return ToolResult(ok=True, output="\n\n".join(results))

        except Exception as exc:
            logger.debug("web_search.bing_scrape_failed", error=str(exc)[:100])
            return None

    async def _try_ddg_lite(self, query: str, num: int) -> Optional[ToolResult]:
        """Scrape DuckDuckGo HTML lite version."""
        try:
            url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
                resp.raise_for_status()
                text = resp.text

            results = []
            link_pattern = re.compile(
                r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>\s*(.*?)\s*</a>', re.DOTALL
            )
            snippet_pattern = re.compile(
                r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', re.DOTALL
            )

            links = link_pattern.findall(text)
            snippets = snippet_pattern.findall(text)

            for i, (href, title) in enumerate(links[:num]):
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                results.append(f"{i+1}. **{title_clean}**\n   URL: {href}\n   {snippet}")

            if not results:
                return None
            return ToolResult(ok=True, output="\n\n".join(results))

        except Exception as exc:
            logger.debug("web_search.ddg_lite_failed", error=str(exc)[:100])
            return None

    @staticmethod
    def _format_results(results: list, key_title: str,
                        key_url: list[str], key_snippet: list[str]) -> ToolResult:
        """Format search result dicts into readable text."""
        output_parts = []
        for i, r in enumerate(results, 1):
            title = r.get(key_title, "No title")
            url = "N/A"
            for k in key_url:
                if k in r:
                    url = r[k]
                    break
            snippet = "No description"
            for k in key_snippet:
                if k in r:
                    snippet = r[k]
                    break
            output_parts.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")
        return ToolResult(ok=True, output="\n\n".join(output_parts))


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
