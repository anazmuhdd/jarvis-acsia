# Pulse AI — Intelligence Backend

A high-performance FastAPI backend that generates role-specific search queries and aggregates professional news articles from Google News.

## Tech Stack

| Layer           | Technology                     |
| --------------- | ------------------------------ |
| Framework       | FastAPI + Uvicorn              |
| HTTP Client     | httpx (async)                  |
| HTML Parsing    | BeautifulSoup4, selectolax     |
| LLM (topic gen) | NVIDIA NIM (OpenAI-compatible) |
| News Source     | Google News RSS                |

---

## Deploying to Render

### One-click (recommended)

1. Push this `backend/` folder (or the full monorepo) to GitHub.
2. In Render → **New → Web Service** → connect your repo.
3. Render will auto-detect `render.yaml` and configure:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Go to **Environment** tab and add:

| Key              | Value                                           |
| ---------------- | ----------------------------------------------- |
| `NVIDIA_API_KEY` | Your NVIDIA API Key                             |
| `NVIDIA_MODEL`   | `qwen/qwen3-coder-480b-a35b-instruct` (default) |

5. Click **Deploy** — done. ✅

---

## Manual setup (any server)

```bash
# 1. Clone & enter backend dir
git clone <your-repo> && cd backend

# 2. Create virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your NVIDIA_API_KEY

# 5. Start server
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Environment Variables

| Variable         | Required | Default                               | Description                     |
| ---------------- | -------- | ------------------------------------- | ------------------------------- |
| `NVIDIA_API_KEY` | ✅       | -                                     | Your NVIDIA API Key             |
| `NVIDIA_MODEL`   | ❌       | `qwen/qwen3-coder-480b-a35b-instruct` | Model name for topic generation |

Copy `.env.example` → `.env` and fill in values. **Never commit `.env` to git.**

---

## API Reference

### `GET /api/news`

Fetches top articles for one or more search queries.

**Query Parameters**

| Param  | Required | Description                    |
| ------ | -------- | ------------------------------ |
| `q`    | ✅       | Comma-separated search queries |
| `role` | ❌       | Professional role              |

---

### `POST /api/generate-topics`

Uses an LLM to generate 5 role-tailored Google News search queries.

**Request Body**

```json
{
  "role": "AI Engineer",
  "department": "Technology",
  "teams": ["ML Platform", "Infra"]
}
```

---

### `GET /debug/visualizer`

HTML page for visually browsing decoded news cards. Useful for testing.
