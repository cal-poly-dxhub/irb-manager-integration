# Compliance Assistant

An AI-powered tool that helps university researchers fill out Cayuse IRB (Human Ethics) submission forms. The app provides a split-view interface with a chat panel (left) and a live form preview (right), along with an activity drawer showing real-time agent reasoning.

## Prerequisites

- Node.js (v20+)
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- AWS credentials configured with access to Amazon Bedrock (Claude + Titan Embeddings)

## Project Structure

```
apps/compliance-assistant/       # React frontend (Vite)
services/compliance-assistant-api/  # Flask backend (Bedrock agent)
data/compliance-assistant/       # Field prompts, embeddings, test uploads
```

## Running Locally

### Backend (Flask API on port 5002)

```bash
cd services/compliance-assistant-api
uv run python run.py
```

### Frontend (Vite dev server on port 5173)

```bash
cd apps/compliance-assistant
npm run dev
```

The Vite dev server proxies `/api` requests to the backend on port 5002.

### Quick Start

From the repo root, run the demo script:

```bash
./apps/compliance-assistant/demo.sh
```

This starts both the backend and frontend in a single terminal. Press `Ctrl+C` to stop both.

## Demo Test Uploads

Sample research documents are in `data/compliance-assistant/test-uploads/`:

| File | Description |
|------|-------------|
| `study4_yoga_anxiety_athletes_demo.txt/pdf` | Yoga RCT study with **funding info removed** (triggers early follow-up question) |
| `study4_yoga_anxiety_athletes_demo_no_counts.txt/pdf` | Same study with **participant counts removed** |
| `study4_yoga_anxiety_athletes.txt/pdf` | Complete version with all info |
| `study1-3` | Other sample studies |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPLATE_PATH` | Auto-detected | Path to `.etemplate` form file |
| `DATA_DIR` | Auto-detected | Path to `data/compliance-assistant/` |
| `EMBEDDINGS_DIR` | Auto-detected | Path to embeddings directory |
| `USE_MOCK` | `false` | Set to `true` to use mock agent (no AWS needed) |
