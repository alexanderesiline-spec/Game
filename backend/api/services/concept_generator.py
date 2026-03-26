"""
Concept Generator — interactive Q&A to build a story concept from scratch.

Flow:
1. User writes a rough idea
2. Claude asks focused questions (setting, characters, tone, conflict)
3. After enough detail, Claude generates a full story outline
4. User can refine or accept → flows into story parsing
"""

import json
import anthropic
from typing import Any


CONCEPT_SYSTEM = """You are a creative writing consultant who helps people develop comic/manga story concepts.
Your goal is to gather enough detail to generate a compelling story that can be turned into a comic.

You ask smart, targeted questions one or two at a time — never overwhelming the user.
You are enthusiastic, creative, and encouraging.
You understand manga, manhwa, and western comic storytelling tropes and genres.

IMPORTANT: When you have gathered enough information (usually after 3-5 exchanges),
generate a complete story outline using the STORY_COMPLETE signal."""

INITIAL_ANALYSIS_PROMPT = """The user has given you this initial concept:

"{concept}"

Your job:
1. Briefly acknowledge what's exciting about this concept (1-2 sentences)
2. Ask 1-2 focused questions to develop it further

Focus on the MOST IMPORTANT gaps. Good questions cover:
- Setting (world, era, location)
- Main character (who they are, their flaw or desire)
- Core conflict (what's the central struggle)
- Tone (dark/gritty vs light/fun vs emotional)
- Genre hooks (romance? action? mystery? isekai? slice-of-life?)

Do NOT ask about the comic style/format — that's handled separately.
Keep your response concise and conversational."""

FOLLOW_UP_PROMPT = """Continue the concept development conversation.

Previous messages:
{history}

User just said: "{message}"

Either:
A) If you need 1-2 more pieces of info, ask focused follow-up questions.
B) If you have enough to write a solid story (setting, protagonist, conflict, tone),
   output the complete story outline using this EXACT format:

STORY_COMPLETE
{{
  "title": "Story Title",
  "tagline": "One-line hook",
  "genre": ["genre1", "genre2"],
  "tone": "description of overall tone",
  "setting": {{
    "world": "world description",
    "era": "time period",
    "key_locations": ["location1", "location2"]
  }},
  "characters": [
    {{
      "name": "Name",
      "role": "protagonist/antagonist/etc",
      "description": "visual + personality description",
      "motivation": "what they want",
      "arc": "how they change"
    }}
  ],
  "story_outline": [
    {{
      "chapter": 1,
      "title": "Chapter title",
      "summary": "What happens",
      "key_scenes": ["scene1", "scene2"],
      "emotional_beat": "feeling this chapter evokes"
    }}
  ],
  "themes": ["theme1", "theme2"],
  "prose_draft": "A 500-800 word prose version of Chapter 1 that captures the opening of the story with vivid detail, dialogue, and atmosphere. This will be turned into comic panels."
}}
END_STORY_COMPLETE

Make the prose_draft genuinely compelling — this is what gets turned into panels.
"""


class ConceptGenerator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def start_session(self, initial_concept: str) -> dict[str, Any]:
        """Process the user's initial concept and return first questions."""
        prompt = INITIAL_ANALYSIS_PROMPT.format(concept=initial_concept)
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            system=CONCEPT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return {
            "reply": text,
            "is_complete": False,
            "story_data": None,
            "messages": [
                {"role": "user", "content": initial_concept},
                {"role": "assistant", "content": text},
            ],
        }

    def continue_session(
        self, messages: list[dict], user_message: str
    ) -> dict[str, Any]:
        """Continue the Q&A session with a user reply."""
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in messages
        )
        prompt = FOLLOW_UP_PROMPT.format(
            history=history_text, message=user_message
        )

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=CONCEPT_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(b.text for b in response.content if b.type == "text")

        updated_messages = messages + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": text},
        ]

        if "STORY_COMPLETE" in text:
            story_data = self._extract_story_data(text)
            return {
                "reply": self._extract_reply_before_signal(text),
                "is_complete": True,
                "story_data": story_data,
                "messages": updated_messages,
            }

        return {
            "reply": text,
            "is_complete": False,
            "story_data": None,
            "messages": updated_messages,
        }

    def _extract_story_data(self, text: str) -> dict | None:
        try:
            start = text.index("STORY_COMPLETE") + len("STORY_COMPLETE")
            end = text.index("END_STORY_COMPLETE")
            json_str = text[start:end].strip()
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError):
            return None

    def _extract_reply_before_signal(self, text: str) -> str:
        if "STORY_COMPLETE" in text:
            before = text[:text.index("STORY_COMPLETE")].strip()
            return before if before else "Your story concept is ready!"
        return text
