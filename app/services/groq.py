import base64
import json
import time
from pathlib import Path
from PIL import Image
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL

MAX_IMAGES_PER_REQUEST = 5

def _small_data_url(path: Path) -> str:
    with Image.open(path) as im:
        im.thumbnail((512, 512))
        rgb = im.convert("RGB")
        import io
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def _one_batch(client, script, words, photo_paths, offset, window_start, window_end):
    compact = [{"i": i, "w": x["word"], "s": round(x["start"], 2), "e": round(x["end"], 2)}
               for i, x in enumerate(words) if x["end"] >= window_start and x["start"] <= window_end]
    content = [{"type": "text", "text": (
        "You are a visual editor. Keep the supplied photos in exact order. "
        "For this batch, assign contiguous narration intervals inside the supplied time window. "
        "Never reorder photos and never use a photo before the previous photo. "
        "Return JSON only: {\"scenes\":[{\"photo_index\":0,\"start\":0,\"end\":5,"
        "\"focus\":\"none|face|person\",\"focus_time\":3.2}]}. "
        "Cover the entire supplied window when possible. Use a photo for a general shot and optionally a second"
        " adjacent scene with the same photo for a closer character shot when the words clearly support it. "
        f"TIME_WINDOW={window_start:.2f}-{window_end:.2f}. SCRIPT={script}. "
        f"ALIGNED_WORDS={json.dumps(compact[:900])}"
    )}]
    for local_i, p in enumerate(photo_paths):
        content.append({"type": "text", "text": f"PHOTO_INDEX={offset+local_i}"})
        content.append({"type": "image_url", "image_url": {"url": _small_data_url(p)}})
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": content}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

def plan_visuals(script: str, alignment: dict, photo_paths: list[Path]) -> tuple[dict | None, str | None]:
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY não configurada; distribuição proporcional usada."
    try:
        client = Groq(api_key=GROQ_API_KEY)
        words = alignment.get("words", [])
        duration = float(alignment.get("duration", 0))
        if not photo_paths or duration <= 0:
            return None, "Não foi possível montar o plano visual; distribuição proporcional usada."
        # At most five images per multimodal request. Batches receive chronological time windows,
        # so the global result remains ordered even when many photos were uploaded.
        merged = []
        total = len(photo_paths)
        for start in range(0, total, MAX_IMAGES_PER_REQUEST):
            batch = photo_paths[start:start + MAX_IMAGES_PER_REQUEST]
            w0 = duration * start / total
            w1 = duration * min(total, start + len(batch)) / total
            data = _one_batch(client, script, words, batch, start, w0, w1)
            merged.extend(data.get("scenes", []))
        return {"scenes": merged}, None
    except Exception as exc:
        return None, f"Groq indisponível ou limite atingido; distribuição proporcional usada: {exc}"
