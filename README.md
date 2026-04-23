# ORObOT

ORObOT is a FastAPI assistant with a web UI, chat history, RAG-backed knowledge lookup, voice input, and several desktop automation features.

## Run locally

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` and use `http://127.0.0.1:8000/health` for a health check.

## Environment variables

Copy `.env.example` and set the values you need:

- `ASSEMBLYAI_API_KEY` for speech-to-text
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` for email

## Deploy

### Option 1: Docker

```bash
docker build -t orobot .
docker run -p 8000:8000 --env-file .env orobot
```

### Option 2: Render

This repo includes `render.yaml` and a `Dockerfile`, so you can deploy it as a Docker web service.

## Hosted deployment notes

When deployed to a cloud server, browser automation, microphone access, camera access, local calculator control, and similar desktop-only actions may not work because they require direct access to a user machine. The web UI, chat flow, RAG features, database, and health endpoint remain deployable.
