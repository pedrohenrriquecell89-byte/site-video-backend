import uuid
import shutil
import asyncio
from typing import List, Dict
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import ALLOWED_ORIGINS, MEDIA_DIR, MAX_WORDS_PER_CHUNK
from app.services.text_splitter import split_script_into_chunks
from app.services.tts_service import generate_tts
from app.services.align_service import align_audio_script
from app.services.video_service import render_video_part

app = FastAPI(title="Video Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/download", StaticFiles(directory=MEDIA_DIR), name="download")

jobs_db: Dict[str, dict] = {}

def process_job(job_id: str, script_text: str, image_paths: List[Path]):
    try:
        chunks = split_script_into_chunks(script_text, max_words=MAX_WORDS_PER_CHUNK)
        jobs_db[job_id]["total_parts"] = len(chunks)
        jobs_db[job_id]["parts_status"] = [{"part": i + 1, "status": "pending", "file": None} for i in range(len(chunks))]
        jobs_db[job_id]["status"] = "processing"

        total_images = len(image_paths)
        imgs_per_chunk = max(1, total_images // len(chunks))

        for idx, chunk in enumerate(chunks):
            jobs_db[job_id]["parts_status"][idx]["status"] = "generating_audio"
            part_num = idx + 1
            part_dir = MEDIA_DIR / job_id / f"part_{part_num}"
            part_dir.mkdir(parents=True, exist_ok=True)

            audio_path = part_dir / "narration.wav"
            generate_tts(chunk, audio_path)

            jobs_db[job_id]["parts_status"][idx]["status"] = "aligning"
            align_audio_script(audio_path, chunk)

            start_img = idx * imgs_per_chunk
            end_img = start_img + imgs_per_chunk if idx < len(chunks) - 1 else total_images
            chunk_images = image_paths[start_img:end_img]
            if not chunk_images:
                chunk_images = image_paths

            jobs_db[job_id]["parts_status"][idx]["status"] = "rendering"
            output_mp4 = part_dir / f"video_parte_{part_num}.mp4"
            render_video_part(audio_path, chunk_images, output_mp4)

            rel_path = f"/download/{job_id}/part_{part_num}/video_parte_{part_num}.mp4"
            jobs_db[job_id]["parts_status"][idx]["status"] = "completed"
            jobs_db[job_id]["parts_status"][idx]["file"] = rel_path

        jobs_db[job_id]["status"] = "completed"
    except Exception as e:
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)

@app.post("/api/render")
async def create_render_job(
    background_tasks: BackgroundTasks,
    script: str = Form(...),
    images: List[UploadFile] = File(...)
):
    if not script.strip():
        raise HTTPException(status_code=400, detail="O roteiro não pode estar vazio.")
    if not images:
        raise HTTPException(status_code=400, detail="Pelo menos uma imagem deve ser enviada.")

    job_id = str(uuid.uuid4())
    job_dir = MEDIA_DIR / job_id / "raw_images"
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_images = []
    for idx, img in enumerate(images):
        ext = Path(img.filename).suffix or ".jpg"
        file_path = job_dir / f"img_{idx:03d}{ext}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
        saved_images.append(file_path)

    jobs_db[job_id] = {
        "status": "queued",
        "total_parts": 0,
        "parts_status": [],
        "error": None
    }

    background_tasks.add_task(process_job, job_id, script, saved_images)
    return {"job_id": job_id, "message": "Processamento iniciado."}

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Trabalho não encontrado.")
    return jobs_db[job_id]
