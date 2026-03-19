#!/usr/bin/env python3
"""
Stories → Instagram Reels — GitHub Actions Pipeline
Reads from Google Sheet → Gemini picks story → script → TTS → Veo 2 → video
Saves output as GitHub Actions artifacts (downloadable from browser)
"""

import sys
import os
import logging
from datetime import datetime
from pipeline.sheets_scraper import GoogleSheetsScraper
from pipeline.selector import StorySelector
from pipeline.scriptwriter import ScriptWriter
from pipeline.voiceover import VoiceoverGenerator
from pipeline.veo_generator import VeoGenerator
from pipeline.video_assembler import VideoAssembler
from pipeline.caption_generator import CaptionGenerator
from utils.database import Database
from utils.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def run_pipeline():
    log.info("=" * 60)
    log.info(f"ReelsBot — {datetime.now().isoformat()}")
    log.info("=" * 60)

    db = Database()

    try:
        log.info("STEP 1: Reading stories from Google Sheet...")
        candidates = GoogleSheetsScraper().fetch_candidates()
        seen_ids = db.get_used_post_ids()
        candidates = [p for p in candidates if p["id"] not in seen_ids]
        log.info(f"  → {len(candidates)} unposted stories")
        if not candidates:
            log.warning("No new stories — add more rows to your Google Sheet.")
            return

        log.info("STEP 2: Gemini selecting best story...")
        story = StorySelector().pick_best(candidates)
        log.info(f"  → '{story['title'][:70]}'")

        log.info("STEP 3: Gemini writing 4-part script...")
        script = ScriptWriter().generate(story)

        log.info("STEP 4: Google TTS generating voiceovers...")
        audio_parts = VoiceoverGenerator().generate_all_parts(script, story["id"])

        log.info("STEP 5: Veo 2 generating 4 video clips...")
        video_paths = VeoGenerator().generate_all_parts(script, story["id"])

        log.info("STEP 6: Assembling final video...")
        final_video = VideoAssembler().build(
            story=story, script=script,
            video_paths=video_paths, audio_parts=audio_parts,
        )

        log.info("STEP 7: Generating caption and thumbnail...")
        cap_gen = CaptionGenerator()
        caption = cap_gen.generate(story, script)
        thumbnail = cap_gen.make_thumbnail(story)

        # Save outputs to ./output/ — GitHub Actions uploads this as artifact
        import shutil
        os.makedirs("output", exist_ok=True)
        shutil.copy2(final_video, "output/reel.mp4")
        if thumbnail and os.path.exists(thumbnail):
            shutil.copy2(thumbnail, "output/thumbnail.jpg")
        with open("output/caption.txt", "w") as f:
            f.write(caption)
        with open("output/story_info.txt", "w") as f:
            f.write(f"Title: {story['title']}\nDate: {datetime.now().isoformat()}\n")
        for i, p in enumerate(video_paths, 1):
            shutil.copy2(p, f"output/clip_part{i}.mp4")

        # Save DB so used stories persist across runs (committed back to repo)
        if os.path.exists(config.DB_PATH) and config.DB_PATH != "pipeline.db":
            shutil.copy2(config.DB_PATH, "pipeline.db")

        db.mark_used(story["id"], post_id="github_actions",
                     title=story["title"], subreddit=story["subreddit"])

        log.info("")
        log.info("=" * 60)
        log.info("✅  REEL READY!")
        log.info(f"  Title: {story['title'][:60]}")
        log.info("  Download from GitHub Actions → your workflow run → Artifacts")
        log.info("  Files: reel.mp4 · thumbnail.jpg · caption.txt")
        log.info("=" * 60)

    except Exception as e:
        log.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
