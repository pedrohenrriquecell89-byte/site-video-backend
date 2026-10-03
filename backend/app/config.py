import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = Path(os.getenv("TMP_DIR", "/tmp/video_narrator"))
TMP_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "Narrated Video Builder"
MAX_SCRIPT_WORDS = int(os.getenv("MAX_SCRIPT_WORDS", "12000"))
MAX_PART_WORDS = 1600
MIN_PHOTOS = int(os.getenv("MIN_PHOTOS", "1"))
MAX_PHOTOS = int(os.getenv("MAX_PHOTOS", "30"))
MAX_PHOTO_MB = int(os.getenv("MAX_PHOTO_MB", "8"))
MIN_SCENE_SECONDS = float(os.getenv("MIN_SCENE_SECONDS", "1.5"))
MAX_SCENE_SECONDS = float(os.getenv("MAX_SCENE_SECONDS", "20"))
RETENTION_SECONDS = int(os.getenv("RETENTION_SECONDS", "3600"))
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "3"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
CORS_ORIGINS = [x.strip() for x in os.getenv("CORS_ORIGINS", "*").split(",") if x.strip()]
PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-hfc_male-medium")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
ALIGNMENT_MODE = os.getenv("ALIGNMENT_MODE", "whisperx")
PIPER_BIN = os.getenv("PIPER_BIN", "piper")

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
