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
        if not resp.ok:
            log.error("Veo submit error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        operation_name = resp.json()["name"]
        log.info("    Operation: %s", operation_name)
        return self._poll_operation(operation_name)

    def _poll_operation(self, operation_name: str, max_wait: int = 600) -> bytes:
        location = config.GOOGLE_CLOUD_LOCATION
        poll_url = f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
        deadline = time.time() + max_wait
        interval = 15

        while time.time() < deadline:
            time.sleep(interval)
            token = self._get_token()
            resp = requests.get(poll_url,
                                headers={"Authorization": f"Bearer {token}"},
                                timeout=15)
            resp.raise_for_status()
            data = resp.json()
            log.info("    Polling... done=%s", data.get("done"))

            if data.get("done"):
                if "error" in data:
                    raise RuntimeError(f"Veo failed: {data['error']}")

                response = data.get("response", {})

                # Try inline bytes first
                samples = response.get("generateVideoResponse", {}).get("generatedSamples", [])
                if samples:
                    video = samples[0].get("video", {})
                    if video.get("bytesBase64Encoded"):
                        return base64.b64decode(video["bytesBase64Encoded"])
                    # GCS URI fallback
                    if video.get("uri"):
                        return self._download_gcs(video["uri"])

                # Veo 3 may nest differently
                for key in ["videos", "predictions"]:
                    items = response.get(key, [])
                    if items:
                        item = items[0]
                        if isinstance(item, dict):
                            b64 = item.get("bytesBase64Encoded") or item.get("video", {}).get("bytesBase64Encoded")
                            if b64:
                                return base64.b64decode(b64)
                            uri = item.get("gcsUri") or item.get("uri")
                            if uri:
                                return self._download_gcs(uri)
