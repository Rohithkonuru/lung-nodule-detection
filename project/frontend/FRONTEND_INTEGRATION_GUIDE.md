# Frontend Integration Guide

## 🚀 Quick Start

This is a **React + Tailwind CSS** frontend for the Lung Nodule Detection System. Follow these steps to integrate with your Flask backend.

---

## 📦 Installation

### 1. Prerequisites
- Node.js 16+ and npm
- Flask backend running on `http://localhost:5000`
- Python backend configured with API endpoints

### 2. Install Dependencies

```bash
cd frontend
npm install
```

### 3. Environment Setup

Create a `.env` file in the `frontend/` directory:

```env
REACT_APP_API_URL=http://localhost:5000/api
REACT_APP_ENV=development
```

**For production:**
```env
REACT_APP_API_URL=https://your-domain.com/api
REACT_APP_ENV=production
```

### 4. Start Development Server

```bash
npm start
```

The app will open at `http://localhost:3000`

---

## 🔗 API Integration

The frontend communicates with Flask backend via these endpoints:

### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration
- `POST /api/auth/logout` - User logout

### Scans
- `GET /api/scans` - List user's scans
- `POST /api/scans/upload` - Upload new scan
- `GET /api/scans/{scanId}` - Get scan details
- `DELETE /api/scans/{scanId}` - Delete scan

### Analysis
- `POST /api/analyze/{scanId}` - Run analysis
- `GET /api/results/{scanId}` - Get analysis results

### Reports
- `POST /api/generate_report/{scanId}` - Generate report
- `GET /api/report/{scanId}` - Get report
- `GET /api/report/{scanId}/download` - Download PDF

### User
- `GET /api/user/profile` - Get user profile
- `PUT /api/user/profile` - Update profile
- `GET /api/user/stats` - Get dashboard stats

---

## 🔐 Flask Backend Setup

Update your Flask `app.py` to expose these endpoints:

### Required Flask Routes

```python
# Authentication
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    # Authenticate user
    return jsonify({'token': token, 'user': user_data})

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    # Create user account
    return jsonify({'token': token, 'user': user_data})

# Scans
@app.route('/api/scans', methods=['GET'])
@token_required
def api_list_scans():
    # Return user's scans
    return jsonify(scans_list)

@app.route('/api/scans/upload', methods=['POST'])
@token_required
def api_upload_scan():
    file = request.files['file']
    # Save and process file
    return jsonify({'scan_id': scan_id})

@app.route('/api/analyze/<scan_id>', methods=['POST'])
@token_required
def api_analyze(scan_id):
    # Run detection model
    return jsonify({'detections': results})

@app.route('/api/report/<scan_id>', methods=['GET'])
@token_required
def api_get_report(scan_id):
    # Generate/retrieve report
    return jsonify({'report': report_data})
```

### Enable CORS

```python
from flask_cors import CORS

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "https://yourdomain.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

---

## 🏗️ Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   └── UI.jsx              # Reusable UI components
│   │   └── layout/
│   │       └── MainLayout.jsx      # Main layout with sidebar
│   ├── pages/
│   │   ├── LoginPage.jsx           # Login/Register
│   │   ├── DashboardPage.jsx       # Main dashboard
│   │   ├── UploadScanPage.jsx      # File upload
│   │   ├── ResultsPage.jsx         # Analysis results
│   │   ├── ReportPage.jsx          # Clinical report
│   │   └── HistoryPage.jsx         # Scan history
│   ├── context/
│   │   └── AuthContext.jsx         # Auth state management
│   ├── api/
│   │   └── client.js               # API client
│   ├── App.jsx                      # Main app component
│   ├── main.jsx                     # React entry point
│   └── index.css                    # Tailwind imports
├── package.json
├── tailwind.config.js
├── postcss.config.js
└── index.html
```

---

## 🎨 Customization

### Change Color Scheme

Edit `tailwind.config.js`:

```javascript
theme: {
  extend: {
    colors: {
      primary: "#2563EB",      // Change primary blue
      secondary: "#1E40AF",    // Change secondary blue
      danger: "#EF4444",       // Change danger red
    },
  },
},
```

### Add Custom Fonts

```javascript
// tailwind.config.js
theme: {
  extend: {
    fontFamily: {
      sans: ['Inter', 'sans-serif'],
    },
  },
},
```

### Add New Pages

1. Create component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add navigation link in `src/components/layout/MainLayout.jsx`

---

## 📱 Responsive Design

The UI is **fully responsive** and works on:
- ✅ Desktop (1024px+)
- ✅ Tablet (768px - 1023px)
- ✅ Mobile (< 768px)

Mobile menu automatically appears on small screens.

---

## 🔐 Authentication

### Login Flow

1. User enters credentials on `/login`
2. Frontend calls `POST /api/auth/login`
3. Backend returns JWT token
4. Token stored in localStorage
5. Token sent in `Authorization` header for protected routes

### Token Expiration

Implement token refresh:

```javascript
// src/api/client.js - Add refresh logic
apiClient.interceptors.response.use(
  response => response,
  async error => {
    if (error.response.status === 401) {
      // Refresh token or redirect to login
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

---

## 📊 Adding DICOM Viewer

For advanced CT scan viewing, integrate **Cornerstone.js**:

```bash
npm install cornerstone-core cornerstoneTools
```

Example integration in `src/components/DicomViewer.jsx`:

```javascript
import * as cornerstone from 'cornerstone-core';

export const DicomViewer = ({ imageUrl }) => {
  useEffect(() => {
    cornerstone.loadImage(imageUrl).then(image => {
      cornerstone.displayImage(element, image);
    });
  }, [imageUrl]);

  return <div id="dicom-viewer" style={{ width: '100%', height: '500px' }} />;
};
```

---

## 🚀 Deployment

### Build for Production

```bash
npm run build
```

Creates optimized production build in `build/` folder.

### Deploy Options

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
FROM node:18 as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Option 4: AWS S3 + CloudFront
```bash
npm run build
aws s3 sync build/ s3://your-bucket-name
```

---

## 🐛 Troubleshooting

### CORS Errors
Make sure Flask has CORS enabled and `REACT_APP_API_URL` is correct.

### Auth Token Issues
Clear localStorage: `localStorage.clear()` and re-login.

### 404 on API Routes
Verify Flask backend is running and routes are defined.

### Slow File Uploads
- Check network conditions
- Implement chunked upload for large files
- See comments in `UploadScanPage.jsx`

---

## 📚 Key Features

✅ **Authentication** - Secure login/register
✅ **File Upload** - Drag-and-drop support
✅ **Real-time Analysis** - Progress tracking
✅ **Results Viewer** - CT slice navigation
✅ **Report Generation** - PDF download
✅ **History** - Scan management
✅ **Responsive** - Mobile-friendly design
✅ **Dark UI** - Professional medical appearance
✅ **Error Handling** - Toast notifications
✅ **Loading States** - Skeleton screens

---

## 📖 Additional Resources

- [React Docs](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)
- [Axios](https://axios-http.com)
- [Lucide Icons](https://lucide.dev)

---

## 📞 Support

For issues or questions, please refer to the main project documentation.

**Generated:** 2024
**Status:** Production Ready ✅
