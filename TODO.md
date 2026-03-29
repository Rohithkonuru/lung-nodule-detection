# Lung Nodule Detection Deployment TODO
Current working directory: d:/project (project/ contains app)

## Approved Plan Steps (Vercel Frontend + Render Backend+DB)

### 1. Prerequisites & Verification ✅ [Verified]
- [x] Git repository: Initialized on main, ready for commit/push (untracked files present)
- [x] models/retinanet_best.pth: Exists (~547KB in project/models/)
- [x] Local frontend build: SUCCESS - npm install & npm run build completed, dist/ generated (395KB JS, 23KB CSS)
- [x] Backend configs: Dockerfile.prod, render.yaml production-ready (deps install succeeded)
- [x] Backend deps: All requirements.txt + requirements-ml.txt satisfied (torch, torchvision, SimpleITK ready)
- [ ] Backend server test: Run manually `cd project/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000` then http://localhost:8000/health OK

Next step: 2. Git Setup

Next step: 2. Git Setup

### 2. Git Setup
- [ ] ...

### 2. Git Setup
- [ ] Initialize git if needed: git init, create .gitignore if missing
- [ ] Create new public GitHub repo 'lung-nodule-detection' (or user-specified)
- [ ] git add . && git commit -m "Initial deployment commit" && git push origin main

### 3. Deploy Backend + DB on Render (Blueprint)
- [ ] Go to render.com/dashboard -> New Blueprint -> Connect GitHub repo
- [ ] Render auto-deploys from render.yaml: lung-backend-api (Python web), lung-postgres (DB), 10GB disk
- [ ] Set manual env vars in Render: SECRET_KEY (generate strong one), CORS_ORIGINS initially '*'
- [ ] Note Backend URL (e.g. https://lung-backend-api-xxx.onrender.com), confirm /health

### 4. Deploy Frontend on Vercel
- [ ] Go to vercel.com/dashboard -> Import GitHub repo
- [ ] Settings: Root dir = 'frontend', Framework=Vite, Build cmd='npm run build', Output dir='dist'
- [ ] Env var: VITE_API_URL = [Render Backend URL]/api/v1
- [ ] Deploy, note Frontend URL (e.g. https://lung-nodule-detection.vercel.app)

### 5. Connect & Test
- [ ] Update Render CORS_ORIGINS = [Vercel Frontend URL]
- [ ] Test: Register/login on frontend -> Upload scan -> Analysis/report works
- [ ] Update this TODO with final URLs

### 6. Completion
- [ ] Run attempt_completion with URLs + test commands

Next step: 1. Prerequisites & Verification

