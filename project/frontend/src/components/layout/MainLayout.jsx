import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  Home,
  Upload,
  BarChart3,
  FileText,
  History,
  LogOut,
} from 'lucide-react';

export const Sidebar = ({ onNavigate = () => {}, className = '' }) => {
  const location = useLocation();
  const { logout } = useAuth();

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: Home },
    { path: '/upload', label: 'Upload Scan', icon: Upload },
    { path: '/results', label: 'Results', icon: BarChart3 },
    { path: '/reports', label: 'Reports', icon: FileText },
    { path: '/history', label: 'History', icon: History },
  ];

  const isActive = (path) => {
    if (path === '/dashboard') {
      return location.pathname === path;
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className={`h-full p-6 bg-[#0b1220] text-white border-r border-gray-800 ${className}`}>
      <div className="mb-8">
        <h1 className="text-xl font-semibold flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-white text-black">
            🫁
          </div>
          <span>LungAI</span>
        </h1>
        <p className="text-gray-400 text-sm mt-1">Clinical Diagnosis</p>
      </div>

      <nav className="space-y-2 mb-8">
        {navItems.map(({ path, label, icon: Icon }) => (
          <Link
            key={path}
            to={path}
            onClick={onNavigate}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
              isActive(path)
                ? 'bg-white/10 text-white border border-gray-700'
                : 'text-gray-400 hover:text-white hover:bg-gray-900/70'
            }`}
          >
            <Icon size={20} />
            <span>{label}</span>
          </Link>
        ))}
      </nav>

      <button
        onClick={handleLogout}
        className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-gray-400 hover:text-white hover:bg-gray-900/70 transition-all duration-200"
      >
        <LogOut size={20} />
        <span>Logout</span>
      </button>
    </div>
  );
};

export const MainLayout = ({ children }) => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const mobileNavItems = [
    { path: '/dashboard', icon: '🏠', label: 'Home' },
    { path: '/upload', icon: '📤', label: 'Upload' },
    { path: '/results', icon: '📊', label: 'Results' },
    { path: '/reports', icon: '📄', label: 'Reports' },
  ];

  const isMobileActive = (path) => {
    if (path === '/dashboard') {
      return location.pathname === path;
    }
    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <div className="flex min-h-screen">
      <div className="hidden md:block w-64 shrink-0">
        <Sidebar className="min-h-screen sticky top-0" />
      </div>

      <div className="md:hidden fixed top-0 left-0 right-0 bg-[#0b1220] p-4 z-50 flex justify-between items-center border-b border-gray-800">
        <h1 className="text-lg font-semibold">LungAI</h1>
        <button
          onClick={() => setOpen(true)}
          className="text-white text-2xl leading-none px-2"
          aria-label="Open sidebar"
        >
          ☰
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 bg-black/50 z-[60] md:hidden" onClick={() => setOpen(false)}>
          <div className="w-64 h-full" onClick={(e) => e.stopPropagation()}>
            <Sidebar onNavigate={() => setOpen(false)} className="h-full" />
          </div>
        </div>
      )}

      <main className="flex-1 p-4 md:p-6 lg:p-8 mt-16 md:mt-0 pb-24 md:pb-8">
        {children}
      </main>

      <div className="fixed bottom-0 left-0 right-0 bg-[#0b1220] border-t border-gray-800 flex justify-around p-3 md:hidden z-50">
        {mobileNavItems.map((item) => (
          <button
            key={item.path}
            onClick={() => navigate(item.path)}
            className={`flex flex-col items-center gap-1 px-2 py-1 rounded-lg transition duration-200 ${
              isMobileActive(item.path)
                ? 'text-white bg-white/10'
                : 'text-gray-400 hover:text-white hover:bg-white/5'
            }`}
            aria-label={item.label}
          >
            <span className="text-lg leading-none">{item.icon}</span>
            <span className="text-[10px] tracking-wide">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
