"""
Veo Video Generator — Vertex AI Veo 3 Fast via REST API
"""
import os, time, base64, logging, requests, subprocess, tempfile
import google.auth, google.auth.transport.requests
from utils.config import config

log = logging.getLogger(__name__)

STYLE_PREFIX = (
    "Cinematic vertical 9:16 smartphone video, photorealistic, "
    "warm dramatic lighting, shallow depth of field, "
    "social media storytelling style. "
)


class VeoGenerator:
    def __init__(self):
        os.makedirs(f"{config.OUTPUT_DIR}/videos", exist_ok=True)

    def generate_all_parts(self, script: dict, story_id: str) -> list[str]:
        video_paths = []
        last_frame_b64 = None
        for part in script["parts"]:
            idx = part["index"]
            prompt = STYLE_PREFIX + part["veo_prompt"]
            log.info("  Generating Veo clip %d/4...", idx)
            video_bytes = self._generate_clip(prompt, last_frame_b64)
            out_path = f"{config.OUTPUT_DIR}/videos/{story_id}_part{idx}.mp4"
            with open(out_path, "wb") as f:
                f.write(video_bytes)
            log.info("    Saved: %s (%d KB)", out_path, len(video_bytes) // 1024)
            last_frame_b64 = self._extract_last_frame_b64(out_path)
            video_paths.append(out_path)
        return video_paths

    def _get_token(self) -> str:
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token

    def _generate_clip(self, prompt: str, last_frame_b64: str = None) -> bytes:
        token = self._get_token()
        project = config.GOOGLE_CLOUD_PROJECT
        location = config.GOOGLE_CLOUD_LOCATION
        model = config.VEO_MODEL

        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/publishers/google/models/{model}:predictLongRunning"
        )

        instance = {"prompt": prompt}
        if last_frame_b64:
            instance["image"] = {
                "bytesBase64Encoded": last_frame_b64,
                "mimeType": "image/jpeg",
            }

        body = {
            "instances": [instance],
            "parameters": {
                "aspectRatio": config.VEO_ASPECT_RATIO,
                "durationSeconds": config.VEO_DURATION,
                "sampleCount": 1,
