from pathlib import Path
import whisperx

def align_audio_script(audio_path: Path, script_text: str, device: str = "cpu"):
    """Alinha o áudio gerado com o texto usando WhisperX para timestamps por palavra."""
    try:
        model = whisperx.load_model("base", device=device, compute_type="int8")
        audio = whisperx.load_audio(str(audio_path))
        result = model.transcribe(audio, batch_size=1)
        
        model_a, metadata = whisperx.load_align_model(language_code="en", device=device)
        aligned_result = whisperx.align(result["segments"], model_a, metadata, audio, device)
        
        return aligned_result
    except Exception as e:
        raise RuntimeError(f"Falha no alinhamento WhisperX: {str(e)}")
