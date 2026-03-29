# ⚡ Frontend Quick Start

Get the LungAI frontend running in **5 minutes**.

---

## 🚀 Quick Setup

### 1. Install Dependencies (1 min)

```bash
cd frontend
npm install
```

### 2. Configure API (1 min)

Create `.env`:

```bash
cp .env.example .env
```

Edit `.env`:
```env
REACT_APP_API_URL=http://localhost:5000/api
```

### 3. Start Dev Server (1 min)

```bash
npm start
```

Opens **http://localhost:3000** automatically.

### 4. Test Login

Demo credentials:
- Email: `demo@example.com`
- Password: `demo123`

### 5. Upload & Test (2 min)

1. Go to "Upload Scan"
2. Drag & drop or select a CT image
3. Wait for analysis
4. View results

---

## 📦 What's Included

✅ **7 Professional Pages**
- Login / Register
- Dashboard
- Upload Scan (with drag-and-drop)
- Results Viewer
- Clinical Report
- Scan History
- Sidebar Navigation

✅ **Complete Components**
- Buttons, Inputs, Cards, Badges
- Alerts, Spinners, Progress bars
- Modals, Loading skeletons
- All fully styled with Tailwind

✅ **Full Features**
- JWT Authentication
- API Integration
- Responsive design
- Error handling
- Loading states
- Toast notifications

---

## 🔗 Connect to Backend

Ensure your Flask backend is running:

```bash
python app.py
```

Backend should be on `http://localhost:5000` with these routes:

```
POST /api/auth/login              - Login
GET  /api/user/stats              - Dashboard stats
POST /api/scans/upload            - Upload scan
POST /api/analyze/{scanId}        - Start analysis
GET  /api/results/{scanId}        - Get results
POST /api/generate_report/{scanId}- Generate report
```

---

## 🎯 Project Structure

```
frontend/
├── src/
│   ├── pages/              # All 7 pages
│   ├── components/         # UI + Layout
│   ├── context/            # Auth state
│   ├── api/                # API calls
│   └── App.jsx             # Main app
├── package.json
├── .env                    # Configuration
└── FRONTEND_INTEGRATION_GUIDE.md  # Full integration docs
```

---

## 🛠️ Common Commands

```bash
npm start              # Start dev server (port 3000)
npm run build          # Build for production
npm test               # Run tests
npm audit              # Check dependencies
npm install            # Install packages
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 3000 in use | `npm start -- --port 3001` |
| API errors | Check `REACT_APP_API_URL` in `.env` |
| CORS errors | Enable CORS in Flask backend |
| Blank page | Check browser console for errors |
| npm not found | Install [Node.js](https://nodejs.org) |

---

## 📚 Documentation

- **[COMPLETE_SETUP_GUIDE.md](./COMPLETE_SETUP_GUIDE.md)** - Full setup & customization
- **[FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md)** - Backend integration
- **[COMPONENT_SHOWCASE.md](./COMPONENT_SHOWCASE.md)** - UI components reference
- **[README.md](./README.md)** - Project overview

---

## 🎨 Customize

**Change Colors:**
Edit `tailwind.config.js`:

```javascript
colors: {
  primary: "#2563EB",     // Change blue
  danger: "#EF4444",      // Change red
}
```

**Add Pages:**
1. Create component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add nav link in `src/components/layout/MainLayout.jsx`

---

## 📱 Features

- ✅ Drag-and-drop file upload
- ✅ Real-time CT analysis
- ✅ Interactive results viewer
- ✅ Auto-generated clinical reports
- ✅ Scan history & management
- ✅ Fully responsive design
- ✅ Dark theme ready
- ✅ Professional medical UI

---

## 🚀 Production Deployment

### Build

```bash
npm run build
```

### Deploy to Netlify

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=build
```

### Deploy to Docker

```bash
docker build -t lungai-frontend .
docker run -p 80:80 lungai-frontend
```

---

## ✅ Next Steps

1. ✅ Run `npm install`
2. ✅ Create `.env` with your API URL
3. ✅ Start Flask backend
4. ✅ Run `npm start`
5. ✅ Test login and upload
6. ✅ Customize colors/text as needed
7. ✅ Deploy when ready

---

## 🎉 You're Ready!

Frontend is production-ready and fully integrated.

**Questions?** Check the documentation files in this folder.

---

**Status:** ✅ Production Ready
**Tech:** React 18 + Tailwind CSS 3
**Time to Live:** 5 minutes
