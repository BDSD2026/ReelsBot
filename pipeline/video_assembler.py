"""
Video Assembler — stitches 4 Veo clips + TTS audio + burned-in captions
into one final 9:16 Reel MP4 (~32 seconds)
"""
import os, subprocess, logging
from utils.config import config

log = logging.getLogger(__name__)


class VideoAssembler:
    def __init__(self):
        os.makedirs(f"{config.OUTPUT_DIR}/videos", exist_ok=True)

    def build(self, story: dict, script: dict, voiceover: dict, video_parts: list[str]) -> str:
        """
        video_parts: list of 4 MP4 paths (from VeoGenerator)
        Returns: path to final assembled Reel
        """
        story_id = story["id"]

        # 1. Build SRT from combined word timestamps
        srt_path = self._build_srt(voiceover["combined_word_timestamps"], story_id)

        # 2. Concatenate 4 clips into one silent video
        concat_path = self._concat_clips(video_parts, story_id)

        # 3. Burn captions + add audio → final output
        output_path = f"{config.OUTPUT_DIR}/videos/{story_id}_final.mp4"
        self._ffmpeg_final(
            video_path=concat_path,
            audio_path=voiceover["combined_audio_path"],
            srt_path=srt_path,
            output_path=output_path,
            duration=voiceover["total_duration"] + 0.5,
        )

        log.info("  Final reel: %s", output_path)
        return output_path

    # ── Concat 4 clips ────────────────────────────────────────────────

    def _concat_clips(self, paths: list[str], story_id: str) -> str:
        list_file = f"{config.OUTPUT_DIR}/videos/{story_id}_concat.txt"
        with open(list_file, "w") as f:
            for p in paths:
                f.write(f"file '{os.path.abspath(p)}'\n")

        out = f"{config.OUTPUT_DIR}/videos/{story_id}_concat.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an", out,
        ]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed:\n{r.stderr.decode()[-1000:]}")
        log.info("  4 clips concatenated → %s", out)
        return out

    # ── Caption SRT ───────────────────────────────────────────────────

    def _build_srt(self, word_timestamps: list[dict], story_id: str) -> str:
        srt_path = f"{config.OUTPUT_DIR}/videos/{story_id}.srt"
        chunk = config.WORDS_PER_CAPTION
        chunks = []
        for i in range(0, len(word_timestamps), chunk):
            group = word_timestamps[i: i + chunk]
            text = " ".join(w["word"] for w in group).upper()
            chunks.append((group[0]["start"], group[-1]["end"], text))

        with open(srt_path, "w") as f:
            for idx, (start, end, text) in enumerate(chunks, 1):
                f.write(f"{idx}\n{self._t(start)} --> {self._t(end)}\n{text}\n\n")
        return srt_path

    def _t(self, s: float) -> str:
        h, m = int(s // 3600), int((s % 3600) // 60)
        sec, ms = int(s % 60), int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    # ── Final FFmpeg pass ─────────────────────────────────────────────

    def _ffmpeg_final(self, video_path, audio_path, srt_path, output_path, duration):
        W, H = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
        fs = config.FONT_SIZE
        srt_esc = srt_path.replace("\\", "/").replace(":", "\\:")

        vf = (
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"subtitles='{srt_esc}':"
            f"force_style='FontName=Montserrat,FontSize={fs},"
            f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            f"Outline=3,Alignment=2,MarginV=140,Bold=1,Shadow=2'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-t", str(duration),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-movflags", "+faststart",
            "-r", str(config.VIDEO_FPS),
            output_path,
        ]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"FFmpeg final pass failed:\n{r.stderr.decode()[-2000:]}")
