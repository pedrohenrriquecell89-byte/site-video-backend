from pathlib import Path
import cv2
from app.config import MIN_SCENE_SECONDS, MAX_SCENE_SECONDS

MOVES = ["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]

def detect_focus(path: Path) -> tuple[float, float] | None:
    img = cv2.imread(str(path))
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
    if len(faces):
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        return ((x + w/2) / img.shape[1], (y + h/2) / img.shape[0])
    # center is a safe fallback for generic scenes.
    return (0.5, 0.5)

def normalize_plan(plan: dict | None, photo_count: int, duration: float, photo_paths: list[Path]) -> list[dict]:
    if not plan or not plan.get("scenes"):
        each = duration / max(1, photo_count)
        scenes = []
        for i, p in enumerate(photo_paths):
            start = i * each
            end = duration if i == photo_count - 1 else (i + 1) * each
            scenes.append({"photo_index": i, "start": start, "end": end, "focus": "face" if detect_focus(p) else "none"})
        return scenes
    raw = []
    for s in plan["scenes"]:
        try:
            pi = int(s["photo_index"])
            if 0 <= pi < photo_count:
                raw.append({"photo_index": pi, "start": max(0.0, float(s["start"])),
                            "end": min(duration, float(s["end"])), "focus": s.get("focus", "none"),
                            "focus_time": float(s.get("focus_time", 0))})
        except Exception:
            continue
    raw.sort(key=lambda x: (x["start"], x["photo_index"]))
    # Enforce chronological coverage and photo order.
    result, cursor, last_photo = [], 0.0, -1
    for s in raw:
        if s["photo_index"] < last_photo or s["end"] <= s["start"]:
            continue
        s["start"] = max(s["start"], cursor)
        if s["end"] <= s["start"]:
            continue
        result.append(s); cursor = s["end"]; last_photo = s["photo_index"]
    if cursor < duration:
        result.append({"photo_index": min(last_photo + 1, photo_count - 1), "start": cursor,
                       "end": duration, "focus": "none"})
    return result

def choose_move(index: int) -> str:
    return MOVES[index % len(MOVES)]
