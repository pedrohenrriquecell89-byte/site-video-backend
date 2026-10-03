import json
import logging
import os
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path
from app.config import TMP_DIR, RETENTION_SECONDS
from app.models import JobState, PartState
from app.utils import split_into_parts, count_words
from app.services.tts import synthesize
from app.services.alignment import align
from app.services.groq import plan_visuals
from app.services.visual import normalize_plan
from app.services.render import render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.FileHandler(TMP_DIR / "app.log"), logging.StreamHandler()])
log = logging.getLogger("video_narrator")

JOBS: dict[str, JobState] = {}
QUEUE: queue.Queue[tuple[str, int]] = queue.Queue()
LOCK = threading.RLock()


def _job(job_id):
    with LOCK:
        return JOBS.get(job_id)


def _set(job, **kwargs):
    with LOCK:
        for k, v in kwargs.items():
            setattr(job, k, v)


def _part_texts(script: str):
    return split_into_parts(script)


def create_job(script: str, photo_files: list[tuple[str, bytes]]) -> JobState:
    job_id = uuid.uuid4().hex
    directory = TMP_DIR / job_id
    directory.mkdir(parents=True, exist_ok=False)
    photos = []
    for i, (name, data) in enumerate(photo_files):
        p = directory / f"photo_{i:03d}_{Path(name).name[:60]}"
        p.write_bytes(data)
        photos.append(str(p))
    parts = [PartState(i + 1, words=count_words(t)) for i, t in enumerate(_part_texts(script))]
    job = JobState(job_id=job_id, script=script, photos=photos, parts=parts,
                   directory=str(directory), expires_at=time.time() + RETENTION_SECONDS)
    with LOCK:
        JOBS[job_id] = job
    for p in parts:
        QUEUE.put((job_id, p.part_id))
    return job


def retry_part(job_id: str, part_id: int) -> bool:
    job = _job(job_id)
    if not job or not any(p.part_id == part_id for p in job.parts):
        return False
    with LOCK:
        p = next(x for x in job.parts if x.part_id == part_id)
        p.status, p.progress, p.message, p.error = "queued", 0, "Reprocessamento solicitado", None
        p.output = None
        job.status = "queued"
    QUEUE.put((job_id, part_id))
    return True


def _photos_for_part(all_photos: list[Path], part_index: int, part_count: int, words: list[int]) -> list[Path]:
    if part_count <= 1:
        return all_photos
    total = sum(words) or part_count
    start = round(len(all_photos) * sum(words[:part_index]) / total)
    end = round(len(all_photos) * sum(words[:part_index + 1]) / total)
    if end <= start:
        end = min(len(all_photos), start + 1)
    if part_index == part_count - 1:
        end = len(all_photos)
    return all_photos[start:end] or [all_photos[min(start, len(all_photos)-1)]]


def _process(job: JobState, part: PartState):
    root = Path(job.directory)
    text_parts = _part_texts(job.script)
    text = text_parts[part.part_id - 1]
    all_photos = [Path(x) for x in job.photos]
    words = [count_words(x) for x in text_parts]
    part_photos = _photos_for_part(all_photos, part.part_id - 1, len(text_parts), words)
    work = root / f"part_{part.part_id:02d}"
    work.mkdir(exist_ok=True)
    wav = work / "voice.wav"
    alignment_json = work / "alignment.json"
    output = root / f"video_part_{part.part_id:02d}.mp4"
    try:
        part.started_at = time.time(); part.status = "processing"
        part.progress = 5; part.message = "Gerando narração com Piper"
        synthesize(text, wav)
        part.progress = 28; part.message = "Alinhando palavras"
        alignment = align(text, wav, work)
        alignment_json.write_text(json.dumps(alignment), encoding="utf-8")
        if alignment.get("warning"):
            part.message = alignment["warning"]
        # Release avoidable files before visual analysis where possible.
        part.progress = 45; part.message = "Analisando roteiro e fotos"
        plan, warning = plan_visuals(text, alignment, part_photos[:5])
        scenes = normalize_plan(plan, len(part_photos), alignment.get("duration", 0), part_photos)
        if warning:
            part.message = warning
        part.progress = 62; part.message = "Aplicando movimentos de câmera"
        render(scenes, part_photos, wav, output, alignment.get("duration", 0), work)
        part.progress = 100; part.status = "done"; part.output = str(output)
        part.message = "Vídeo pronto"
        part.finished_at = time.time()
    except Exception as exc:
        part.status = "error"; part.error = str(exc); part.message = "Esta parte falhou"; part.finished_at = time.time()
        log.exception("Falha no job %s parte %s", job.job_id, part.part_id)
    finally:
        # Delete bulky intermediate scene files and ASR outputs; keep final MP4.
        for child in work.iterdir():
            if child.name not in {"voice.wav", "alignment.json"}:
                try:
                    if child.is_dir(): shutil.rmtree(child)
                    else: child.unlink()
                except OSError: pass
        try: wav.unlink()
        except OSError: pass


def worker():
    while True:
        job_id, part_id = QUEUE.get()
        try:
            job = _job(job_id)
            if not job:
                continue
            part = next((p for p in job.parts if p.part_id == part_id), None)
            if not part or part.status == "done":
                continue
            _process(job, part)
            done = sum(1 for p in job.parts if p.status == "done")
            failed = sum(1 for p in job.parts if p.status == "error")
            pending = sum(1 for p in job.parts if p.status in {"queued", "processing"})
            job.progress = int((done / len(job.parts)) * 100)
            if pending:
                job.status = "processing"; job.message = f"{done}/{len(job.parts)} partes concluídas"
            elif failed:
                job.status = "partial"; job.message = f"{failed} parte(s) falharam; as outras continuam disponíveis"
            else:
                job.status = "done"; job.message = "Todas as partes concluídas"
            job.expires_at = time.time() + RETENTION_SECONDS
        except Exception:
            log.exception("Erro inesperado no worker")
        finally:
            QUEUE.task_done()


def cleanup_loop():
    while True:
        time.sleep(60)
        now = time.time()
        for job_id, job in list(JOBS.items()):
            if job.expires_at and now > job.expires_at:
                try: shutil.rmtree(job.directory, ignore_errors=True)
                except Exception: pass
                with LOCK: JOBS.pop(job_id, None)

threading.Thread(target=worker, daemon=True, name="video-worker").start()
threading.Thread(target=cleanup_loop, daemon=True, name="cleanup").start()
