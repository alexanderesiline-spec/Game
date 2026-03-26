# PanelForge — AI Comic Generator

Turn any story into manga, manhwa, or western comics using AI.

## What makes this different

- **Character consistency** — reference images generated once per character, used for all subsequent panels
- **Smart story parsing** — Claude analyzes pacing, emotion, and scene composition (not just slicing text)
- **Three styles** — Manga (B&W ink), Manhwa (full color webtoon), Western Comic
- **Three input modes** — paste text, upload PDF/EPUB/TXT, or use the interactive concept generator

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python + FastAPI |
| Story AI | Claude Opus 4.6 (adaptive thinking) |
| Image Gen | FLUX.1 via Replicate API (no GPU needed) |
| Frontend | Next.js 14 + TypeScript + Tailwind |
| Queue | Redis |

## Quick Start

### 1. Get API keys

- **Anthropic API key**: https://console.anthropic.com
- **Replicate API token**: https://replicate.com/account/api-tokens

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Run

```bash
docker-compose up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your keys
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/concepts/start` | Start interactive concept Q&A |
| `POST` | `/api/concepts/continue` | Continue Q&A session |
| `POST` | `/api/stories/text` | Create story from pasted text |
| `POST` | `/api/stories/upload` | Upload PDF/EPUB/TXT |
| `POST` | `/api/comics/generate` | Start comic generation job |
| `GET`  | `/api/comics/{id}` | Poll job status + progress |
| `GET`  | `/api/comics/{id}/pages` | Get all page/panel data |

## Generation Pipeline

```
Story Text
    │
    ├─ 1. Extract characters + visual descriptions (Claude)
    ├─ 2. Break story into panels with layout/mood/dialogue (Claude)
    ├─ 3. Generate character reference images (FLUX)
    ├─ 4. Generate all panels with consistency (FLUX + img2img)
    ├─ 5. Assemble pages with speech bubbles (Pillow)
    └─ 6. Export CBZ + webtoon strip
```

## Selling / Licensing

This is structured for easy SaaS deployment:
- Add authentication (JWT is pre-wired in dependencies.py)
- Add rate limiting per user/tier
- Replace in-memory stores with PostgreSQL
- Add Stripe for billing
- Deploy backend on Railway/Fly.io, frontend on Vercel
