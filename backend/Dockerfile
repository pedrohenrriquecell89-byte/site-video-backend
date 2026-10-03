FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPER_MODEL=/opt/piper/en_US-hfc_male-medium.onnx \
    ALIGNMENT_MODE=whisperx \
    WHISPER_MODEL=tiny

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg wget ca-certificates libsndfile1 espeak-ng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Piper runtime and requested US male medium voice.
RUN pip install piper-tts==1.3.0
RUN mkdir -p /opt/piper && \
    wget -q -O /opt/piper/en_US-hfc_male-medium.onnx \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx && \
    wget -q -O /opt/piper/en_US-hfc_male-medium.onnx.json \
    https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx.json

# WhisperX is deliberately installed separately. See README: on the 512 MB free tier
# it can exceed the memory budget, so the application has a proportional-timing fallback.
ARG INSTALL_WHISPERX=false
RUN if [ "$INSTALL_WHISPERX" = "true" ]; then pip install -r requirements-whisperx.txt; fi

COPY app ./app
COPY .env.example ./
EXPOSE 10000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000"]
