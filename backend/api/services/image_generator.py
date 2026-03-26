"""
Image Generator — wraps Replicate API for panel image generation.

Uses FLUX.1-dev by default (best quality for realistic/stylized art).
Falls back to SDXL for speed if needed.

Character consistency strategy:
- First panel with a character: generate a reference image
- Subsequent panels: use img2img with that reference + detailed prompt
- Track reference image URLs per character per comic
"""

import asyncio
import httpx
import base64
import replicate
from pathlib import Path
from typing import Any


# FLUX.1-dev — best quality, no GPU needed
FLUX_DEV_MODEL = "black-forest-labs/flux-dev"
FLUX_SCHNELL_MODEL = "black-forest-labs/flux-schnell"  # faster, less quality

# Style-specific negative prompts
NEGATIVE_PROMPTS = {
    "manga": "color, photo, realistic, 3d render, watermark, text, logo, blurry, bad anatomy, extra limbs, deformed hands",
    "manhwa": "photo, realistic, 3d render, watermark, text, logo, blurry, bad anatomy, extra limbs, deformed",
    "western": "anime, manga, photo, realistic, 3d render, watermark, text, logo, blurry, bad anatomy",
}

STYLE_LORA_PROMPTS = {
    "manga": "manga art style, black and white ink illustration, halftone screen tones, bold outlines, expressive linework, japanese manga panel",
    "manhwa": "manhwa art style, full color digital illustration, clean linework, soft shading, korean webtoon panel, vibrant colors",
    "western": "western comic book art style, full color illustration, bold inks, dynamic composition, marvel/dc comic panel style",
}


class ImageGenerator:
    def __init__(self, api_token: str, storage_path: str = "./storage"):
        self.client = replicate.Client(api_token=api_token)
        self.storage_path = Path(storage_path)
        self.panels_path = self.storage_path / "panels"
        self.panels_path.mkdir(parents=True, exist_ok=True)

    async def generate_panel(
        self,
        prompt: str,
        style: str,
        width: int = 832,
        height: int = 1216,
        reference_image_url: str = None,
        quality: str = "standard",  # standard | high
    ) -> dict[str, Any]:
        """Generate a single comic panel."""
        style_prefix = STYLE_LORA_PROMPTS.get(style, STYLE_LORA_PROMPTS["manhwa"])
        negative = NEGATIVE_PROMPTS.get(style, "")

        full_prompt = f"{style_prefix}, {prompt}"

        model = FLUX_DEV_MODEL if quality == "high" else FLUX_SCHNELL_MODEL

        input_params: dict[str, Any] = {
            "prompt": full_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": 28 if quality == "high" else 4,
            "guidance": 3.5,
            "output_format": "webp",
            "output_quality": 90,
        }

        # If we have a reference image, use img2img for character consistency
        if reference_image_url:
            input_params["image"] = reference_image_url
            input_params["prompt_strength"] = 0.75  # balance between ref and new prompt

        output = await asyncio.to_thread(
            self.client.run, model, input=input_params
        )

        # Replicate returns a list of URLs or a FileOutput
        if isinstance(output, list):
            image_url = str(output[0])
        else:
            image_url = str(output)

        return {
            "url": image_url,
            "prompt": full_prompt,
            "style": style,
            "width": width,
            "height": height,
        }

    async def generate_character_reference(
        self,
        character: dict,
        style: str,
    ) -> dict[str, Any]:
        """Generate a reference portrait for a character (used for consistency)."""
        prompt = (
            f"{character['image_prompt_base']}, "
            f"character portrait, neutral expression, full body, white background, "
            f"character reference sheet"
        )
        return await self.generate_panel(
            prompt=prompt,
            style=style,
            width=512,
            height=768,
            quality="high",
        )

    async def generate_panels_batch(
        self,
        panels: list[dict],
        style: str,
        character_references: dict[str, str],  # name -> image_url
        concurrency: int = 3,
        progress_callback=None,
    ) -> list[dict[str, Any]]:
        """Generate all panels with limited concurrency."""
        semaphore = asyncio.Semaphore(concurrency)
        results = [None] * len(panels)

        async def generate_one(idx: int, panel: dict):
            async with semaphore:
                # Find reference image for primary character in panel
                reference_url = None
                for char_name in panel.get("characters_present", []):
                    if char_name in character_references:
                        reference_url = character_references[char_name]
                        break

                result = await self.generate_panel(
                    prompt=panel.get("image_generation_prompt", ""),
                    style=style,
                    reference_image_url=reference_url,
                )
                results[idx] = {**panel, "image": result}
                if progress_callback:
                    await progress_callback(idx + 1, len(panels))

        await asyncio.gather(*[generate_one(i, p) for i, p in enumerate(panels)])
        return results

    @staticmethod
    def get_panel_dimensions(style: str, panel_size: str) -> tuple[int, int]:
        """Return width x height for a panel based on style and size."""
        dimensions = {
            "manga": {
                "small": (416, 416),
                "medium": (832, 624),
                "large": (832, 1040),
                "splash": (832, 1216),
            },
            "manhwa": {
                "small": (800, 400),
                "medium": (800, 600),
                "large": (800, 900),
                "splash": (800, 1200),
            },
            "western": {
                "small": (400, 300),
                "medium": (600, 450),
                "large": (800, 600),
                "splash": (800, 800),
            },
        }
        return dimensions.get(style, dimensions["manhwa"]).get(
            panel_size, (800, 600)
        )
