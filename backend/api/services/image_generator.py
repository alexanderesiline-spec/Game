"""
Image Generator — Replicate FLUX.1 with real retry logic and character consistency.
"""

import asyncio
import logging
import time
import replicate
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

FLUX_DEV   = "black-forest-labs/flux-dev"
FLUX_SCHNELL = "black-forest-labs/flux-schnell"

STYLE_PREFIXES = {
    "manga":   "manga panel, black and white ink illustration, screen tones, bold outlines, expressive linework, japanese manga style",
    "manhwa":  "manhwa webtoon panel, full color digital art, clean linework, soft cel shading, korean webtoon style, vibrant colors",
    "western": "western comic book panel, full color, bold ink outlines, dynamic composition, marvel comic style, professional illustration",
}

NEGATIVE_PROMPTS = {
    "manga":   "color photo, realistic, 3d render, cgi, watermark, signature, blurry, bad anatomy, extra limbs, deformed hands, missing fingers, text overlay",
    "manhwa":  "photo, realistic, 3d render, watermark, signature, blurry, bad anatomy, extra limbs, deformed, missing fingers, text overlay",
    "western": "anime, manga, photo, realistic, 3d render, watermark, signature, blurry, bad anatomy, extra limbs, text overlay",
}

# Sensible panel dimensions per style
PANEL_DIMS = {
    "manga":   {"small": (512, 512),  "medium": (768, 576),  "large": (768, 1024), "splash": (768, 1152)},
    "manhwa":  {"small": (800, 450),  "medium": (800, 600),  "large": (800, 900),  "splash": (800, 1200)},
    "western": {"small": (512, 384),  "medium": (640, 480),  "large": (768, 576),  "splash": (768, 768)},
}

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]   # seconds between retries


class ImageGenerator:
    def __init__(self, api_token: str, storage_path: str = "./storage"):
        self.client = replicate.Client(api_token=api_token)
        self.storage_path = Path(storage_path)
        (self.storage_path / "panels").mkdir(parents=True, exist_ok=True)

    async def _run_with_retry(self, model: str, input_params: dict) -> str:
        """Run a Replicate model with exponential backoff retries."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                output = await asyncio.to_thread(
                    self.client.run, model, input=input_params
                )
                url = str(output[0]) if isinstance(output, list) else str(output)
                if url.startswith("http"):
                    return url
                raise ValueError(f"Unexpected output format: {url[:100]}")
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    log.warning(f"Replicate attempt {attempt+1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
        raise RuntimeError(f"Image generation failed after {MAX_RETRIES} attempts: {last_error}")

    def _build_prompt(self, prompt: str, style: str) -> str:
        prefix = STYLE_PREFIXES.get(style, STYLE_PREFIXES["manhwa"])
        return f"{prefix}, {prompt}, highly detailed, professional quality"

    async def generate_panel(
        self,
        prompt: str,
        style: str,
        width: int = 800,
        height: int = 600,
        reference_image_url: str = None,
        quality: str = "standard",
    ) -> dict[str, Any]:
        full_prompt = self._build_prompt(prompt, style)
        model = FLUX_DEV if quality == "high" else FLUX_SCHNELL

        params: dict[str, Any] = {
            "prompt": full_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": 28 if quality == "high" else 4,
            "guidance": 3.5,
            "output_format": "webp",
            "output_quality": 90,
        }

        # Strong img2img for character consistency — 0.65 keeps the character
        # recognizable while still following the new scene prompt
        if reference_image_url:
            params["image"] = reference_image_url
            params["prompt_strength"] = 0.65

        url = await self._run_with_retry(model, params)
        log.debug(f"Generated panel: {url[:60]}...")
        return {"url": url, "prompt": full_prompt, "width": width, "height": height}

    async def generate_character_reference(
        self, character: dict, style: str
    ) -> dict[str, Any]:
        """
        Generate a clean character reference portrait.
        Uses FLUX_DEV always for quality — this image drives all subsequent panels.
        """
        base = character.get("image_prompt_base", character.get("name", "character"))
        prompt = (
            f"{base}, character portrait, neutral expression, "
            f"standing pose, simple background, character reference sheet, "
            f"full body visible, clear lighting"
        )
        full_prompt = self._build_prompt(prompt, style)

        params = {
            "prompt": full_prompt,
            "width": 512,
            "height": 768,
            "num_inference_steps": 28,
            "guidance": 3.5,
            "output_format": "webp",
            "output_quality": 95,
        }

        url = await self._run_with_retry(FLUX_DEV, params)
        log.info(f"Generated reference for {character.get('name')}: {url[:60]}")
        return {"url": url, "character": character.get("name")}

    async def generate_panels_batch(
        self,
        panels: list[dict],
        style: str,
        character_references: dict[str, str],
        quality: str = "standard",
        concurrency: int = 3,
        progress_callback=None,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(concurrency)
        results: list[dict | None] = [None] * len(panels)

        async def generate_one(idx: int, panel: dict):
            async with semaphore:
                size = panel.get("size", "medium")
                dims = PANEL_DIMS.get(style, PANEL_DIMS["manhwa"])
                w, h = dims.get(size, dims["medium"])

                # Use first matched character reference
                ref_url = None
                for name in panel.get("characters_present", []):
                    if name in character_references:
                        ref_url = character_references[name]
                        break

                try:
                    result = await self.generate_panel(
                        prompt=panel.get("image_generation_prompt", "comic panel"),
                        style=style,
                        width=w,
                        height=h,
                        reference_image_url=ref_url,
                        quality=quality,
                    )
                    results[idx] = {**panel, "image": result}
                except Exception as e:
                    log.error(f"Panel {idx} failed permanently: {e}")
                    results[idx] = {**panel, "image": None, "image_error": str(e)}

                if progress_callback:
                    done = sum(1 for r in results if r is not None)
                    await progress_callback(done, len(panels))

        await asyncio.gather(*[generate_one(i, p) for i, p in enumerate(panels)])
        return results  # type: ignore
