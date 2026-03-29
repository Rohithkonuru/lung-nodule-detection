# Lung Project

This repository contains a lung nodule detection and retrieval pipeline and a Flask-based web UI.

## Production deployment (VPS)

Use the dedicated production container stack documented in [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md).

Quick start:

```bash
cp .env.vps.example .env.vps
docker compose --env-file .env.vps -f docker-compose.vps.yml up -d --build
```

## Production deployment (Vercel + Render)

Use [VERCEL_RENDER_DEPLOYMENT.md](VERCEL_RENDER_DEPLOYMENT.md) to deploy frontend on Vercel and backend/Postgres on Render.

Blueprint and platform files:

- `render.yaml`
- `frontend/vercel.json`
- `frontend/.env.vercel.example`

## Web application (Flask)

To run the Flask web app (recommended):

1. Create and activate the project's virtual environment.
2. Install web dependencies:

```bash
pip install -r requirements-web.txt
```

3. Start the web server (development mode):

```powershell
& "C:/Users/91938/OneDrive/Desktop/lung project/.venv/Scripts/python.exe" "lung project\app.py"
```

The app will be available at http://localhost:5000 by default. To change the port, set the `FLASK_PORT` environment variable before launching.

## Notes

- If PyTorch model loading fails on Windows due to missing DLLs, install the Microsoft Visual C++ Redistributable (x64, 2015–2022).
- To precompute embeddings for retrieval (optional):

```bash
python -m src.compute_embeddings --images-dir data/processed/images --out data/processed/embeddings.npz --model models/baseline_model.pth
```
