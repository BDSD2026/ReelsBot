"""Story Selector — uses Gemini via google-generativeai SDK"""
import json
import logging
import google.generativeai as genai
from utils.config import config

log = logging.getLogger(__name__)

SELECTOR_PROMPT = """You are a viral short-form video producer for Instagram Reels.
Pick ONE story from the list below that will get the most views as a 60-second Reel.
Score on: hook potential, emotional punch, narrative clarity, relatability, controversy.
Respond ONLY with valid JSON, no markdown fences:
{"selected_id": "<id>", "reason": "<one sentence>", "hook": "<opening line, max 12 words>"}"""

class StorySelector:
    def __init__(self):
        genai.configure()
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.3, "max_output_tokens": 300},
        )

    def pick_best(self, candidates: list[dict]) -> dict:
        if len(candidates) == 1:
            return candidates[0]
        lines = []
        for c in candidates[:10]:
            lines.append(f"ID: {c['id']}\nTitle: {c['title']}\nWords: {c['word_count']}\nPreview: {c['body'][:250]}...\n")
        prompt = SELECTOR_PROMPT + "\n\nSTORIES:\n---\n" + "\n---\n".join(lines)
        response = self.model.generate_content(prompt)
        raw = response.text.strip().strip("```json").strip("```").strip()
        result = json.loads(raw)
        selected_id = result["selected_id"]
        story = next((c for c in candidates if c["id"] == selected_id), candidates[0])
        story["hook"] = result.get("hook", "")
        log.info("  Gemini selected: %s — %s", selected_id, result.get("reason", ""))
        return story
