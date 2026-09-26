import subprocess
from pathlib import Path
from app.config import PIPER_MODEL_PATH

def generate_tts(text: str, output_wav_path: Path) -> Path:
    """Gera o arquivo de áudio WAV usando Piper TTS."""
    cmd = [
        "piper",
        "--model", PIPER_MODEL_PATH,
        "--output_file", str(output_wav_path)
    ]
    try:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        _, stderr = process.communicate(input=text)
        if process.returncode != 0:
            raise RuntimeError(f"Erro no Piper TTS: {stderr}")
        return output_wav_path
    except Exception as e:
        raise RuntimeError(f"Falha na geração de TTS: {str(e)}")
