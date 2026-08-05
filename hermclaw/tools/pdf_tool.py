"""PDF extraction tool.

Extracts text content from PDF files using PyMuPDF (fitz) or
falls back to pdfminer.six, and finally to basic binary parsing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec


class PDFTool(ToolABC):
    """Extract text and metadata from PDF files."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="pdf_read",
            description=(
                "Extract text content from a PDF file. Actions: read (extract all text), "
                "info (get metadata: pages, title, author), page (extract specific page)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["read", "info", "page"],
                        "description": "What to extract from the PDF.",
                    },
                    "path": {"type": "string", "description": "Path to the PDF file."},
                    "page_number": {"type": "integer", "description": "Page number (1-indexed) for 'page' action."},
                    "max_pages": {"type": "integer", "description": "Max pages to extract (default: 50)."},
                },
                "required": ["action", "path"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        action = args.get("action", "read")
        path = args.get("path", "")
        if not path:
            return ToolResult(ok=False, output="", error="'path' is required.")

        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult(ok=False, output="", error=f"File not found: {path}")
        if not p.suffix.lower() == ".pdf":
            return ToolResult(ok=False, output="", error=f"Not a PDF file: {path}")

        try:
            # Try PyMuPDF first
            return self._extract_pymupdf(p, action, args)
        except ImportError:
            pass

        try:
            # Fall back to pdfminer
            return self._extract_pdfminer(p, action, args)
        except ImportError:
            pass

        # Final fallback: basic binary text extraction
        return self._extract_basic(p, action)

    def _extract_pymupdf(self, path: Path, action: str, args: dict) -> ToolResult:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))

        if action == "info":
            meta = doc.metadata
            info = {
                "pages": doc.page_count,
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "subject": meta.get("subject", ""),
                "creator": meta.get("creator", ""),
                "producer": meta.get("producer", ""),
                "file_size": f"{path.stat().st_size / 1024:.1f} KB",
            }
            doc.close()
            lines = [f"{k}: {v}" for k, v in info.items() if v]
            return ToolResult(ok=True, output="\n".join(lines))

        elif action == "page":
            page_num = args.get("page_number", 1)
            if page_num < 1 or page_num > doc.page_count:
                doc.close()
                return ToolResult(ok=False, output="", error=f"Page {page_num} out of range (1-{doc.page_count}).")
            page = doc[page_num - 1]
            text = page.get_text()
            doc.close()
            return ToolResult(ok=True, output=f"--- Page {page_num} ---\n{text}")

        else:  # read
            max_pages = args.get("max_pages", 50)
            pages = min(doc.page_count, max_pages)
            text_parts = []
            for i in range(pages):
                page = doc[i]
                text_parts.append(f"--- Page {i+1} ---\n{page.get_text()}")
            doc.close()
            full = "\n\n".join(text_parts)
            if len(full) > 50000:
                full = full[:50000] + "\n... [truncated]"
            return ToolResult(ok=True, output=full)

    def _extract_pdfminer(self, path: Path, action: str, args: dict) -> ToolResult:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage

        if action == "info":
            with open(str(path), "rb") as f:
                pages = list(PDFPage.get_pages(f))
            return ToolResult(ok=True, output=f"Pages: {len(pages)}\nFile: {path.name}")

        text = extract_text(str(path), maxpages=args.get("max_pages", 50))
        if len(text) > 50000:
            text = text[:50000] + "\n... [truncated]"
        return ToolResult(ok=True, output=text)

    def _extract_basic(self, path: Path, action: str) -> ToolResult:
        """Last-resort: extract readable text from PDF binary."""
        data = path.read_bytes()
        # Simple regex to find text between stream objects
        text_chunks = []
        for match in re.finditer(rb'BT\s*(.*?)\s*ET', data, re.DOTALL):
            chunk = match.group(1)
            # Extract text from Tj and TJ operators
            for tj in re.finditer(rb'\((.*?)\)\s*Tj', chunk):
                text_chunks.append(tj.group(1).decode("latin-1", errors="replace"))

        if not text_chunks:
            return ToolResult(
                ok=True,
                output="Could not extract text. Install PyMuPDF for better extraction:\n  pip install PyMuPDF",
            )
        text = "\n".join(text_chunks)
        return ToolResult(ok=True, output=text[:50000])
