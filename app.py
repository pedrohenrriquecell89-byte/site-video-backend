"""
FastAPI backend for automated narrated-video generation.
Single-user, no auth. Pipeline: script+photos -> TTS (Piper) ->
word-level alignment (faster-whisper) -> scene timing -> FFmpeg render.
"""

import json
import shutil
import logging
import traceback
import uuid
import zipfile
from pathlib import Path
from threading import Thread

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pipeline import validate, tts, align, assemble

BASE_DIR = Path(__file__).parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "app.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("video-narrator")

app = FastAPI(title="Video Narrator API")

# Single-user tool, no auth: the frontend is hosted separately on Netlify
# (different origin), so CORS must allow it. Restrict to your Netlify
# domain in production if you want to be stricter than "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job status (single-user tool). Mirrored to disk for resilience
# across a Render free-tier sleep/wake cycle within the same deploy.
JOBS = {}


def set_status(job_id, stage, progress=0, message="", error=None, done=False,
                download_ready=False, parts=None):
    status = {
        "stage": stage,
        "progress": progress,
        "message": message,
        "error": error,
        "done": done,
        "download_ready": download_ready,
        "parts": parts if parts is not None else JOBS.get(job_id, {}).get("parts", []),
    }
    JOBS[job_id] = status
    try:
        (JOBS_DIR / job_id / "status.json").write_text(json.dumps(status))
    except Exception:
        log.warning("Could not persist status for job %s", job_id, exc_info=True)


@app.get("/")
def health():
    return {"status": "ok", "service": "video-narrator-api"}


@app.post("/upload")
async def upload(script: str = Form(...), images: list[UploadFile] = File(...)):
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    (job_dir / "images").mkdir(parents=True, exist_ok=True)

    try:
        # ---- Validate everything before spending any processing time ----
        validate.validate_script(script)
        scenes = validate.split_scenes(script)
        validate.validate_images(images, len(scenes))

        (job_dir / "script.txt").write_text(script, encoding="utf-8")

        for i, img in enumerate(images):
            ext = validate.safe_ext(img.filename)
            dest = job_dir / "images" / f"{i:04d}{ext}"
            content = await img.read()
            validate.validate_image_bytes(content, img.filename)
            dest.write_bytes(content)

    except validate.ValidationError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Upload failed: %s", e, exc_info=True)
        shutil.rmtree(job_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Upload failed. Please try again.")

    set_status(job_id, "queued", 0, "Job queued.")
    Thread(target=run_pipeline, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}


def run_pipeline(job_id: str):
    job_dir = JOBS_DIR / job_id
    try:
        script = (job_dir / "script.txt").read_text(encoding="utf-8")
        scenes = validate.split_scenes(script)
        images_dir = job_dir / "images"
        image_files = sorted(images_dir.glob("*"))

        # Long scripts are split into parts (max ~1600 words each) instead
        # of being rejected. Each part becomes its own video; the user joins
        # them afterwards (e.g. in a video editor or with ffmpeg concat).
        chunks = validate.chunk_scene_indices(scenes)
        total_parts = len(chunks)

        parts_dir = job_dir / "parts"
        parts_dir.mkdir(exist_ok=True)
        parts_info = []

        for p, indices in enumerate(chunks):
            part_num = p + 1
            part_scenes = [scenes[i] for i in indices]
            part_images = [image_files[i] for i in indices]
            part_script = "\n\n".join(part_scenes)
            base = int(p / total_parts * 100)

            set_status(job_id, "tts", base, f"Part {part_num}/{total_parts}: generating narration...")
            wav_path = parts_dir / f"part_{part_num:02d}.wav"
            tts.synthesize(part_script, wav_path)

            set_status(job_id, "align", base, f"Part {part_num}/{total_parts}: aligning words...")
            words = align.get_word_timestamps(wav_path)

            set_status(job_id, "planning", base, f"Part {part_num}/{total_parts}: calculating timing...")
            scene_times = assemble.plan_scene_timing(part_scenes, words)

            set_status(job_id, "render", base, f"Part {part_num}/{total_parts}: rendering...")
            output_path = parts_dir / f"part_{part_num:02d}.mp4"

            def _cb(pr, msg, p=p, part_num=part_num, total_parts=total_parts):
                set_status(job_id, "render", int((p + pr) / total_parts * 100),
                           f"Part {part_num}/{total_parts}: {msg}")

            assemble.render_video(scene_times, part_images, wav_path, output_path, progress_cb=_cb)
            parts_info.append({"index": part_num, "filename": output_path.name})
            wav_path.unlink(missing_ok=True)  # audio no longer needed once rendered

        zip_path = job_dir / "all_parts.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for info in parts_info:
                zf.write(parts_dir / info["filename"], arcname=info["filename"])

        set_status(
            job_id, "done", 100,
            f"{total_parts} video part(s) ready!" if total_parts > 1 else "Video ready!",
            done=True, download_ready=True, parts=parts_info,
        )

    except Exception as e:
        log.error("Pipeline failed for job %s: %s", job_id, e, exc_info=True)
        (job_dir / "error.log").write_text(traceback.format_exc())
        set_status(job_id, "error", 0, "", error=str(e), done=True)


@app.get("/status/{job_id}")
def status(job_id: str):
    if job_id not in JOBS:
        status_file = JOBS_DIR / job_id / "status.json"
        if status_file.exists():
            return json.loads(status_file.read_text())
        raise HTTPException(status_code=404, detail="Job not found.")
    return JOBS[job_id]


@app.get("/download/{job_id}/all")
def download_all(job_id: str):
    path = JOBS_DIR / job_id / "all_parts.zip"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Zip not ready or job not found.")
    return FileResponse(path, media_type="application/zip", filename="video_parts.zip")


@app.get("/download/{job_id}/part/{index}")
def download_part(job_id: str, index: int):
    path = JOBS_DIR / job_id / "parts" / f"part_{index:02d}.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Part not found.")
    return FileResponse(path, media_type="video/mp4", filename=f"part_{index:02d}.mp4")
