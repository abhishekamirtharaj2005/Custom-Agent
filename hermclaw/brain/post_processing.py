"""Think-tag scrubber and response post-processing utilities.

Some models (DeepSeek, QwQ, etc.) output their internal reasoning wrapped
in <think>...</think> tags. This module strips those from the final output
shown to the user while optionally preserving them for reflection/learning.

Also handles:
- Title auto-generation from first exchange
- Response sanitization
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Think-tag scrubbing
# ---------------------------------------------------------------------------

_THINK_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.DOTALL),
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL),
    re.compile(r"<internal_thought>.*?</internal_thought>", re.DOTALL),
    re.compile(r"<reflection>.*?</reflection>", re.DOTALL),
]


def extract_thinking(text: str) -> tuple[str, Optional[str]]:
    """Extract and separate thinking content from model output.

    Returns (clean_text, thinking_content). If no think tags found,
    returns (text, None).
    """
    thinking_parts = []
    clean = text
    for pattern in _THINK_PATTERNS:
        matches = pattern.findall(clean)
        for match in matches:
            # Strip the outer tags to get just the thinking content
            inner = re.sub(r"^<\w+>|</\w+>$", "", match, flags=re.DOTALL).strip()
            if inner:
                thinking_parts.append(inner)
        clean = pattern.sub("", clean)

    clean = clean.strip()
    thinking = "\n\n".join(thinking_parts) if thinking_parts else None
    return clean, thinking


def scrub_think_tags(text: str) -> str:
    """Remove think/reasoning tags from model output, keeping only the
    user-facing response."""
    clean, _ = extract_thinking(text)
    return clean


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------

def generate_title_prompt(user_message: str, assistant_response: str) -> str:
    """Generate a prompt to create a session title from the first exchange."""
    return (
        "Generate a very short title (3-6 words, no quotes) that summarizes "
        "this conversation. Respond with ONLY the title, nothing else.\n\n"
        f"User: {user_message[:200]}\n"
        f"Assistant: {assistant_response[:200]}"
    )


# ---------------------------------------------------------------------------
# Response sanitization
# ---------------------------------------------------------------------------

def sanitize_response(text: str) -> str:
    """Clean up model responses: remove think tags, excessive whitespace,
    and trailing artifacts."""
    text = scrub_think_tags(text)
    # Remove excessive blank lines (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove trailing whitespace
    text = text.strip()
    return text
