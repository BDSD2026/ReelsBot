"""Script Writer — Gemini splits story into 4 timed parts with Veo prompts"""
import json
import logging
import google.generativeai as genai
from utils.config import config

log = logging.getLogger(__name__)

SCRIPT_PROMPT = """You are a viral Instagram Reels scriptwriter.
Rewrite the Reddit story below as a spoken script split into EXACTLY 4 parts.
Each part ~20-25 words, read aloud over an 8-second video clip.
Part 1: Hook + setup. Part 2: Tension. Part 3: Escalation. Part 4: Outcome + CTA question.
Natural spoken tone, short sentences, no stage directions.
Respond ONLY with valid JSON (no markdown fences):
{"parts": [{"index": 1, "text": "<spoken narration>", "veo_prompt": "<cinematic scene, 9:16 vertical, photorealistic>"}, ...4 parts...], "full_text": "<all 4 joined>", "duration_estimate": <int seconds>}"""

class ScriptWriter:
    def __init__(self):
        genai.configure()
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.7, "max_output_tokens": 1000},
        )

    def generate(self, story: dict) -> dict:
        hook = story.get("hook", "")
        prompt = f"{SCRIPT_PROMPT}\n\nHOOK: {hook}\nTITLE: {story['title']}\nSTORY:\n{story['body']}"
        response = self.model.generate_content(prompt)
        raw = response.text.strip().strip("```json").strip("```").strip()
        script = json.loads(raw)
        assert len(script["parts"]) == 4, "Expected exactly 4 parts"
        word_count = len(script["full_text"].split())
        script["duration_estimate"] = script.get("duration_estimate", int(word_count / 2.5))
        log.info("  Script: 4 parts, ~%d words, ~%ds", word_count, script["duration_estimate"])
        return script
