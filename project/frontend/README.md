# 🫁 LungAI Frontend

Modern, responsive React + Tailwind CSS web interface for the **Lung Nodule Detection and Clinical Reporting System**.

## ✨ Features

- 🔐 **Secure Authentication** - Login/Register with JWT tokens
- 📤 **Easy Upload** - Drag-and-drop file upload support
- 🧠 **AI Analysis** - Real-time CT scan analysis with progress tracking
- 👁️ **Results Viewer** - Interactive CT slice navigation
- 📄 **Clinical Reports** - Auto-generated PDF reports
- 📊 **Scan History** - Full scan management and download
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- 🎨 **Medical UI** - Professional clinical appearance
- ⚡ **Fast Performance** - Optimized React components
- 🛡️ **Error Handling** - Toast notifications and validation

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm start

# Open browser to http://localhost:3000
```

### Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Update API URL in `.env`:
```env
VITE_API_URL=http://localhost:8000/api/v1
```

### Build for Production

```bash
npm run build
```

## 📦 Tech Stack

- **React 18** - UI framework
- **Tailwind CSS** - Styling
- **React Router** - Navigation
- **Axios** - HTTP client
- **Lucide React** - Icons
- **React Hot Toast** - Notifications

## 🏗️ Project Structure

```
src/
├── components/
│   ├── common/
│   │   └── UI.jsx              # Reusable UI components
│   └── layout/
│       └── MainLayout.jsx      # Sidebar & layout
├── pages/
│   ├── LoginPage.jsx
│   ├── DashboardPage.jsx
│   ├── UploadScanPage.jsx
│   ├── ResultsPage.jsx
│   ├── ReportPage.jsx
│   └── HistoryPage.jsx
├── context/
│   └── AuthContext.jsx         # Auth state
├── api/
│   └── client.js               # API client
└── App.jsx                      # Main app
```

## 🔗 API Integration

The frontend connects to the Flask backend at the configured `REACT_APP_API_URL`.

**Required API Endpoints:**

```
GET    /api/user/stats              - Dashboard stats
POST   /api/auth/login              - User login
POST   /api/auth/register           - User registration
GET    /api/scans                   - List scans
POST   /api/scans/upload            - Upload scan
GET    /api/scans/{scanId}          - Get scan details
POST   /api/analyze/{scanId}        - Run analysis
GET    /api/results/{scanId}        - Get results
POST   /api/generate_report/{scanId}- Generate report
GET    /api/report/{scanId}         - Get report
```

See `FRONTEND_INTEGRATION_GUIDE.md` for complete integration details.

## 📱 Pages

### 1. Login & Register
- Clean card layout
- Email/password validation
- Demo credentials provided

### 2. Dashboard
- Welcome message
- Summary cards (scans, nodules, reports)
- Quick action buttons

### 3. Upload Scan
- Drag-and-drop upload
- Supported formats: .nii, .mhd, .dcm, .png, .jpg
- Upload progress bar
- Auto-analysis after upload

### 4. Results
- CT scan viewer
- Slice navigation
- Detected nodules list
- Risk level badges

### 5. Report
- Clinical findings
- Nodule table
- Risk assessment
- PDF download
- Medical disclaimer

### 6. History
- Scan management table
- View/download/delete actions
- Statistics cards

## 🎨 Theming

Edit `tailwind.config.js` to customize colors:

```javascript
colors: {
  primary: "#2563EB",      // Main blue
  secondary: "#1E40AF",    // Dark blue
  success: "#10B981",      // Green
  danger: "#EF4444",       // Red
  warning: "#F59E0B",      // Orange
}
```

## 🔐 Authentication

- JWT token stored in localStorage
- Auto-token refresh on 401 errors
- Logout clears credentials
- Protected routes require login

## 📊 Component Library

Reusable UI components in `src/components/common/UI.jsx`:

```javascript
<Button variant="primary" size="lg">Click me</Button>
<Card><h2>Content</h2></Card>
<Alert type="success" title="Success!" message="Operation completed" />
<Badge variant="danger">High Risk</Badge>
<Input label="Email" type="email" placeholder="..." />
<Spinner size="md" />
<ProgressBar progress={75} />
<Modal isOpen={true} title="Dialog">...</Modal>
```

## 🚀 Deployment

### Netlify
```bash
npm run build
netlify deploy --prod --dir=build
```

### Vercel
```bash
npm run build
vercel --prod
```

### Docker
```dockerfile
FROM node:18 as builder
WORKDIR /app
COPY package*.json ./
RUN npm install && npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| CORS errors | Enable CORS in Flask backend |
| 404 API errors | Verify Flask running on correct port |
| Auth fails | Check `REACT_APP_API_URL` configuration |
| Slow uploads | Check network, implement chunked upload |
| Token expires | Clear localStorage and re-login |

## 📚 Documentation

- [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) - Complete integration guide
- [React Docs](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)

## 📝 Environment Variables

```env
# Required
REACT_APP_API_URL=http://localhost:5000/api

# Optional
REACT_APP_ENV=development
REACT_APP_ANALYTICS_ID=your-id
REACT_APP_ENABLE_ADVANCED_VIEWER=false
```

## 🎯 Next Steps

After installation:

1. ✅ Install dependencies: `npm install`
2. ✅ Configure `.env` with API URL
3. ✅ Start dev server: `npm start`
4. ✅ Ensure Flask backend is running
5. ✅ Test login with demo credentials
6. ✅ Upload a test scan

## 📞 Support

Refer to the main project README for additional support and documentation.

---

**Status:** Production Ready ✅
**Last Updated:** 2024
