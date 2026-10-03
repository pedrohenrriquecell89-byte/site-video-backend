import os
import subprocess
from pathlib import Path
from app.config import PIPER_BIN, PIPER_VOICE

def synthesize(text: str, wav_path: Path) -> None:
    model = os.getenv("PIPER_MODEL", PIPER_VOICE)
    cmd = [PIPER_BIN, "--model", model, "--output_file", str(wav_path)]
    result = subprocess.run(cmd, input=text.encode("utf-8"), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=os.environ.copy(), timeout=900)
    if result.returncode != 0:
        raise RuntimeError("Piper falhou: " + result.stderr.decode("utf-8", "ignore")[-1200:])
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        raise RuntimeError("Piper não gerou o áudio.")
