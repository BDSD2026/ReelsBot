"""Config — reads from environment variables (set as GitHub Secrets)"""
import os

class Config:
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "sixth-utility-383712")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")

    # Google Sheets
    SHEETS_ID: str = os.getenv("SHEETS_ID", "18c3HSNWF75HHohUUlGhZMSo_cceLE9TJ0B_1nRUR3xE")
    SHEETS_MODE: str = os.getenv("SHEETS_MODE", "public")
    MIN_WORDS: int = int(os.getenv("MIN_WORDS", "100"))
    MAX_WORDS: int = int(os.getenv("MAX_WORDS", "800"))

    # Gemini
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    # Veo 2
    VEO_MODEL: str = os.getenv("VEO_MODEL", "veo-2.0-generate-001")
    VEO_PARTS: int = 4
    VEO_DURATION: int = 8
    VEO_ASPECT_RATIO: str = "9:16"

    # Google Cloud TTS
    TTS_VOICE: str = os.getenv("TTS_VOICE", "en-US-Neural2-F")
    TTS_LANGUAGE: str = os.getenv("TTS_LANGUAGE", "en-US")
    TTS_SPEAKING_RATE: float = float(os.getenv("TTS_SPEAKING_RATE", "1.05"))
    TTS_PITCH: float = float(os.getenv("TTS_PITCH", "0.0"))

    # Output — use /tmp in CI
    OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "/tmp/reelsbot_output")
    DB_PATH: str = os.getenv("DB_PATH", "pipeline.db")

    # Video
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30
    FONT_PATH: str = os.getenv("FONT_PATH", "/tmp/Montserrat-Bold.ttf")
    FONT_SIZE: int = int(os.getenv("FONT_SIZE", "72"))
    TEXT_COLOR: str = "#FFFFFF"
    TEXT_STROKE_COLOR: str = "#000000"
    TEXT_STROKE_WIDTH: int = 3
    WORDS_PER_CAPTION: int = 4

config = Config()
