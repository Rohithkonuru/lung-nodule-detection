import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AnimatePresence, motion } from 'framer-motion';
import { AuthProvider, useAuth } from './context/AuthContext';
import Loader from './components/Loader';

// Pages
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { UploadScanPage } from './pages/UploadScanPage';
import { ResultsPage } from './pages/ResultsPage';
import { ReportPage } from './pages/ReportPage';
import { HistoryPage } from './pages/HistoryPage';

// Protected Route Component
const ProtectedRoute = ({ component: Component, componentProps = {} }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader label="Validating session..." />
      </div>
    );
  }

  return user ? <Component {...componentProps} /> : <Navigate to="/login" />;
};

// Public Route Component
const PublicRoute = ({ component: Component }) => {
  const { user } = useAuth();
  return !user ? <Component /> : <Navigate to="/dashboard" />;
};

const AnimatedRoutes = () => {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
      >
        <Routes location={location}>
          {/* Authentication Routes */}
          <Route
            path="/login"
            element={<PublicRoute component={LoginPage} />}
          />
          <Route
            path="/register"
            element={<PublicRoute component={RegisterPage} />}
          />

          {/* Protected Routes */}
          <Route
            path="/dashboard"
            element={<ProtectedRoute component={DashboardPage} />}
          />
          <Route
            path="/upload"
            element={<ProtectedRoute component={UploadScanPage} />}
          />
          <Route
            path="/results"
            element={<ProtectedRoute component={HistoryPage} componentProps={{ view: 'results' }} />}
          />
          <Route
            path="/results/:scanId"
            element={<ProtectedRoute component={ResultsPage} />}
          />
          <Route
            path="/reports"
            element={<ProtectedRoute component={HistoryPage} componentProps={{ view: 'reports' }} />}
          />
          <Route
            path="/reports/:scanId"
            element={<ProtectedRoute component={ReportPage} />}
          />
          <Route
            path="/history"
            element={<ProtectedRoute component={HistoryPage} componentProps={{ view: 'history' }} />}
          />

          {/* Default Route */}
          <Route path="/" element={<Navigate to="/dashboard" />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
};

function App() {
  return (
    <Router
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <AuthProvider>
        <div className="min-h-screen text-slate-100">
          <AnimatedRoutes />

          {/* Toast Notifications */}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#111827',
                color: '#f8fafc',
                border: '1px solid #374151',
                boxShadow: '0 8px 24px rgba(2, 6, 23, 0.25)',
              },
            }}
          />
        </div>
      </AuthProvider>
    </Router>
  );
}

export default App;
