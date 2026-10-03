import time
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.config import *
from app.jobs_api import router as jobs_router

app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(jobs_router, prefix="/api")

@app.get("/")
def root():
    return {"name": APP_NAME, "status": "online", "message": "API pronta"}

@app.get("/health")
def health():
    return {"status": "ok", "time": time.time(), "worker": "single-sequential"}
