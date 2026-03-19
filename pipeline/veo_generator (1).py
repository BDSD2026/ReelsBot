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

    def generate_all_parts(self, script, story_id):
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

    def _get_token(self):
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token

    def _generate_clip(self, prompt, last_frame_b64=None):
        token = self._get_token()
        project = config.GOOGLE_CLOUD_PROJECT
        location = config.GOOGLE_CLOUD_LOCATION
        model = config.VEO_MODEL

        submit_url = (
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
        resp = requests.post(submit_url, json=body, headers=headers, timeout=30)
        if not resp.ok:
            log.error("Veo error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()

        result = resp.json()
        log.info("    Submit response keys: %s", list(result.keys()))

        operation_name = result.get("name", "")
        log.info("    Operation name: %s", operation_name)

        return self._poll_operation(operation_name, token)

    def _poll_operation(self, operation_name, initial_token, max_wait=600):
        location = config.GOOGLE_CLOUD_LOCATION

        # The correct poll endpoint for Veo long-running operations
        # strips the publishers/google/models/MODEL/operations/ID
        # and uses the global operations endpoint
        op_id = operation_name.split("/operations/")[-1]
        project = config.GOOGLE_CLOUD_PROJECT

        urls_to_try = [
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/operations/{op_id}",
            f"https://us-central1-aiplatform.googleapis.com/v1/{operation_name}",
            f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/operations/{op_id}",
        ]

        deadline = time.time() + max_wait
        interval = 15
        url_idx = 0
        poll_url = urls_to_try[0]

        log.info("    Polling: %s", poll_url)

        while time.time() < deadline:
            time.sleep(interval)
            token = self._get_token()
            resp = requests.get(
                poll_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=15
            )
            log.info("    Poll %s -> %s", poll_url, resp.status_code)

            if resp.status_code in (404, 400) and url_idx < len(urls_to_try) - 1:
                url_idx += 1
                poll_url = urls_to_try[url_idx]
                log.info("    Trying next URL: %s", poll_url)
                continue

            if not resp.ok:
                log.error("Poll error body: %s", resp.text[:500])
            resp.raise_for_status()

            data = resp.json()
            log.info("    done=%s keys=%s", data.get("done"), list(data.keys()))

            if data.get("done"):
                if "error" in data:
                    raise RuntimeError(f"Veo failed: {data['error']}")

                response = data.get("response", {})
                log.info("    Response keys: %s", list(response.keys()))

                samples = response.get("generateVideoResponse", {}).get("generatedSamples", [])
                if samples:
                    video = samples[0].get("video", {})
                    log.info("    Video keys: %s", list(video.keys()))
                    if video.get("bytesBase64Encoded"):
                        return base64.b64decode(video["bytesBase64Encoded"])
                    if video.get("uri"):
                        return self._download_gcs(video["uri"])

                log.error("Full done response: %s", str(data)[:2000])
                raise RuntimeError("Could not extract video bytes from response")

            interval = min(interval + 10, 30)

        raise TimeoutError(f"Veo timed out after {max_wait}s")

    def _download_gcs(self, gcs_uri):
        path = gcs_uri.replace("gs://", "")
        bucket, obj = path.split("/", 1)
        url = f"https://storage.googleapis.com/{bucket}/{obj}"
        token = self._get_token()
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120
        )
        resp.raise_for_status()
        return resp.content

    def _extract_last_frame_b64(self, video_path):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = tmp.name
            cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", video_path,
                   "-vframes", "1", "-q:v", "2", tmp_path]
            result = subprocess.run(cmd, capture_output=True, timeout=15)
            if result.returncode == 0:
                with open(tmp_path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
        except Exception as e:
            log.warning("Could not extract last frame: %s", e)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        return None
