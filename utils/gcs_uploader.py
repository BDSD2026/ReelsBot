"""
Google Cloud Storage uploader — saves finished Reel files to GCS
so you can download them from the browser.
"""
import os
import logging
from google.cloud import storage
from utils.config import config

log = logging.getLogger(__name__)


class GCSUploader:
    def __init__(self):
        self.client = storage.Client()
        self.bucket_name = config.GCS_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Create the GCS bucket if it doesn't exist."""
        try:
            self.bucket = self.client.get_bucket(self.bucket_name)
        except Exception:
            log.info("Creating GCS bucket: %s", self.bucket_name)
            self.bucket = self.client.create_bucket(
                self.bucket_name,
                location="us-central1",
            )

    def upload(self, local_path: str, gcs_path: str) -> str:
        """Upload a file and return its public URL."""
        if not local_path or not os.path.exists(local_path):
            log.warning("Skipping upload — file not found: %s", local_path)
            return ""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_filename(local_path)
        url = f"https://storage.cloud.google.com/{self.bucket_name}/{gcs_path}"
        log.info("  Uploaded: %s → %s", local_path, url)
        return url

    def upload_text(self, text: str, gcs_path: str) -> str:
        """Upload a text string as a file."""
        blob = self.bucket.blob(gcs_path)
        blob.upload_from_string(text, content_type="text/plain")
        url = f"https://storage.cloud.google.com/{self.bucket_name}/{gcs_path}"
        log.info("  Uploaded text: %s", url)
        return url
