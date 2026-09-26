"""Input validation for the upload pipeline. Fails fast, before any
expensive processing (TTS, alignment, rendering)."""

from pathlib import Path

MAX_WORDS_PER_PART = 1600  # ~10 min of narration at ~160 wpm, per generated video part
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_MB = 15


class ValidationError(Exception):
    pass


def validate_script(script: str):
    if not script or not script.strip():
        raise ValidationError("Script is empty.")
    if len(script.split()) < 3:
        raise ValidationError("Script is too short.")


def chunk_scene_indices(scenes, max_words=MAX_WORDS_PER_PART):
    """Group scenes into parts of up to max_words each, without splitting a
    scene across parts. Returns a list of index-lists, one per part. A
    script longer than the limit becomes multiple parts (multiple videos)
    instead of being rejected."""
    chunks = []
    current = []
    current_words = 0
    for i, scene in enumerate(scenes):
        w = len(scene.split())
        if w > max_words:
            raise ValidationError(
                f"Scene {i + 1} alone has {w} words, above the {max_words}-word "
                f"per-part limit. Split that scene into smaller scenes in the script."
            )
        if current and current_words + w > max_words:
            chunks.append(current)
            current = []
            current_words = 0
        current.append(i)
        current_words += w
    if current:
        chunks.append(current)
    return chunks


def split_scenes(script: str):
    """Scenes are separated by one or more blank lines. Each scene = one photo."""
    raw = [s.strip() for s in script.replace("\r\n", "\n").split("\n\n")]
    scenes = [s for s in raw if s]
    if not scenes:
        raise ValidationError("Could not find any scenes in the script.")
    return scenes


def validate_images(images, expected_count):
    if not images:
        raise ValidationError("No photos uploaded.")
    if len(images) != expected_count:
        raise ValidationError(
            f"Script has {expected_count} scene(s) (separated by blank lines) "
            f"but {len(images)} photo(s) were sent. Counts must match, one photo per scene."
        )
    for img in images:
        ext = safe_ext(img.filename)
        if ext not in ALLOWED_IMAGE_EXT:
            raise ValidationError(f"Unsupported image format: {img.filename}")


def safe_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in ALLOWED_IMAGE_EXT else ".jpg"


def validate_image_bytes(content: bytes, filename: str):
    if not content:
        raise ValidationError(f"Empty file: {filename}")
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_IMAGE_MB:
        raise ValidationError(f"{filename} is too large ({size_mb:.1f}MB). Max {MAX_IMAGE_MB}MB.")
    # Basic magic-byte check catches corrupted / non-image uploads early.
    valid_headers = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
    if not any(content.startswith(h) for h in valid_headers):
        raise ValidationError(f"{filename} does not look like a valid image.")
