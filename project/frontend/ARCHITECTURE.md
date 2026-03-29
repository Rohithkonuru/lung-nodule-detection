# 🏗️ Frontend Architecture

Complete architecture overview of the LungAI frontend.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                     End User (Browser)                       │
│                                                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ HTTP/HTTPS (REST API)
                 │
┌────────────────▼────────────────────────────────────────────┐
│                                                             │
│              React Frontend (Port 3000)                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                   App.jsx                           │  │
│  │  ├─ Router (React Router)                           │  │
│  │  ├─ Public Routes: /login, /register               │  │
│  │  ├─ Protected Routes: /dashboard, /upload, etc.    │  │
│  │  └─ AuthProvider (Authentication Context)          │  │
│  └─────────────────────────────────────────────────────┘  │
│         │                                    │              │
│         ├─ Pages                     Components             │
│         │                                    │              │
│         ├─ LoginPage                  UI Components         │
│         ├─ DashboardPage             ├─ Buttons            │
│         ├─ UploadScanPage            ├─ Cards              │
│         ├─ ResultsPage               ├─ Inputs             │
│         ├─ ReportPage                ├─ Alerts             │
│         └─ HistoryPage               ├─ Badges             │
│                                      ├─ Modals             │
│                                      ├─ Spinners           │
│                                      ├─ ProgressBars       │
│                                      └─ Skeletons          │
│                                           │                │
│                                      MainLayout             │
│                                      ├─ Sidebar             │
│                                      └─ Main Content        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │              API Client (Axios)                     │  │
│  │  ├─ authAPI          (login, register, logout)     │  │
│  │  ├─ scanAPI          (upload, list, delete)        │  │
│  │  ├─ analysisAPI      (analyze, getResults)         │  │
│  │  ├─ reportAPI        (generate, download)          │  │
│  │  └─ userAPI          (profile, stats)              │  │
│  └─────────────────────────────────────────────────────┘  │
│                          │                                 │
│  ┌─────────────────────────────────────────────────────┐  │
│  │           Context (State Management)                │  │
│  │           ├─ AuthContext                            │  │
│  │           │  ├─ user (current user)                │  │
│  │           │  ├─ loading (state)                    │  │
│  │           │  ├─ error (error messages)             │  │
│  │           │  ├─ login()  (function)                │  │
│  │           │  ├─ register() (function)              │  │
│  │           │  └─ logout() (function)                │  │
│  │           └─ localStorage (JWT token)               │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│                   Tailwind CSS Styling                      │
│                   Local Storage (JWT)                       │
│                   Toast Notifications                       │
│                                                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ REST API Calls (JSON)
                 │
