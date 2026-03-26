"""
Story Parser — Claude Opus 4.6 with adaptive thinking.
Parses prose into structured comic script data with retries + JSON recovery.
"""

import json
import logging
import re
import anthropic
from typing import Any

from ..models.story import ComicStyle

log = logging.getLogger(__name__)

PARSE_SYSTEM = """You are an expert manga/comic artist and story adapter.
Your job is to convert prose into structured comic script data.

You deeply understand:
- Visual storytelling: show, don't tell
- Panel composition, camera angles, pacing, timing
- Character expression, body language, and emotion
- The specific visual language of manga, manhwa, and western comics
- How to condense prose while preserving emotional impact
- When one big panel beats six small ones

CRITICAL: Always output ONLY valid JSON. No markdown, no explanation, no code fences.
If you're unsure about a value, use a reasonable default — never leave required fields empty."""


STYLE_NOTES = {
    ComicStyle.MANGA: "MANGA: Dramatic angles, speed lines, screen tones, B&W, right-to-left, 4-8 panels/page, exaggerated reactions",
    ComicStyle.MANHWA: "MANHWA: Full color, vertical scroll, clean lines, soft shading, 3-5 tall panels per section, realistic proportions",
    ComicStyle.WESTERN: "WESTERN: Full color, bold inks, traditional grid layout, 6-9 panels/page, dynamic action poses",
}

CHARACTER_PROMPT = """Analyze this story and extract ALL named characters.
Create detailed visual descriptions optimized for AI image generation.

Return ONLY this JSON (no markdown, no extra text):
{
  "characters": [
    {
      "name": "Character Name",
      "role": "protagonist|antagonist|supporting|minor",
      "age_range": "child|teen|young_adult|adult|elderly",
      "image_prompt_base": "concise SDXL/FLUX prompt: physical features, hair, eyes, skin, clothing. Example: 'young woman, long silver hair, violet eyes, pale skin, blue school uniform, determined expression'"
    }
  ]
}"""

SCENE_PROMPT = """Break this story into comic panels/pages for {style_label} style.

{style_notes}

Target: {panel_target} panels total, {panels_per_page} panels per page.

CHARACTER REFERENCES (use exact names):
{char_context}

Return ONLY this JSON (no markdown, no code fences):
{{
  "pages": [
    {{
      "page_number": 1,
      "layout": "splash|grid_2x2|grid_2x3|grid_3x3|vertical_strip",
      "panels": [
        {{
          "panel_number": 1,
          "size": "small|medium|large|splash",
          "scene_description": "One sentence: what is happening",
          "setting": "location and time",
          "characters_present": ["Name1"],
          "character_actions": {{"Name1": "action and expression"}},
          "dialogue": [
            {{"speaker": "Name1", "text": "spoken text", "bubble_style": "speech|thought|shout|whisper|narration"}}
          ],
          "sfx": ["BOOM"],
          "camera_angle": "wide|medium|close-up|extreme-close-up|birds-eye|worms-eye|dutch-angle",
          "lighting": "bright daylight|dim indoor|dramatic shadows|neon glow|golden hour|night",
          "mood": "tense|joyful|sad|mysterious|action|romantic|comedic|horrified",
          "image_generation_prompt": "Detailed AI image prompt for this exact panel. Include: art style, character descriptions, setting, lighting, composition, mood. Be specific."
        }}
      ]
    }}
  ]
}}"""


