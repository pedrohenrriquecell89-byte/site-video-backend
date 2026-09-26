import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
PIPER_MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "/app/models/piper/voice.onnx")
MAX_WORDS_PER_CHUNK = 1600
