"""
Veo Video Generator — Vertex AI Veo 2 via REST API
Generates 4 consistent 8-second clips, one per story part.
Uses direct REST calls (no SDK VideoGenerationModel needed).
"""
import os
import time
import base64
import logging
import requests
import subprocess
import tempfile
import google.auth
import google.auth.transport.requests
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
            log.info("    Prompt: %s", prompt[:100])

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
        req = google.auth.transport.requests.Request()
        creds.refresh(req)
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
                "enhancePrompt": True,
                "personGeneration": "allow_adult",
            },
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        log.info("    Submitting Veo request...")
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        operation_name = resp.json()["name"]
        log.info("    Operation: %s", operation_name)

        return self._poll_operation(operation_name)

    def _poll_operation(self, operation_name: str, max_wait: int = 300) -> bytes:
        project = config.GOOGLE_CLOUD_PROJECT
        location = config.GOOGLE_CLOUD_LOCATION

        poll_url = (
            f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
        )

        deadline = time.time() + max_wait
        interval = 10

        while time.time() < deadline:
            time.sleep(interval)
            token = self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(poll_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("done"):
                if "error" in data:
                    raise RuntimeError(f"Veo generation failed: {data['error']}")

                samples = (
                    data.get("response", {})
                    .get("generateVideoResponse", {})
                    .get("generatedSamples", [])
                )
                if not samples:
                    raise RuntimeError("Veo returned no video samples")

                return base64.b64decode(samples[0]["video"]["bytesBase64Encoded"])

            elapsed = time.time() - (deadline - max_wait)
            log.info("    Still generating... (%.0fs elapsed)", elapsed)
            interval = min(interval + 5, 30)

        raise TimeoutError(f"Veo clip timed out after {max_wait}s")

    def _extract_last_frame_b64(self, video_path: str):
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
            cmd = [
                "ffmpeg", "-y", "-sseof", "-0.1",
                "-i", video_path, "-vframes", "1", "-q:v", "2", tmp_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0:
                with open(tmp_path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
        except Exception as e:
            log.warning("Could not extract last frame: %s", e)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        return None
