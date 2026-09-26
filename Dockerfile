FROM python:3.10-slim

# Instala FFmpeg e dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    espeak-ng \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download da voz do Piper (en_US-hfc_male-medium)
RUN mkdir -p /app/models/piper && \
    wget -O /app/models/piper/voice.onnx https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx && \
    wget -O /app/models/piper/voice.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_male/medium/en_US-hfc_male-medium.onnx.json

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
