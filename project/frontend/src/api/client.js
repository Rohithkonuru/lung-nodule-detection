import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:8001/api/v1' : '/api/v1');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

const normalizeError = (value) => {
  if (!value) return 'Unknown error occurred';
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value);
  } catch (err) {
    return 'Unknown error occurred';
  }
};

const isAuthEndpoint = (url) => {
  const u = String(url || '');
  return u.includes('/auth/login') || u.includes('/auth/register');
};

// Add token to requests
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail;
    const message = error?.response?.data?.message;
    const errorMsg = normalizeError(message || detail || error?.message || 'Unknown error occurred');

    if (detail && !message && error?.response?.data) {
      error.response.data.message = normalizeError(detail);
    }

    // Store formatted error for easy access (string only)
    error.formattedMessage = errorMsg;

    // Token can expire or become invalid after backend restarts.
    if (error?.response?.status === 401 && !isAuthEndpoint(error?.config?.url)) {
      localStorage.removeItem('authToken');
      localStorage.removeItem('user');

      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('auth:unauthorized', {
            detail: { message: errorMsg },
          })
        );
      }
    }

    return Promise.reject(error);
  }
);

export const authAPI = {
  login: (email, password) =>
    apiClient.post('/auth/login', { email, password }),
  register: (email, password, name) =>
    apiClient.post('/auth/register', { email, password, name }),
  logout: () => apiClient.post('/auth/logout'),
};

export const scanAPI = {
  uploadScan: (formData) =>
    apiClient.post('/scans/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  getScan: (scanId) => apiClient.get(`/scans/${scanId}`),
  getScanPreview: (scanId, withBoxes = true) =>
    apiClient.get(`/scans/${scanId}/preview`, {
      params: { with_boxes: withBoxes },
      responseType: 'blob',
    }),
  listScans: () => apiClient.get('/scans'),
  deleteScan: (scanId) => apiClient.delete(`/scans/${scanId}`),
  analyzeScan: (scanId) => apiClient.post(`/analyze/${scanId}`),
};

export const analysisAPI = {
  analyze: (scanId) => apiClient.post(`/analyze/${scanId}`),
  getResults: (scanId) => apiClient.get(`/results/${scanId}`),
};

export const reportAPI = {
  generateReport: (scanId) =>
    apiClient.post(`/generate_report/${scanId}`),
  getReport: (scanId) => apiClient.get(`/report/${scanId}`),
  downloadReport: (scanId) =>
    apiClient.get(`/report/${scanId}/download`, { responseType: 'blob' }),
};

export const userAPI = {
  getProfile: () => apiClient.get('/user/profile'),
  updateProfile: (data) => apiClient.put('/user/profile', data),
  getDashboardStats: () => apiClient.get('/user/stats'),
};

export default apiClient;
