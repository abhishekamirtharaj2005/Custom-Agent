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

        # Backend 0: Brave Search API (requires BRAVE_API_KEY)
        result = await self._try_brave(query, num)
        if result:
            return result

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

    async def _try_brave(self, query: str, num: int) -> Optional[ToolResult]:
        """Try Brave Search API (requires BRAVE_API_KEY env var)."""
        import os
        api_key = os.environ.get("BRAVE_API_KEY")
        if not api_key:
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": num},
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            results = []
            for i, r in enumerate(data.get("web", {}).get("results", [])[:num], 1):
                title = r.get("title", "No title")
                url = r.get("url", "")
                snippet = r.get("description", "No description")
                results.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

            if not results:
                return None
            return ToolResult(ok=True, output="\n\n".join(results))
        except Exception as exc:
            logger.debug("web_search.brave_failed", error=str(exc)[:100])
            return None

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


# ---------------------------------------------------------------------------
# Web Readability Tool (Mozilla Readability / Markdown Extraction)
# ---------------------------------------------------------------------------


class WebReadabilityTool(ToolABC):
    """Extract clean, distraction-free markdown article content from any webpage."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="web_readability",
            description=(
                "Extract clean, distraction-free Markdown article content from a web page. "
                "Strips navigation menus, ads, headers, footers, and sidebars, returning "
                "the main article text formatted in Markdown with title and reading time."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to extract article content from."},
                },
                "required": ["url"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        url = args["url"]
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                })
                resp.raise_for_status()
                html = resp.text

            # 1. Extract metadata
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "Untitled Document"

            author_match = re.search(r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            author = author_match.group(1) if author_match else "Unknown"

            # 2. Strip noise elements
            cleaned = re.sub(r'<(script|style|nav|header|footer|aside|form|button|noscript|svg)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)

            # 3. Locate article container if present
            article_match = re.search(r'<article[^>]*>(.*?)</article>', cleaned, re.DOTALL | re.IGNORECASE)
            if not article_match:
                article_match = re.search(r'<main[^>]*>(.*?)</main>', cleaned, re.DOTALL | re.IGNORECASE)
            content_html = article_match.group(1) if article_match else cleaned

            # 4. Convert HTML tags to Markdown formatting
            md = content_html
            # Headings
            md = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h[4-6][^>]*>(.*?)</h[4-6]>', r'\n#### \1\n', md, flags=re.DOTALL | re.IGNORECASE)

            # Formatting
            md = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\n> \1\n', md, flags=re.DOTALL | re.IGNORECASE)

            # Code blocks & inline code
            md = re.sub(r'<pre><code[^>]*>(.*?)</code></pre>', r'\n```\n\1\n```\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', md, flags=re.DOTALL | re.IGNORECASE)

            # Links
            md = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', md, flags=re.DOTALL | re.IGNORECASE)

            # Lists & paragraphs
            md = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'</?(p|div|br\s*/?)>', '\n\n', md, flags=re.IGNORECASE)

            # Remove remaining tags & unescape entities
            md = re.sub(r'<[^>]+>', '', md)
            import html as html_mod
            md = html_mod.unescape(md)

            # Normalize multiple blank lines
            lines = [l.strip() for l in md.splitlines()]
            body_text = "\n".join(lines)
            body_text = re.sub(r'\n{3,}', '\n\n', body_text).strip()

            word_count = len(body_text.split())
            read_time = max(1, round(word_count / 200))

            if len(body_text) > 12000:
                body_text = body_text[:12000] + "\n\n... [article truncated for context budget]"

            output = (
                f"# {title}\n\n"
                f"**URL:** {url} | **Author:** {author} | **Read Time:** ~{read_time} min ({word_count} words)\n\n"
                f"---\n\n"
                f"{body_text}"
            )
            return ToolResult(ok=True, output=output)
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Readability extraction error: {exc}")


# ---------------------------------------------------------------------------
# Firecrawl Scraping & Crawling Tool
# ---------------------------------------------------------------------------


class FirecrawlScrapeTool(ToolABC):
    """Scrape or crawl websites with Firecrawl or built-in recursive crawler."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="firecrawl_scrape",
            description=(
                "Deep scrape or crawl web pages into structured Markdown and sitemaps. "
                "Supports Firecrawl API (via FIRECRAWL_API_KEY) with built-in multi-page crawler fallback. "
                "Actions: scrape (single page deep markdown), crawl (site hierarchy & sub-pages)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target website URL."},
                    "action": {
                        "type": "string",
                        "enum": ["scrape", "crawl"],
                        "description": "Scrape single URL or crawl site hierarchy. Default: scrape.",
                    },
                    "max_depth": {"type": "integer", "description": "Maximum crawl depth (default 2, max 5)."},
                    "limit": {"type": "integer", "description": "Maximum pages to crawl (default 5, max 20)."},
                },
                "required": ["url"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        import os
        from urllib.parse import urljoin, urlparse

        url = args["url"]
        action = args.get("action", "scrape")
        max_depth = min(args.get("max_depth", 2), 5)
        limit = min(args.get("limit", 5), 20)

        # 1. Try Firecrawl API if configured
        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
        if firecrawl_key:
            try:
                endpoint = "https://api.firecrawl.dev/v1/scrape" if action == "scrape" else "https://api.firecrawl.dev/v1/crawl"
                payload = {"url": url}
                if action == "crawl":
                    payload["limit"] = limit
                    payload["maxDepth"] = max_depth

                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {firecrawl_key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if action == "scrape":
                        md = data.get("data", {}).get("markdown", "")
                        return ToolResult(ok=True, output=f"🕷️ Firecrawl Scrape ({url}):\n\n{md[:6000]}")
                    else:
                        crawl_id = data.get("id", "done")
                        return ToolResult(ok=True, output=f"🕷️ Firecrawl Crawl started: Job ID {crawl_id} for {url}")
            except Exception as exc:
                logger.debug("firecrawl.api_failed", error=str(exc))

        # 2. Built-in Local Recursive Scraper & Sitemap Generator
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "HermClaw-WebCrawler/1.0"})
                resp.raise_for_status()
                html = resp.text

            parsed_root = urlparse(url)
            base_domain = parsed_root.netloc

            # Extract links
            found_links = set(re.findall(r'href=["\']([^"\'#]+)["\']', html))
            same_domain_links = []
            for link in found_links:
                full_link = urljoin(url, link)
                p = urlparse(full_link)
                if p.netloc == base_domain and p.scheme in ("http", "https"):
                    same_domain_links.append(full_link)

            unique_links = sorted(list(set(same_domain_links)))[:limit]

            # Convert main page text
            readability_tool = WebReadabilityTool()
            page_res = await readability_tool.execute({"url": url})
            main_markdown = page_res.output if page_res.ok else "Failed to parse main page."

            if action == "scrape":
                return ToolResult(
                    ok=True,
                    output=(
                        f"🕷️ Scrape Result: {url}\n\n"
                        f"{main_markdown[:5000]}\n\n"
                        f"--- Discovered Internal Links ({len(unique_links)}):\n"
                        + "\n".join(f"- {link}" for link in unique_links[:10])
                    ),
                )
            else:
                sitemap_tree = [f"🕷️ Site Hierarchy for {base_domain}:"]
                sitemap_tree.append(f"└── 🏠 {url} (Root)")
                for lk in unique_links:
                    path = urlparse(lk).path or "/"
                    sitemap_tree.append(f"    ├── 📄 {path} -> {lk}")

                return ToolResult(ok=True, output="\n".join(sitemap_tree))

        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Crawler error: {exc}")

