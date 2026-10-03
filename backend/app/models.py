from dataclasses import dataclass, field
from typing import Any
import time

@dataclass
class PartState:
    part_id: int
    status: str = "queued"
    progress: int = 0
    message: str = "Na fila"
    output: str | None = None
    error: str | None = None
    words: int = 0
    started_at: float | None = None
    finished_at: float | None = None

@dataclass
class JobState:
    job_id: str
    status: str = "queued"
    progress: int = 0
    message: str = "Aguardando processamento"
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0
    script: str = ""
    photos: list[str] = field(default_factory=list)
    parts: list[PartState] = field(default_factory=list)
    directory: str = ""
    lock: Any = field(default=None, repr=False)
