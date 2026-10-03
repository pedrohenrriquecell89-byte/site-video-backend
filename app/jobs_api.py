from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from app.config import *
from app.utils import count_words, split_into_parts, validate_image
from app.services.jobs import JOBS, LOCK, create_job, retry_part

router = APIRouter()

@router.post("/jobs")
async def create(script: str = Form(...), photos: list[UploadFile] = File(...)):
    script = script.strip()
    if not script:
        raise HTTPException(400, "O roteiro está vazio.")
    if count_words(script) > MAX_SCRIPT_WORDS:
        raise HTTPException(400, f"O roteiro ultrapassa o limite de {MAX_SCRIPT_WORDS} palavras.")
    if not (MIN_PHOTOS <= len(photos) <= MAX_PHOTOS):
        raise HTTPException(400, f"Envie entre {MIN_PHOTOS} e {MAX_PHOTOS} fotos.")
    saved = []
    for photo in photos:
        if photo.content_type not in ALLOWED_PHOTO_TYPES:
            raise HTTPException(400, f"Formato não permitido: {photo.filename}.")
        data = await photo.read()
        if len(data) > MAX_PHOTO_MB * 1024 * 1024:
            raise HTTPException(400, f"A foto {photo.filename} excede {MAX_PHOTO_MB} MB.")
        # Validate bytes through a short temporary file in the job directory after create_job.
        # PIL validation is repeated after saving to avoid trusting MIME alone.
        saved.append((photo.filename or "photo.jpg", data))
    job = create_job(script, saved)
    for p in job.photos:
        ok, msg = validate_image(Path(p))
        if not ok:
            import shutil
            shutil.rmtree(job.directory, ignore_errors=True)
            with LOCK: JOBS.pop(job.job_id, None)
            raise HTTPException(400, msg)
    parts = split_into_parts(script)
    return {"job_id": job.job_id, "parts": len(parts), "status": job.status,
            "message": "Servidor acordado. O processamento começou em fila sequencial."}

@router.get("/jobs/{job_id}")
def status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado ou já expirou.")
    with LOCK:
        return {"job_id": job.job_id, "status": job.status, "progress": job.progress,
                "message": job.message, "expires_at": job.expires_at,
                "parts": [{"part_id": p.part_id, "status": p.status, "progress": p.progress,
                            "message": p.message, "error": p.error,
                            "download": f"/api/jobs/{job.job_id}/parts/{p.part_id}/download" if p.output else None}
                           for p in job.parts]}

@router.post("/jobs/{job_id}/parts/{part_id}/retry")
def retry(job_id: str, part_id: int):
    if not retry_part(job_id, part_id):
        raise HTTPException(404, "Job ou parte não encontrado.")
    return {"status": "queued", "message": "Parte colocada novamente na fila."}

@router.get("/jobs/{job_id}/parts/{part_id}/download")
def download(job_id: str, part_id: int):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado ou expirado.")
    part = next((p for p in job.parts if p.part_id == part_id), None)
    if not part or not part.output or not Path(part.output).exists():
        raise HTTPException(404, "Vídeo ainda não está disponível.")
    return FileResponse(part.output, media_type="video/mp4", filename=f"video_parte_{part_id:02d}.mp4")
