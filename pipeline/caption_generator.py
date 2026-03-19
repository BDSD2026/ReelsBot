"""Caption Generator — Gemini writes Instagram caption + Pillow makes thumbnail"""
import os
import textwrap
import logging
import google.generativeai as genai
from utils.config import config

log = logging.getLogger(__name__)

CAPTION_PROMPT = """Write an Instagram caption for a Reel based on this AITA story.
Format: Line 1: hook (no emoji). Blank line. 2-3 punchy sentences. Blank line. CTA with emoji. Blank line. 20-25 hashtags.
Story title: {title}
Summary: {summary}
Output only the caption."""

class CaptionGenerator:
    def __init__(self):
        genai.configure()
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            generation_config={"temperature": 0.8, "max_output_tokens": 500},
        )
        os.makedirs(f"{config.OUTPUT_DIR}/thumbnails", exist_ok=True)

    def generate(self, story: dict, script: dict) -> str:
        summary = " ".join(p["text"] for p in script["parts"][:2])
        prompt = CAPTION_PROMPT.format(title=story["title"], summary=summary)
        response = self.model.generate_content(prompt)
        caption = response.text.strip()
        log.info("  Caption: %d chars", len(caption))
        return caption

    def make_thumbnail(self, story: dict) -> str:
        try:
            from PIL import Image, ImageDraw, ImageFont
            W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
            thumb_path = f"{config.OUTPUT_DIR}/thumbnails/{story['id']}.jpg"
            img = Image.new("RGB", (W, H), color=(12, 8, 24))
            draw = ImageDraw.Draw(img)
            for y in range(H):
                intensity = int(15 + (y / H) * 60)
                draw.line([(0, y), (W, y)], fill=(intensity // 2, intensity // 4, intensity))
            try:
                font_small = ImageFont.truetype(config.FONT_PATH, 52)
                font_large = ImageFont.truetype(config.FONT_PATH, 88)
            except Exception:
                font_small = ImageFont.load_default()
                font_large = font_small
            draw.text((W // 2, 180), "AITA?", font=font_small, fill=(200, 100, 255), anchor="mm")
            wrapped = textwrap.fill(story["title"][:90], width=20)
            draw.text((W // 2, H // 2 - 80), wrapped, font=font_large, fill=(255, 255, 255),
                      anchor="mm", align="center", stroke_width=5, stroke_fill=(0, 0, 0))
            draw.text((W // 2, H - 220), "Comment your verdict 👇",
                      font=font_small, fill=(255, 200, 60), anchor="mm")
            img.save(thumb_path, "JPEG", quality=92)
            log.info("  Thumbnail: %s", thumb_path)
            return thumb_path
        except Exception as e:
            log.warning("Thumbnail failed: %s", e)
            return ""
