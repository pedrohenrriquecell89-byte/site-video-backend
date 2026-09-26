import subprocess
from pathlib import Path
from typing import List

def render_video_part(audio_path: Path, image_paths: List[Path], output_mp4_path: Path) -> Path:
    """
    Monta e renderiza o vídeo final usando FFmpeg.
    Aplica transição fade in/out entre imagens e insere o áudio normalizado em H.264 (1080p).
    """
    if not image_paths:
        raise ValueError("Nenhuma imagem fornecida para a montagem do vídeo.")

    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ]
    duration = float(subprocess.check_output(duration_cmd).decode().strip())
    
    num_images = len(image_paths)
    time_per_image = duration / num_images
    fade_duration = 0.4

    inputs = []
    filter_complex = []

    for i, img in enumerate(image_paths):
        inputs.extend(["-loop", "1", "-t", str(time_per_image), "-i", str(img)])
        filter_complex.append(
            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fade=t=in:st=0:d={fade_duration},fade=t=out:st={time_per_image - fade_duration}:d={fade_duration}[v{i}];"
        )

    concat_inputs = "".join([f"[v{i}]" for i in range(num_images)])
    filter_complex.append(f"{concat_inputs}concat=n={num_images}:v=1:a=0[vcat];")
    filter_complex.append(f"[{num_images}:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")

    inputs.extend(["-i", str(audio_path)])

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", "".join(filter_complex),
        "-map", "[vcat]",
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(output_mp4_path)
    ]

    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Erro de renderização no FFmpeg: {process.stderr}")

    return output_mp4_path
