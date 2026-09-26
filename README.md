# Video Narrator

Site pessoal (sem login) que gera vídeo narrado a partir de roteiro em inglês + fotos em sequência.

## ⚠️ Desvio importante em relação ao pedido original

Você pediu WhisperX. Troquei por **faster-whisper** (modelo `base.en`, CPU, int8) para o
alinhamento por palavra. Motivo: WhisperX depende de PyTorch + modelo de alinhamento
separado, que não roda de forma confiável nos 512MB de RAM do plano free do Render —
trava com OOM na prática. faster-whisper entrega os mesmos timestamps por palavra com
uma pegada de memória muito menor. Se você migrar para um plano pago do Render (mais
RAM), dá pra trocar em `pipeline/align.py` sem mexer no resto do pipeline.

## Limitações reais do plano free do Render que valem saber

- **Sleep**: o serviço dorme após ~15 min sem tráfego. Primeira visita depois disso
  demora 30–60s pra acordar. Normal, não é bug.
- **RAM (512MB)**: renderizar 10 minutos de vídeo com muitas fotos em alta resolução
  pode ser lento e, em casos extremos, estourar memória. Se acontecer, reduza a
  resolução das fotos enviadas (o servidor já redimensiona para 1080p, mas fotos de
  origem enormes consomem RAM antes disso).
- **CPU compartilhada**: sem GPU. TTS + alinhamento + render de 10 min podem levar
  vários minutos — a interface mostra progresso pra isso ficar claro.
- **Disco efêmero**: arquivos de jobs (`jobs/`) somem a cada novo deploy. Isso é
  esperado para um app single-user sem histórico.

## Estrutura do projeto

```
video-narrator/
├── backend/                  # Deploy no Render
│   ├── app.py                # FastAPI: rotas, orquestração do pipeline
│   ├── pipeline/
│   │   ├── validate.py       # validação + divisão do roteiro em partes
│   │   ├── tts.py            # narração via Piper
│   │   ├── align.py          # timestamps por palavra via faster-whisper
│   │   └── assemble.py       # timing de cena + montagem com FFmpeg
│   ├── Dockerfile
│   ├── render.yaml
│   └── requirements.txt
└── frontend/                 # Deploy no Netlify (site estático)
    ├── index.html
    ├── style.css
    └── app.js                # tem a constante API_BASE apontando pro Render
```

## Como usar

1. Escreva o roteiro em inglês. Separe cada cena com **uma linha em branco**.
2. Envie **uma foto por cena**, na mesma ordem do roteiro (galeria, não câmera).
3. Clique em "Generate Video" e acompanhe o progresso.
4. Roteiro longo (acima de ~1600 palavras) vira automaticamente várias partes,
   em ordem cronológica. Baixe cada parte ou todas de uma vez em .zip.

## Deploy — backend no Render

1. Suba a pasta `backend/` pro GitHub (pode ser o mesmo repo do frontend,
   Render só precisa apontar pro subdiretório certo).
2. render.com → New → Web Service → conecte o repositório.
3. Se o repo tiver as duas pastas, em "Root Directory" coloque `backend`.
4. Runtime: Docker (detectado pelo `Dockerfile`). Plano: **Free**.
5. Variável de ambiente opcional: `WHISPER_MODEL` = `base.en` (já é o padrão).
6. Deploy. Render te dá uma URL tipo `https://video-narrator-api.onrender.com`.

## Deploy — frontend no Netlify

1. Antes de subir, abra `frontend/app.js` e troque a linha:
   ```js
   const API_BASE = "https://SEU-BACKEND.onrender.com";
   ```
   pela URL real que o Render te deu no passo anterior.
2. netlify.com → Add new site → Deploy manually (arraste a pasta `frontend/`)
   **ou** conecte o repositório e configure "Base directory" = `frontend`,
   sem build command (é HTML/CSS/JS puro).
3. Netlify te dá uma URL tipo `https://video-narrator.netlify.app` — é essa
   que você abre no celular.

**CORS**: o backend já libera qualquer origem (`allow_origins=["*"]`), então
o Netlify consegue chamar o Render sem bloqueio. Se quiser travar só pro seu
domínio Netlify, edite `backend/app.py`, na configuração do `CORSMiddleware`.

## Tratamento de erros

Cada etapa (upload, validação, TTS, alinhamento, render) tem try/except próprio.
Falhas aparecem na interface com mensagem clara — nada trava silenciosamente.
Logs completos ficam em `backend/app.log` e, por job, em `backend/jobs/<id>/error.log`.