┌────────────────▼────────────────────────────────────────────┐
│                                                             │
│          Flask Backend (Port 5000)                          │
│                                                             │
│  ├─ /api/auth/*           (Authentication)                │
│  ├─ /api/user/*           (User management)               │
│  ├─ /api/scans/*          (Scan management)               │
│  ├─ /api/analyze/*        (AI Analysis)                   │
│  ├─ /api/report/*         (Report generation)             │
│  └─ /api/results/*        (Result retrieval)              │
│                                                             │
│  SQLite Database                                           │
│  ├─ users table                                           │
│  ├─ scans table                                           │
│  ├─ detections table                                      │
│  ├─ reports table                                         │
│  └─ analysis_results table                                │
│                                                             │
│  ML Models                                                 │
│  ├─ RetinaNet (Object Detection)                          │
│  ├─ UNet (Segmentation)                                   │
│  └─ Preprocessing Pipeline                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Authentication Flow

```
LoginPage (user input)
    │
    ├─ Validate form
    │
    ├─ Send POST /api/auth/login
    │
    │ Flask Backend
    │ ├─ Hash password
    │ ├─ Check database
    │ └─ Generate JWT
    │
    ├─ Receive token + user data
    │
    ├─ Store in localStorage
    │
    ├─ Update AuthContext
    │
    └─ Redirect to /dashboard
```

### File Upload Flow

```
UploadScanPage (user selects file)
    │
    ├─ Validate file format
    ├─ Validate file size
    │
    ├─ Create FormData
    │
    ├─ Send POST /api/scans/upload
    │
    │ Show progress bar (0-100%)
    │
    │ Flask Backend
    │ ├─ Save file to disk
    │ ├─ Create scan record
    │ └─ Return scan_id
    │
    ├─ Receive scan_id
    │
    ├─ Auto-trigger analysis
    │ └─ POST /api/analyze/{scanId}
    │
    │ Flask processes CT volume
    │
    ├─ Redirect to /results/{scanId}
    │
    └─ Display detection results
```

### Report Generation Flow

```
ResultsPage (user clicks "Generate Report")
    │
    ├─ Send POST /api/generate_report/{scanId}
    │
    │ Flask Backend
    │ ├─ Retrieve analysis results
    │ ├─ Query RAG knowledge base
    │ ├─ Generate clinical text
    │ ├─ Create PDF
    │ └─ Store report record
    │
    ├─ Show success notification
    │
    ├─ Navigate to /reports/{scanId}
    │
    └─ Display report with download button
```

---

## Component Hierarchy

```
App
├─ AuthProvider
│  └─ Router
│     ├─ PublicRoute
│     │  ├─ LoginPage
│     │  └─ RegisterPage
│     │
│     └─ ProtectedRoute
│        ├─ DashboardPage
│        │  └─ MainLayout
│        │     ├─ Sidebar
│        │     ├─ Card
│        │     ├─ Badge
│        │     └─ Button
│        │
│        ├─ UploadScanPage
│        │  └─ MainLayout
│        │     ├─ Card
│        │     ├─ Input
│        │     ├─ Button
│        │     ├─ Alert
│        │     └─ ProgressBar
│        │
│        ├─ ResultsPage
│        │  └─ MainLayout
│        │     ├─ Card
│        │     ├─ Badge
│        │     ├─ Spinner
│        │     └─ Button
│        │
│        ├─ ReportPage
│        │  └─ MainLayout
│        │     ├─ Card
│        │     ├─ Button
│        │     └─ Alert
│        │
│        └─ HistoryPage
│           └─ MainLayout
│              ├─ Card
│              ├─ Badge
│              ├─ Button
│              └─ LoadingSkeleton

Sidebar (persistent)
├─ Logo
├─ Navigation Links
│  ├─ Dashboard
│  ├─ Upload Scan
│  ├─ Results
│  ├─ Reports
│  └─ History
└─ Logout Button
```

---

## State Management

### Global State (AuthContext)

```
AuthContext
├─ user
│  ├─ id
│  ├─ email
│  ├─ name
│  └─ created_at
│
├─ loading (boolean)
│
├─ error (string)
│
└─ Actions
   ├─ login(email, password)
   ├─ register(email, password, name)
   └─ logout()
```

### Local State (Component)

```
DashboardPage
├─ stats (useState)
│  ├─ total_scans
│  ├─ total_nodules
│  └─ total_reports
│
├─ loading (useState)
│
└─ useEffect (fetch stats)

UploadScanPage
├─ file (useState)
├─ uploading (useState)
├─ analyzing (useState)
├─ progress (useState)
└─ scanId (useState)
```

---

## API Request/Response Flow

### Example: Login

**Request (Frontend):**
```javascript
POST http://localhost:5000/api/auth/login
Content-Type: application/json
Authorization: Bearer {token}

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (Backend):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### Example: Upload Scan

**Request (Frontend):**
```
POST http://localhost:5000/api/scans/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

[binary file data]
```

**Response (Backend):**
```json
{
  "scan_id": "scan_abc123",
  "filename": "ct_scan.nii.gz",
  "size_mb": 245.5,
  "upload_time": "2024-01-15T10:35:00Z"
}
```

### Example: Get Results

**Request (Frontend):**
```
GET http://localhost:5000/api/results/scan_abc123
Authorization: Bearer {token}
```

**Response (Backend):**
```json
{
  "scan_id": "scan_abc123",
  "total_detections": 3,
  "avg_confidence": 0.87,
  "processing_time": 124.5,
  "detections": [
    {
      "x": 256,
      "y": 128,
      "z": 45,
      "size": 8.5,
      "confidence": 0.92
    }
  ]
}
```

---

## Error Handling Flow

```
API Call
    │
    ├─ Response OK (200)
    │  └─ Update state
    │     └─ Show success toast
    │
    └─ Response Error
       │
       ├─ 401 Unauthorized
       │  ├─ Clear token
       │  ├─ Clear user
       │  └─ Redirect to /login
       │
       ├─ 400 Bad Request
       │  ├─ Show error alert
       │  └─ Show form validation
       │
       ├─ 500 Server Error
       │  ├─ Show error toast
       │  └─ Log error
       │
       └─ Network Error
          ├─ Show offline alert
          └─ Retry option
```

---

## Browser Storage

### localStorage

```
authToken: "eyJhbGciOiJIUzI1NiIs..."  // JWT token
user: {                                // User object
  "id": "user_123",
  "email": "user@example.com",
  "name": "John Doe"
}
```

### sessionStorage

```
(Optional - for temporary data)
currentScanId: "scan_abc123"
lastUpload: "2024-01-15T10:35:00Z"
```

### Cookies

```
(If CSRF protection is needed)
XSRF-TOKEN: "csrf_token_value"
```

---

## Performance Optimization

### Code Splitting

```
App.js (main bundle)
├─ AuthProvider
├─ Router setup
│
├─ LoginPage (lazy loaded)
├─ DashboardPage (lazy loaded)
├─ UploadScanPage (lazy loaded)
├─ ResultsPage (lazy loaded)
├─ ReportPage (lazy loaded)
└─ HistoryPage (lazy loaded)
```

### Caching Strategy

```
Frontend Cache
├─ API responses (in memory)
├─ User profile (localStorage)
├─ JWT token (localStorage)
│
Backend Cache (if needed)
├─ Analysis results (Redis)
├─ Report cache (Database)
└─ User sessions (Database)
```

---

## Deployment Architecture

### Development

```
Local Browser (localhost:3000)
         │
         ├─ Dev Server (Webpack/Vite)
         │  └─ Hot Module Replacement
         │
         └─ Flask Backend (localhost:5000)
            └─ SQLite Database
```

### Production

```
CDN (Static Files)
└─ React Build (HTML/CSS/JS)
   └─ Minified & Optimized

Load Balancer
│
├─ Web Server (Nginx)
│  └─ Gzip Compression
│
├─ Flask Backend (Gunicorn/uWSGI)
│  ├─ Multiple Workers
│  └─ Process Manager (Supervisor)
│
├─ PostgreSQL Database
│  └─ Backup & Replication
│
└─ File Storage
   ├─ User Uploads
   └─ Generated Reports
```

---

## Security Flow

```
User Login
    │
    ├─ Password hashed (bcrypt)
    │
    ├─ JWT created (HS256)
    │
    ├─ Stored in localStorage (client)
    │
    ├─ Sent in header (Authorization: Bearer)
    │
    ├─ Verified on backend
    │
    └─ Access granted ✓
```

---

## Integration Points

```
Frontend ←──→ Backend
    │              │
    ├─ REST API    │
    │              ├─ Database
    │              ├─ ML Models
    │              └─ File System
    │
    └─ Env: REACT_APP_API_URL
```

---

**Diagram Created:** 2024  
**Architecture Version:** 1.0  
**Status:** Production Ready ✅
