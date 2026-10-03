import subprocess
from pathlib import Path
from app.config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, MIN_SCENE_SECONDS, MAX_SCENE_SECONDS
from app.services.visual import choose_move, detect_focus


def _vf(photo: Path, duration: float, move: str, focus: tuple[float,float] | None) -> str:
    # Scale/crop to 16:9, then animate zoom/pan. The final frame remains focused near face when found.
    fx, fy = focus or (0.5, 0.5)
    z = "zoom+0.0007" if move == "zoom_in" else "max(1.0,zoom-0.0007)" if move == "zoom_out" else "1.06"
    x = "iw/2-(iw/zoom/2)"; y = "ih/2-(ih/zoom/2)"
    if move == "pan_left": x = "iw/zoom/2 + (iw-iw/zoom)*(1-on)"
    if move == "pan_right": x = "iw/zoom/2 + (iw-iw/zoom)*on"
    if move == "pan_up": y = "ih/zoom/2 + (ih-ih/zoom)*(1-on)"
    if move == "pan_down": y = "ih/zoom/2 + (ih-ih/zoom)*on"
    # 'on' is a normalized animation progress expression.
    x = x.replace("on", f"t/{max(duration, 0.1)}")
    y = y.replace("on", f"t/{max(duration, 0.1)}")
    if focus and move in ("zoom_in", "zoom_out"):
        x = f"{fx}*iw-iw/(2*zoom)"; y = f"{fy}*ih-ih/(2*zoom)"
    return (f"scale={VIDEO_WIDTH*2}:{VIDEO_HEIGHT*2},zoompan=z='{z}':x='{x}':y='{y}':"
            f"d={int(max(1,duration*VIDEO_FPS))}:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={VIDEO_FPS},"
            f"format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={max(0,duration-0.4)}:d=0.4")


def render(scenes: list[dict], photo_paths: list[Path], audio: Path, output: Path, duration: float, work: Path) -> None:
    scene_files = []
    for i, s in enumerate(scenes):
        start, end = float(s["start"]), float(s["end"])
        d = max(MIN_SCENE_SECONDS, end - start)
        photo = photo_paths[int(s["photo_index"]) % len(photo_paths)]
        focus = detect_focus(photo) if s.get("focus") in ("face", "person") else detect_focus(photo)
        # For > max duration, split the same image into two different moves.
        segments = max(1, int((d + MAX_SCENE_SECONDS - 1) // MAX_SCENE_SECONDS))
        seg_d = d / segments
        for j in range(segments):
            f = work / f"scene_{i:03d}_{j:02d}.mp4"
            vf = _vf(photo, seg_d, choose_move(i+j), focus)
            cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(photo), "-t", f"{seg_d:.3f}",
                   "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", str(f)]
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
            if r.returncode != 0:
                raise RuntimeError("FFmpeg cena falhou: " + r.stderr.decode("utf-8", "ignore")[-1200:])
            scene_files.append(f)
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p.as_posix()}'\n" for p in scene_files), encoding="utf-8")
    silent = work / "silent.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-c", "copy", str(silent)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg concat falhou: " + r.stderr.decode("utf-8", "ignore")[-1200:])
    # AAC audio is normalized during final mux. Loudness target is conservative for YouTube.
    r = subprocess.run(["ffmpeg", "-y", "-i", str(silent), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                        "-shortest", "-movflags", "+faststart", str(output)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg mux falhou: " + r.stderr.decode("utf-8", "ignore")[-1200:])
