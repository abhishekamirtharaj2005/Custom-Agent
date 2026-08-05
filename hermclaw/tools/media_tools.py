"""Image generation and vision tools.

Supports:
- Image generation via OpenAI DALL-E API
- Image generation via fal.ai API
- Vision/image analysis by sending images to multimodal models
"""

from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
import structlog

from hermclaw.tools.base import ToolABC, ToolResult, ToolSpec

logger = structlog.get_logger(__name__)


class ImageGenerateTool(ToolABC):
    """Generate images from text descriptions using DALL-E or fal.ai."""

    def __init__(self) -> None:
        pass

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="image_generate",
            description=(
                "Generate an image from a text description using AI. "
                "Supports DALL-E (OpenAI) and fal.ai. The image is saved to a file. "
                "Use this when the user asks to create, draw, or generate an image."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text description of the image to generate."},
                    "provider": {
                        "type": "string",
                        "enum": ["dalle", "fal"],
                        "description": "Image generation provider. Default: dalle.",
                    },
                    "size": {
                        "type": "string",
                        "enum": ["1024x1024", "1024x1792", "1792x1024", "512x512", "256x256"],
                        "description": "Image size. Default: 1024x1024.",
                    },
                    "output_path": {"type": "string", "description": "Where to save the image. Optional."},
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        prompt = args["prompt"]
        provider = args.get("provider", "dalle")
        size = args.get("size", "1024x1024")
        output_path = args.get("output_path", "")

        if not output_path:
            output_dir = Path.home() / ".hermclaw" / "generated_images"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"{uuid.uuid4().hex[:8]}.png")

        try:
            if provider == "dalle":
                return await self._dalle_generate(prompt, size, output_path)
            elif provider == "fal":
                return await self._fal_generate(prompt, size, output_path)
            else:
                return ToolResult(ok=False, output="", error=f"Unknown provider: {provider}")
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Image generation failed: {exc}")

    async def _dalle_generate(self, prompt: str, size: str, output_path: str) -> ToolResult:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return ToolResult(ok=False, output="", error="OPENAI_API_KEY environment variable not set.")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        image_data = base64.b64decode(data["data"][0]["b64_json"])
        Path(output_path).write_bytes(image_data)
        revised = data["data"][0].get("revised_prompt", prompt)
        return ToolResult(ok=True, output=f"Image saved to: {output_path}\nRevised prompt: {revised}")

    async def _fal_generate(self, prompt: str, size: str, output_path: str) -> ToolResult:
        api_key = os.environ.get("FAL_KEY", "")
        if not api_key:
            return ToolResult(ok=False, output="", error="FAL_KEY environment variable not set.")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://fal.run/fal-ai/flux/schnell",
                headers={"Authorization": f"Key {api_key}", "Content-Type": "application/json"},
                json={"prompt": prompt, "image_size": size, "num_images": 1},
            )
            resp.raise_for_status()
            data = resp.json()

        image_url = data["images"][0]["url"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            Path(output_path).write_bytes(img_resp.content)

        return ToolResult(ok=True, output=f"Image saved to: {output_path}")


class VisionTool(ToolABC):
    """Analyze images using multimodal AI models."""

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="vision",
            description=(
                "Analyze an image using AI vision capabilities. Send a local image file "
                "or URL to a multimodal model for description, analysis, OCR, etc."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to a local image file."},
                    "image_url": {"type": "string", "description": "URL of an image to analyze."},
                    "question": {
                        "type": "string",
                        "description": "What to analyze or ask about the image. Default: 'Describe this image in detail.'",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        image_path = args.get("image_path", "")
        image_url = args.get("image_url", "")
        question = args.get("question", "Describe this image in detail.")

        if not image_path and not image_url:
            return ToolResult(ok=False, output="", error="Provide either image_path or image_url.")

        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            # Try Ollama with a vision model
            return await self._ollama_vision(image_path, image_url, question)

        try:
            content = [{"type": "text", "text": question}]

            if image_url:
                content.append({"type": "image_url", "image_url": {"url": image_url}})
            elif image_path:
                p = Path(image_path)
                if not p.exists():
                    return ToolResult(ok=False, output="", error=f"Image not found: {image_path}")
                image_data = base64.b64encode(p.read_bytes()).decode()
                ext = p.suffix.lower().lstrip(".")
                mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{mime};base64,{image_data}"},
                })

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "gpt-4o",
                        "messages": [{"role": "user", "content": content}],
                        "max_tokens": 1024,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            answer = data["choices"][0]["message"]["content"]
            return ToolResult(ok=True, output=answer)
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Vision analysis failed: {exc}")

    async def _ollama_vision(self, image_path: str, image_url: str, question: str) -> ToolResult:
        """Fallback: use Ollama with a vision-capable model (e.g., gemma4:12b)."""
        try:
            images = []
            if image_path:
                p = Path(image_path)
                if not p.exists():
                    return ToolResult(ok=False, output="", error=f"Image not found: {image_path}")
                images.append(base64.b64encode(p.read_bytes()).decode())
            elif image_url:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(image_url)
                    resp.raise_for_status()
                    images.append(base64.b64encode(resp.content).decode())

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": "gemma4:12b",
                        "prompt": question,
                        "images": images,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            return ToolResult(ok=True, output=data.get("response", "No response from vision model."))
        except Exception as exc:
            return ToolResult(ok=False, output="", error=f"Ollama vision failed: {exc}")
