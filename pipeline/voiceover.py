"""
Voiceover — Google Cloud Text-to-Speech Neural2
Generates one MP3 per story part + one combined MP3 for the full reel.
Returns word-level timestamps via the timepoint API.
"""
import os, base64, logging
from google.cloud import texttospeech
from utils.config import config

log = logging.getLogger(__name__)


class VoiceoverGenerator:
    def __init__(self):
        os.makedirs(f"{config.OUTPUT_DIR}/audio", exist_ok=True)
        # Picks up GOOGLE_APPLICATION_CREDENTIALS from env automatically
        self.client = texttospeech.TextToSpeechClient()

    def generate(self, script: dict, story_id: str) -> dict:
        """
        Generate one audio file per part + a combined full audio.
        Returns:
        {
            "parts": [
                {"part": 1, "audio_path": "...", "duration": float,
                 "word_timestamps": [...] },
                ...
            ],
            "combined_audio_path": "...",
            "total_duration": float
        }
        """
        parts_out = []
        total_duration = 0.0

        for part in script["parts"]:
            log.info("  Generating voiceover for part %d...", part["part"])
            result = self._synthesize(
                text=part["text"],
                out_path=f"{config.OUTPUT_DIR}/audio/{story_id}_part{part['part']}.mp3",
            )
            parts_out.append({
                "part": part["part"],
                "audio_path": result["path"],
                "duration": result["duration"],
                "word_timestamps": result["word_timestamps"],
            })
            total_duration += result["duration"]

        # Also make a single combined audio for the assembled reel
        combined_text = script["full_text"]
        combined = self._synthesize(
            text=combined_text,
            out_path=f"{config.OUTPUT_DIR}/audio/{story_id}_combined.mp3",
        )

        log.info("  Total audio duration: %.1fs", combined["duration"])
        return {
            "parts": parts_out,
            "combined_audio_path": combined["path"],
            "total_duration": combined["duration"],
            "combined_word_timestamps": combined["word_timestamps"],
        }

    def _synthesize(self, text: str, out_path: str) -> dict:
        voice = texttospeech.VoiceSelectionParams(
            language_code=config.TTS_LANGUAGE_CODE,
            name=config.TTS_VOICE_NAME,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=config.TTS_SPEAKING_RATE,
            pitch=config.TTS_PITCH,
            effects_profile_id=["headphone-class-device"],
        )
        # Use SSML to get timepoints for word-level timestamps
        ssml = self._text_to_ssml(text)
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml)

        try:
            resp = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config,
                enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK],
            )
            word_timestamps = self._parse_timepoints(resp.timepoints, text)
        except Exception as e:
            # Fallback: synthesize without timepoints
            log.warning("  Timepoints unavailable (%s) — falling back to plain TTS", e)
            synthesis_input = texttospeech.SynthesisInput(text=text)
            resp = self.client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            word_timestamps = self._estimate_timestamps(text)

        with open(out_path, "wb") as f:
            f.write(resp.audio_content)

        duration = self._estimate_duration(len(resp.audio_content))
        if word_timestamps:
            duration = max(duration, word_timestamps[-1]["end"])

        return {"path": out_path, "duration": duration, "word_timestamps": word_timestamps}

    def _text_to_ssml(self, text: str) -> str:
        """Wrap each word in an SSML mark so we get timepoints back."""
        import html
        words = text.split()
        marked = " ".join(
            f'<mark name="w{i}"/>{html.escape(w)}' for i, w in enumerate(words)
        )
        return f"<speak>{marked}</speak>"

    def _parse_timepoints(self, timepoints, text: str) -> list[dict]:
        words = text.split()
        result = []
        for i, tp in enumerate(timepoints):
            start = tp.time_seconds
            end = timepoints[i + 1].time_seconds if i + 1 < len(timepoints) else start + 0.4
            word_idx = int(tp.mark_name.replace("w", ""))
            if word_idx < len(words):
                result.append({"word": words[word_idx], "start": start, "end": end})
        return result

    def _estimate_timestamps(self, text: str) -> list[dict]:
        """Rough fallback: assume 2.5 words/second."""
        words = text.split()
        ts = []
        t = 0.0
        for w in words:
            dur = 0.4
            ts.append({"word": w, "start": t, "end": t + dur})
            t += dur
        return ts

    def _estimate_duration(self, byte_count: int) -> float:
        # MP3 at ~128kbps
        return byte_count / (128_000 / 8)