def _clean_json(text: str) -> str:
    """Strip markdown fences and find the first valid JSON object."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find the outermost { ... }
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response")
    # Find matching closing brace
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return text[start:]


def _parse_json_with_recovery(text: str) -> dict:
    """Try to parse JSON, with progressive recovery attempts."""
    # Attempt 1: clean and parse directly
    try:
        return json.loads(_clean_json(text))
    except Exception:
        pass

    # Attempt 2: fix common Claude JSON mistakes (trailing commas)
    try:
        cleaned = re.sub(r",\s*([}\]])", r"\1", _clean_json(text))
        return json.loads(cleaned)
    except Exception:
        pass

    # Attempt 3: extract with regex as last resort
    raise ValueError(f"Could not parse JSON from response (first 200 chars): {text[:200]}")


class StoryParser:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def _call(self, prompt: str, max_tokens: int = 4096) -> str:
        """Call Claude with adaptive thinking and return text content."""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=PARSE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return next(b.text for b in response.content if b.type == "text")

    def extract_characters(self, story_text: str) -> dict[str, Any]:
        """Extract characters with visual descriptions. Retries once on parse failure."""
        truncated = story_text[:50000]
        prompt = f"{CHARACTER_PROMPT}\n\nSTORY:\n{truncated}"

        for attempt in range(2):
            try:
                text = self._call(prompt, max_tokens=4096)
                return _parse_json_with_recovery(text)
            except Exception as e:
                if attempt == 0:
                    log.warning(f"Character extraction attempt 1 failed: {e}. Retrying...")
                else:
                    log.error(f"Character extraction failed both attempts: {e}")
                    return {"characters": []}

    def parse_scenes(
        self,
        story_text: str,
        style: ComicStyle,
        characters: list[dict],
        panels_per_page: int = None,
    ) -> dict[str, Any]:
        """Parse story into pages + panels. Retries once on parse failure."""
        if panels_per_page is None:
            panels_per_page = {"manga": 6, "manhwa": 4, "western": 6}.get(style.value, 5)

        word_count = len(story_text.split())
        panel_target = max(6, min(int(word_count / 120), 80))

        char_context = "\n".join(
            f"- {c['name']} ({c.get('role','?')}): {c.get('image_prompt_base','')}"
            for c in characters
        ) or "No named characters identified."

        prompt = SCENE_PROMPT.format(
            style_label=style.value.upper(),
            style_notes=STYLE_NOTES[style],
            panel_target=panel_target,
            panels_per_page=panels_per_page,
            char_context=char_context,
        ) + f"\n\nSTORY:\n{story_text[:60000]}"

        for attempt in range(2):
            try:
                text = self._call(prompt, max_tokens=8192)
                return _parse_json_with_recovery(text)
            except Exception as e:
                if attempt == 0:
                    log.warning(f"Scene parsing attempt 1 failed: {e}. Retrying...")
                else:
                    log.error(f"Scene parsing failed both attempts: {e}")
                    # Return minimal fallback structure
                    return {
                        "pages": [{
                            "page_number": 1,
                            "layout": "vertical_strip",
                            "panels": [{
                                "panel_number": 1,
                                "size": "splash",
                                "scene_description": "Story scene",
                                "setting": "Unknown location",
                                "characters_present": [],
                                "character_actions": {},
                                "dialogue": [],
                                "sfx": [],
                                "camera_angle": "medium",
                                "lighting": "natural daylight",
                                "mood": "neutral",
                                "image_generation_prompt": story_text[:200],
                            }],
                        }]
                    }

    def build_panel_prompt(
        self,
        panel: dict,
        characters: list[dict],
        style: ComicStyle,
    ) -> str:
        """Build a final enriched image prompt for a panel."""
        char_map = {c["name"]: c.get("image_prompt_base", "") for c in characters}

        style_prefix = {
            ComicStyle.MANGA:   "manga art, black and white, ink illustration, screen tones",
            ComicStyle.MANHWA:  "manhwa art, full color, clean digital illustration, webtoon style",
            ComicStyle.WESTERN: "western comic art, full color, bold inks, superhero comic style",
        }[style]

        # Inject character visual descriptions into the prompt
        char_parts = []
        for name in panel.get("characters_present", []):
            if name in char_map and char_map[name]:
                action = panel.get("character_actions", {}).get(name, "")
                char_parts.append(f"{char_map[name]}{', ' + action if action else ''}")

        components = [
            style_prefix,
            panel.get("image_generation_prompt", ""),
            *char_parts,
            panel.get("setting", ""),
            panel.get("lighting", ""),
            f"{panel.get('camera_angle', 'medium shot')} shot",
            panel.get("mood", ""),
            "high quality, detailed, professional comic art",
        ]
        return ", ".join(c.strip() for c in components if c.strip())
