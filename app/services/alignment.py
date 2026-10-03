import json
import subprocess
import tempfile
from pathlib import Path
from app.config import ALIGNMENT_MODE, WHISPER_MODEL
import os


def _fallback(text: str, wav_path: Path) -> dict:
    """Conservative fallback: proportional word timings, so rendering can continue."""
    import wave
    with wave.open(str(wav_path), "rb") as wf:
        duration = wf.getnframes() / max(1, wf.getframerate())
    words = text.split()
    if not words:
        return {"duration": duration, "words": []}
    step = duration / len(words)
    return {"duration": duration, "words": [{"word": w, "start": i*step, "end": (i+1)*step}
                                              for i, w in enumerate(words)]}


def align(text: str, wav_path: Path, work_dir: Path) -> dict:
    if ALIGNMENT_MODE != "whisperx":
        return _fallback(text, wav_path)
    try:
        # WhisperX CLI writes JSON beside the input/output directory.
        out = work_dir / "whisperx"
        out.mkdir(exist_ok=True)
        cmd = ["whisperx", str(wav_path), "--model", WHISPER_MODEL,
               "--device", "cpu", "--compute_type", "int8",
               "--language", "en", "--output_format", "json",
               "--output_dir", str(out), "--batch_size", "1"]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode("utf-8", "ignore")[-1500:])
        json_path = out / (wav_path.stem + ".json")
        if not json_path.exists():
            raise RuntimeError("WhisperX não produziu JSON.")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        words = []
        for seg in data.get("segments", []):
            for w in seg.get("words", []):
                if w.get("start") is not None and w.get("end") is not None:
                    words.append({"word": w.get("word", "").strip(),
                                  "start": float(w["start"]), "end": float(w["end"])})
        duration = max([w["end"] for w in words], default=0.0)
        if not words:
            raise RuntimeError("WhisperX retornou timestamps vazios.")
        return {"duration": duration, "words": words}
    except Exception as exc:
        # Keep the job alive; the UI will explicitly state that alignment fallback was used.
        fallback = _fallback(text, wav_path)
        fallback["warning"] = f"Alinhamento WhisperX indisponível; temporização proporcional usada: {exc}"
        return fallback
