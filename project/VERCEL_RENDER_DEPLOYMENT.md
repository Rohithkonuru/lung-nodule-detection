# Vercel + Render Deployment Guide

This setup uses:
- Render for backend API + PostgreSQL
- Vercel for frontend React app

## Files added for this flow

- `render.yaml` for Render Blueprint deployment
- `frontend/vercel.json` for SPA route fallback
- `frontend/.env.vercel.example` for required Vercel environment variables

## 1) Deploy backend on Render

1. Push repository changes.
2. In Render, create a new Blueprint and point it to this repo root.
3. Render reads `render.yaml` and creates:
   - Web service: `lung-backend-api`
   - Postgres database: `lung-postgres`
4. In Render service environment variables, set:
   - `SECRET_KEY` to a long random value
   - `CORS_ORIGINS` to your Vercel app URL, e.g. `https://your-app.vercel.app`
5. Wait for deployment, then verify:
   - `https://<your-render-service>.onrender.com/health`

## 2) Deploy frontend on Vercel

1. In Vercel, import this repository.
2. Set project root directory to `frontend`.
3. Framework preset: Vite.
4. Build command: `npm run build`.
5. Output directory: `dist`.
6. Add environment variable:
   - `VITE_API_URL=https://<your-render-service>.onrender.com/api/v1`
7. Deploy and open your Vercel URL.

## 3) Final CORS update

After Vercel URL is final, update Render `CORS_ORIGINS` to include it exactly.

Example:
`https://your-app.vercel.app,https://www.your-domain.com`

## 4) Smoke test checklist

- Open frontend URL and confirm login/register loads.
- Register a new user and confirm token-based login works.
- Upload a scan and run analysis.
- Confirm reports/history load.

## Notes

- Backend demo user creation is now skipped when `APP_ENV=production`.
- Render database URLs are normalized automatically for SQLAlchemy + psycopg.
- Ensure model weights file exists in repo at `models/retinanet_best.pth` or update `MODEL_WEIGHTS_PATH` and `RETINANET_MODEL_PATH` in Render.
