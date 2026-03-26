"""
Story Parser — uses Claude to break a story into structured comic scenes.

Extracts:
- Characters with visual descriptions
- Scene breakdowns with emotional beats
- Dialogue and SFX
- Panel composition suggestions
- Pacing guidance
"""

import json
import anthropic
from typing import Any

from ..models.story import ComicStyle


PARSE_SYSTEM_PROMPT = """You are an expert manga/comic artist and story adapter.
Your job is to convert prose into structured comic script data.

You understand:
- Visual storytelling and "show don't tell"
- Panel composition, camera angles, and pacing
- Character expression and body language
- The difference between manga (B&W, dramatic angles, screen tones),
  manhwa (full color, clean lines, vertical scroll), and
  western comics (full color, traditional panels)
- How to condense prose while keeping emotional impact
- When to use big splash panels vs. small reaction panels

Always output valid JSON matching the requested schema exactly."""


STYLE_GUIDANCE = {
    ComicStyle.MANGA: """
MANGA STYLE NOTES:
- Dramatic angle shifts (extreme close-ups, dutch angles, bird's-eye)
- Expressive reactions with exaggerated emotions
- Speed lines and motion blur
- Screen tone descriptions for shadows and textures
- Reading order: right-to-left panels
- N-screentone: solid black, gray tones, patterns
- Typical panel counts: 4-8 per page
""",
    ComicStyle.MANHWA: """
MANHWA STYLE NOTES:
- Vertical scroll format (single column of panels)
- Full color, soft/pastel palette typical
- Clean linework, detailed backgrounds
- Expressive but more realistic proportions than manga
- Wider panels showing more of the scene
- Typical panel counts: 3-5 per vertical scroll section
""",
    ComicStyle.WESTERN: """
WESTERN COMICS STYLE NOTES:
- Traditional grid layout (2-3 rows, 2-3 columns)
- Bold colors, heavy inks
- More realistic proportions
- Dynamic action poses
- Speech bubbles with thick borders
- Typical panel counts: 6-9 per page
""",
}

CHARACTER_EXTRACT_PROMPT = """
Analyze this story and extract ALL named characters.
For each character, create a detailed visual description for AI image generation.

Return JSON in this exact format:
{
  "characters": [
    {
      "name": "Character Name",
      "aliases": ["nickname1", "he/she/they"],
      "role": "protagonist | antagonist | supporting | minor",
      "age_range": "teen | young adult | adult | elderly",
      "gender_presentation": "description",
      "physical_description": "detailed visual: height, build, hair color/style, eye color, skin tone, distinguishing features",
      "clothing_style": "typical outfit description for image prompts",
      "personality_traits": ["trait1", "trait2"],
      "first_appearance_chapter": "chapter/section where they appear",
      "image_prompt_base": "concise image generation prompt capturing their look, suitable for SDXL/FLUX. Example: 'young woman, long silver hair, violet eyes, pale skin, wearing a blue academy uniform, serious expression'"
    }
  ]
}
"""

SCENE_BREAKDOWN_PROMPT = """
Break this story section into comic panels/pages.
Create {panel_target} panels total, arranged into pages of {panels_per_page} panels each.

For {style} style comics.
{style_guidance}

Return JSON in this exact format:
{{
  "pages": [
    {{
      "page_number": 1,
      "layout": "splash | grid_2x3 | grid_3x3 | vertical_strip | irregular",
      "panels": [
        {{
          "panel_number": 1,
          "size": "small | medium | large | splash",
          "scene_description": "What's happening in this panel",
          "setting": "location and time of day",
          "characters_present": ["Character Name"],
          "character_actions": {{
            "Character Name": "what they are doing and their pose/expression"
          }},
          "dialogue": [
            {{
              "speaker": "Character Name",
              "text": "speech text",
              "bubble_style": "speech | thought | shout | whisper"
            }}
          ],
          "narration": "any caption/narration box text",
          "sfx": ["BOOM", "CRASH"],
          "camera_angle": "wide | medium | close-up | extreme-close-up | bird's-eye | worm's-eye | dutch-angle",
          "lighting": "dramatic shadows | bright daylight | dim candlelight | neon glow | etc",
          "mood": "tense | joyful | sorrowful | mysterious | action | romantic",
          "image_generation_prompt": "detailed prompt for AI image generation of this exact panel. Include art style, characters, setting, lighting, mood. Example: 'manga style, young silver-haired girl in school uniform standing at rooftop edge, wind blowing her hair, dramatic sunset behind her, looking determined, cinematic composition'",
          "negative_prompt": "blurry, bad anatomy, text, watermark, deformed"
        }}
      ]
    }}
  ],
  "story_arc_notes": "brief description of the emotional journey across these panels"
}}
"""


class StoryParser:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def extract_characters(self, story_text: str) -> dict[str, Any]:
        """Extract characters from story with visual descriptions."""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=PARSE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"{CHARACTER_EXTRACT_PROMPT}\n\nSTORY:\n{story_text[:50000]}",
                }
            ],
        )
        text = next(b.text for b in response.content if b.type == "text")
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    def parse_scenes(
        self,
        story_text: str,
        style: ComicStyle,
        characters: list[dict],
        chapters: int = 1,
        panels_per_page: int = None,
    ) -> dict[str, Any]:
        """Parse story into structured panel/page data."""
        if panels_per_page is None:
            panels_per_page = {"manga": 6, "manhwa": 4, "western": 6}[style.value]

        # Aim for roughly 1 panel per 150-200 words, capped sensibly
        word_count = len(story_text.split())
        panel_target = max(6, min(int(word_count / 150), 80))

        char_context = "\n".join(
            f"- {c['name']}: {c['image_prompt_base']}" for c in characters
        )

        prompt = (
            SCENE_BREAKDOWN_PROMPT.format(
                panel_target=panel_target,
                panels_per_page=panels_per_page,
                style=style.value.upper(),
                style_guidance=STYLE_GUIDANCE[style],
            )
            + f"\n\nCHARACTERS IN THIS STORY:\n{char_context}"
            + f"\n\nSTORY:\n{story_text[:60000]}"
        )

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=PARSE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    def refine_panel_prompt(
        self,
        panel: dict,
        characters: list[dict],
        style: ComicStyle,
        prev_panel_desc: str = "",
    ) -> str:
        """Build a final, high-quality image prompt for a panel."""
        char_descriptions = {c["name"]: c["image_prompt_base"] for c in characters}

        style_prefix = {
            ComicStyle.MANGA: "manga panel, black and white, ink illustration, screen tones, dramatic linework",
            ComicStyle.MANHWA: "manhwa panel, full color, clean digital art, soft coloring, webtoon style",
            ComicStyle.WESTERN: "western comic panel, full color, bold inks, dynamic illustration, superhero comic style",
        }[style]

        characters_in_panel = panel.get("characters_present", [])
        char_prompts = []
        for name in characters_in_panel:
            if name in char_descriptions:
                action = panel.get("character_actions", {}).get(name, "")
                char_prompts.append(f"{char_descriptions[name]}, {action}".strip(", "))

        components = [
            style_prefix,
            panel.get("image_generation_prompt", ""),
            ", ".join(char_prompts) if char_prompts else "",
            panel.get("setting", ""),
            panel.get("lighting", ""),
            f"camera: {panel.get('camera_angle', 'medium shot')}",
            f"mood: {panel.get('mood', 'neutral')}",
            "high quality, detailed, professional comic art",
        ]
        return ", ".join(c for c in components if c)
