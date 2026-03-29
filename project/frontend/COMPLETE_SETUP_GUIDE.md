# 🫁 LungAI Frontend - Complete Setup & Usage Guide

**Status:** Production Ready ✅  
**Version:** 1.0.0  
**Tech Stack:** React 18 + Tailwind CSS 3  

---

## 📋 Overview

This is a **complete, professional-grade frontend** for the Lung Nodule Detection and Clinical Reporting System built with:

- ⚛️ **React 18** - Modern UI framework
- 🎨 **Tailwind CSS** - Utility-first styling
- 🔗 **React Router** - Client-side routing
- 🌐 **Axios** - HTTP client
- 💬 **React Hot Toast** - Notifications
- 🎯 **Lucide Icons** - Icon library

All pages are **fully responsive** (mobile, tablet, desktop) and follow medical UI best practices.

---

## 🚀 Installation

### Step 1: Prerequisites

```bash
# Check Node.js installation (requires 16+)
node --version    # Should be v16.0.0 or higher
npm --version     # Should be v8+
```

If not installed: [Download Node.js](https://nodejs.org)

### Step 2: Install Dependencies

```bash
cd frontend
npm install
```

This installs:
- react, react-dom, react-router-dom
- axios (HTTP client)
- tailwindcss, postcss, autoprefixer
- lucide-react (icons)
- react-hot-toast (notifications)

### Step 3: Configuration

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# REQUIRED: Flask API URL
REACT_APP_API_URL=http://localhost:5000/api

# Optional
REACT_APP_ENV=development
```

**For Production:**
```env
REACT_APP_API_URL=https://your-domain.com/api
REACT_APP_ENV=production
```

### Step 4: Start Development Server

```bash
npm start
```

Open browser: **http://localhost:3000**

---

## 📁 Project Structure

```
frontend/
│
├── src/
│   ├── api/
│   │   └── client.js               # Axios API client
│   │
│   ├── components/
│   │   ├── common/
│   │   │   └── UI.jsx              # UI components (Button, Card, etc.)
│   │   └── layout/
│   │       └── MainLayout.jsx      # Sidebar + main layout
│   │
│   ├── context/
│   │   └── AuthContext.jsx         # Auth state management
│   │
│   ├── pages/
│   │   ├── LoginPage.jsx           # Login & Register
│   │   ├── DashboardPage.jsx       # Main dashboard
│   │   ├── UploadScanPage.jsx      # File upload
│   │   ├── ResultsPage.jsx         # Analysis results
│   │   ├── ReportPage.jsx          # Clinical report
│   │   └── HistoryPage.jsx         # Scan history
│   │
│   ├── App.jsx                      # Main app with routing
│   ├── main.jsx                     # React entry point
│   └── index.css                    # Tailwind & global styles
│
├── public/
│   └── index.html
│
├── .env.example                      # Environment template
├── .gitignore
├── package.json
├── tailwind.config.js               # Tailwind configuration
├── postcss.config.js                # PostCSS configuration
├── vite.config.js                   # Vite build config (alternative)
│
├── README.md                         # Quick start guide
├── FRONTEND_INTEGRATION_GUIDE.md    # Integration with Flask backend
├── COMPONENT_SHOWCASE.md            # UI component documentation
│
├── setup.sh                          # Setup script (Linux/Mac)
└── setup.bat                         # Setup script (Windows)
```

---

## 🎯 Page Descriptions

### 1. **Login & Register Pages**

**URLs:** `/login`, `/register`

**Features:**
- Clean centered card layout
- Email/password validation
- Remember me checkbox
- Forgot password link
- Logo and branding
- Demo credentials hint

**Access:** Public (not logged in users)

```jsx
<LoginPage>
  - Email input
  - Password input
  - Login button
  - Register link
</LoginPage>
```

### 2. **Dashboard Page**

**URL:** `/dashboard`

**Features:**
- Welcome greeting
- Summary statistics:
  - Total scans analyzed
  - Nodules detected
  - Reports generated
- Quick action button to upload
- Recent activity section

**Access:** Protected (logged-in users only)

### 3. **Upload Scan Page**

**URL:** `/upload`

**Features:**
- Drag-and-drop upload zone
- Click to select file
- Supported formats display
- File preview with size
- Upload progress bar
- Auto-analysis after upload
- Tips for best results

**Supported Formats:**
- `.nii` - NIfTI
- `.nii.gz` - Compressed NIfTI
- `.mhd` - MHD 3D medical format
- `.dcm` - DICOM
- `.jpg`, `.png` - Regular images
- Max size: 500 MB

### 4. **Results Page**

**URL:** `/results/:scanId`

**Features:**
- CT scan viewer (slice navigation)
- Detected nodules list
- Risk level badges (High/Medium/Low)
- Confidence scores
- Nodule size and location
- Re-analyze button
- Generate report button

**Sidebar:**
- Summary statistics
- High-risk warning
- Action buttons

### 5. **Report Page**

**URL:** `/reports/:scanId`

**Features:**
- Clinical report display
- Patient information
- Detailed findings
- Nodule table
- Risk assessment
- Recommendations
- Clinical guidelines
- Medical disclaimer
- Download PDF button

### 6. **History Page**

**URL:** `/history`

**Features:**
- Scan management table
- Columns: ID, Date, Filename, Status, Nodules
- View results action
- Download report action
- Delete scan action
- Statistics cards
- Filter/sort support

---

## 🔐 Authentication Flow

```
User Input → Login Page
          ↓
    POST /api/auth/login
          ↓
Backend validates credentials
          ↓
Returns JWT token + user data
          ↓
Frontend stores in localStorage
          ↓
Redirect to /dashboard
```

**Token Management:**
- Stored in `localStorage`
- Sent in `Authorization: Bearer {token}` header
- Auto-clears on logout
- Validated on 401 errors

---

## 🔗 API Integration

### Required Flask Endpoints

Your Flask backend must expose these endpoints with `/api` prefix:

```javascript
// Authentication
POST   /api/auth/login              → { token, user }
POST   /api/auth/register           → { token, user }
POST   /api/auth/logout             → { success: true }

// User
GET    /api/user/profile            → { user: {...} }
PUT    /api/user/profile            → { user: {...} }
GET    /api/user/stats              → { total_scans, total_nodules, ... }

// Scans
GET    /api/scans                   → { scans: [...] }
POST   /api/scans/upload            → { scan_id: "..." }
GET    /api/scans/{scanId}          → { scan: {...} }
DELETE /api/scans/{scanId}          → { success: true }

// Analysis
POST   /api/analyze/{scanId}        → { detections: [...], avg_confidence: 0.85 }
GET    /api/results/{scanId}        → { detections: [...], total_detections: 3 }

// Reports
POST   /api/generate_report/{scanId}→ { report_id: "..." }
GET    /api/report/{scanId}         → { report: {...} }
GET    /api/report/{scanId}/download→ PDF blob
```

### Example Flask Setup

```python
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3000"],
    "methods": ["GET", "POST", "PUT", "DELETE"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    # Validate credentials
    token = generate_jwt_token(user_id)
    return jsonify({
        'token': token,
        'user': {'id': user_id, 'email': email, 'name': name}
    })

# ... more endpoints
```

See `FRONTEND_INTEGRATION_GUIDE.md` for complete backend setup.

---

## 🎨 Customization

### 1. Change Colors

Edit `tailwind.config.js`:

```javascript
colors: {
  primary: "#2563EB",      // Change blue
  secondary: "#1E40AF",
  success: "#10B981",      // Change green
  danger: "#EF4444",       // Change red
  warning: "#F59E0B",      // Change orange
}
```

### 2. Change Fonts

```javascript
// tailwind.config.js
fontFamily: {
  sans: ['Inter', 'Roboto', 'sans-serif'],
}
```

### 3. Add New Pages

```jsx
// 1. Create page in src/pages/MyPage.jsx
export const MyPage = () => {
  return <MainLayout>...</MainLayout>
}

// 2. Add route in src/App.jsx
<Route path="/mypage" element={<ProtectedRoute component={MyPage} />} />

// 3. Add nav link in src/components/layout/MainLayout.jsx
```

### 4. Modify Components

All components in `src/components/common/UI.jsx` can be customized:

```jsx
// Edit Button component
export const Button = ({ variant = 'primary', size = 'md' }) => {
  // Customize styling, behavior, etc.
}
```

---

## 🚀 Building for Production

### Build Optimized Version

```bash
npm run build
```

Creates `build/` folder with:
- Minified JavaScript
- Optimized CSS
- Optimized images
- Production-ready assets

### Deployment Options

#### Option 1: Netlify

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=build
```

#### Option 2: Vercel

```bash
npm install -g vercel
vercel --prod
```

#### Option 3: Docker

```dockerfile
# Build stage
FROM node:18 as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

Build & run:
```bash
docker build -t lungai-frontend .
docker run -p 80:80 lungai-frontend
```

#### Option 4: AWS S3 + CloudFront

```bash
npm run build
aws s3 sync build/ s3://your-bucket-name
# Configure CloudFront distribution
```

---

## 📦 Build Variants

### With Vite (Recommended for faster builds)

```bash
# Install Vite dependencies
npm install --save-dev vite @vitejs/plugin-react

# Update vite.config.js (already included)
# Update package.json scripts to use vite

npm start      # Dev server
npm run build  # Production build
```

### With Create React App

```bash
# Use react-scripts (already in package.json)
npm start
npm run build
```

---

## 🌐 Environment Variables

### Available Variables

```env
# Required - Flask API URL
REACT_APP_API_URL=http://localhost:5000/api

# Environment (development/production)
REACT_APP_ENV=development

# Optional - Analytics tracking ID
REACT_APP_ANALYTICS_ID=

# Optional - Feature flags
REACT_APP_ENABLE_ADVANCED_VIEWER=false
REACT_APP_ENABLE_DICOM_VIEWER=false
```

### Loading Environment Variables

```javascript
// In any component
const apiUrl = process.env.REACT_APP_API_URL;
const env = process.env.REACT_APP_ENV;
```

---

## 🐛 Troubleshooting

### CORS Errors: "Access to XMLHttpRequest blocked"

**Problem:** Frontend can't reach Flask backend

**Solution:**
1. Ensure Flask has CORS enabled
2. Check `REACT_APP_API_URL` in `.env`
3. Flask must be running on correct port

```python
# Flask backend
from flask_cors import CORS
CORS(app)
```

### 404 "Not Found" errors

**Problem:** API endpoints don't exist

**Solution:**
1. Verify Flask routes are defined
2. Check endpoint URL format
3. Ensure backend is running: `python app.py`

### Authentication fails

**Problem:** Can't login or token not working

**Solution:**
1. Check credentials are correct
2. Verify JWT implementation in backend
3. Clear localStorage: `localStorage.clear()`
4. Check token expiration

### Slow file uploads

**Problem:** Large files take too long to upload

**Solution:**
1. Implement chunked upload
2. Check network conditions
3. Increase timeout
4. Client-side file compression

### Component not updating

**Problem:** Changes to state not reflecting

**Solution:**
1. Check React DevTools
2. Verify state management
3. Use `useEffect` for side effects
4. Ensure proper key attributes on lists

---

## 📱 Responsive Design

The UI is fully responsive:

```
Desktop:   1024px+ (full sidebar)
Tablet:    768px - 1023px (collapsible sidebar)
Mobile:    < 768px (hamburger menu)
```

Sidebar auto-collapses on smaller screens with hamburger menu button.

---

## 🔒 Security Best Practices

1. ✅ **HTTPS only in production** - Always use HTTPS
2. ✅ **Secure token storage** - Keep JWT in localStorage
3. ✅ **CORS properly configured** - Only allow trusted origins
4. ✅ **Input validation** - Validate all user inputs
5. ✅ **XSS prevention** - React auto-escapes content
6. ✅ **CSRF protection** - Use SameSite cookies
7. ✅ **Content Security Policy** - Add CSP headers
8. ✅ **Dependency audit** - Run `npm audit` regularly

---

## 📊 Performance Tips

1. **Code Splitting** - Routes load on demand
2. **Lazy Loading** - Images load when visible
3. **Caching** - API responses cached
4. **Minification** - Production builds minified
5. **Tree Shaking** - Unused code removed
6. **Asset Optimization** - Images optimized
7. **Bundle Analysis** - Run `npm run analyze`

---

## 🎓 Learning Resources

- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)
- [Axios](https://axios-http.com)
- [Components docs](./COMPONENT_SHOWCASE.md)
- [Integration guide](./FRONTEND_INTEGRATION_GUIDE.md)

---

## 📝 Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/new-feature
```

### 2. Make Changes

```bash
npm start              # Start dev server
# Edit files
# Test in browser
```

### 3. Build & Test

```bash
npm run build          # Build for production
# Test build locally
```

### 4. Commit & Push

```bash
git add .
git commit -m "Add new feature"
git push origin feature/new-feature
```

### 5. Create Pull Request

Opens PR for code review before merging to `main`.

---

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy Frontend
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: '18'
      - run: npm install
      - run: npm run build
      - run: npm test
```

---

## 📞 Support & Issues

- Check [COMPONENT_SHOWCASE.md](./COMPONENT_SHOWCASE.md) for component usage
- See [FRONTEND_INTEGRATION_GUIDE.md](./FRONTEND_INTEGRATION_GUIDE.md) for backend integration
- Review [README.md](./README.md) for quick start

---

## ✅ Checklist for Production

- [ ] `.env` configured with production API URL
- [ ] HTTPS enabled on backend
- [ ] CORS configured for production domain
- [ ] Environment variables set
- [ ] Build tested locally (`npm run build`)
- [ ] No console errors or warnings
- [ ] All pages tested manually
- [ ] Token refresh working
- [ ] Error handling working
- [ ] Responsive design tested on mobile
- [ ] Performance acceptable (< 3s load)
- [ ] Security audit passed (`npm audit`)
- [ ] Deployed successfully

---

## 🎉 Summary

You now have a **complete, production-ready** frontend for the Lung Nodule Detection System!

### Next Steps

1. ✅ Setup: `npm install && npm start`
2. ✅ Configure: Update `.env` with your API URL
3. ✅ Develop: Make it your own!
4. ✅ Deploy: Build and deploy to your hosting
5. ✅ Connect: Integrate with Flask backend

---

**Need Help?**
- Check the documentation files
- Review component examples
- Check console for error messages
- Verify Flask backend is running
- Test API endpoints with curl or Postman

---

**Created:** 2024  
**Status:** Production Ready ✅  
**Next Update:** As needed
