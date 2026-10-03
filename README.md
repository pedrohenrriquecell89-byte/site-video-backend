# Backend — Narrated Video Builder

FastAPI REST API para geração assíncrona de vídeos narrados. O worker processa **uma parte por vez** para limitar RAM/CPU.

## Endpoints
- `GET /health`
- `POST /api/jobs` — `multipart/form-data`: `script` + `photos[]`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/parts/{part_id}/retry`
- `GET /api/jobs/{job_id}/parts/{part_id}/download`

## Observação importante sobre o Render Free
O serviço gratuito atualmente tem 512 MB RAM e pode dormir após 15 minutos sem tráfego. O sistema mantém jobs em memória e arquivos temporários; reinício/spin-down perde esses dados. WhisperX/PyTorch pode exceder 512 MB: o código tenta WhisperX tiny/int8, mas usa temporização proporcional se WhisperX não iniciar ou falhar.
