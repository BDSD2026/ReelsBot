"""
Voiceover Generator — Google Cloud Text-to-Speech Neural2
Generates one MP3 per script part.
"""
import os
import logging
from google.cloud import texttospeech
from utils.config import config

log = logging.getLogger(__name__)


class VoiceoverGenerator:
    def __init__(self):
        os.makedirs(f"{config.OUTPUT_DIR}/audio", exist_ok=True)
        self.client = texttospeech.TextToSpeechClient()

    def generate_all_parts(self, script: dict, story_id: str) -> list[dict]:
        results = []
        for part in script["parts"]:
            result = self._synthesize_part(part, story_id)
            results.append(result)
            log.info("  Part %d audio: %.1fs → %s",
                     part["index"], result["duration"], result["audio_path"])
        return results

    def _synthesize_part(self, part: dict, story_id: str) -> dict:
        idx = part["index"]
        text = part["text"]
        audio_path = f"{config.OUTPUT_DIR}/audio/{story_id}_part{idx}.mp3"

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=config.TTS_LANGUAGE,
            name=config.TTS_VOICE,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=config.TTS_SPEAKING_RATE,
            pitch=config.TTS_PITCH,
        )

        response = self.client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config,
        )

        with open(audio_path, "wb") as f:
            f.write(response.audio_content)

        word_count = len(text.split())
        duration = word_count / (config.TTS_SPEAKING_RATE * 2.5)

        return {
            "part_index": idx,
            "audio_path": audio_path,
            "duration": duration,
            "text": text,
        }
