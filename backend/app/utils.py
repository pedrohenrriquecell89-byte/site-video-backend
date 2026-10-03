import re
from pathlib import Path
from PIL import Image

SENTENCE_RE = re.compile(r".+?(?:[.!?]+(?:[\"'’”)]*)|$)", re.S)
WORD_RE = re.compile(r"\b\S+\b")

def count_words(text: str) -> int:
    return len(WORD_RE.findall(text.strip()))

def split_into_parts(text: str, max_words: int = 1600) -> list[str]:
    sentences = [s.strip() for s in SENTENCE_RE.findall(text) if s.strip()]
    if not sentences:
        return []
    parts, current, n = [], [], 0
    for sentence in sentences:
        words = count_words(sentence)
        if words > max_words:
            # Extremely long sentence: preserve sentence boundary as much as possible.
            tokens = sentence.split()
            for i in range(0, len(tokens), max_words):
                chunk = " ".join(tokens[i:i + max_words])
                if current:
                    parts.append(" ".join(current))
                    current, n = [], 0
                parts.append(chunk)
            continue
        if current and n + words > max_words:
            parts.append(" ".join(current))
            current, n = [], 0
        current.append(sentence)
        n += words
    if current:
        parts.append(" ".join(current))
    return parts

def validate_image(path: Path) -> tuple[bool, str]:
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            if img.width < 160 or img.height < 90:
                return False, "Imagem muito pequena."
        return True, "OK"
    except Exception as exc:
        return False, f"Imagem inválida: {exc}"

def safe_name(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", name or "")
    return cleaned[:100] or fallback
