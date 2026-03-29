import React from 'react';

export const Card = ({ children, className = '', hover = false }) => (
  <div className={`${hover ? 'card-hover' : 'card'} ${className}`}>
    {children}
  </div>
);

export const Button = ({ children, className = '', variant = 'primary', size = 'md', as: Component = 'button', ...props }) => {
  const baseClasses = 'inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0f172a]';
  
  const variantClasses = {
    primary: 'btn-apple focus:ring-gray-300',
    secondary: 'bg-[#111827] text-white border border-gray-700 hover:bg-gray-800 focus:ring-gray-500',
    danger: 'bg-red-500 text-white hover:bg-red-400 focus:ring-red-300',
    success: 'bg-emerald-500 text-white hover:bg-emerald-400 focus:ring-emerald-300',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2.5',
    lg: 'px-6 py-3 text-lg',
  };

  return Component === 'span' || Component === 'div' ? (
    <Component
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      role="button"
      tabIndex={0}
      {...props}
    >
      {children}
    </Component>
  ) : (
    <Component
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </Component>
  );
};

export const Input = ({ label, error, className = '', ...props }) => (
  <div className={`mb-4 ${className}`}>
    {label && <label className="block text-sm font-medium text-gray-200 mb-2">{label}</label>}
    <input
      className={`w-full px-4 py-2 rounded-xl border focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-transparent bg-[#0b1220] text-white placeholder-gray-400 ${error ? 'border-red-400' : 'border-gray-700'}`}
      {...props}
    />
    {error && <p className="text-red-400 text-sm mt-1">{error}</p>}
  </div>
);

export const Alert = ({ type = 'info', title, message, className = '' }) => {
  const bgColors = {
    success: 'bg-emerald-500/12 border-emerald-400/35',
    error: 'bg-red-500/12 border-red-400/35',
    warning: 'bg-amber-500/12 border-amber-400/35',
    info: 'bg-slate-700/50 border-slate-500/40',
  };

  const textColors = {
    success: 'text-emerald-100',
    error: 'text-red-100',
    warning: 'text-amber-100',
    info: 'text-slate-100',
  };

  return (
    <div className={`border-l-4 p-4 rounded-xl ${bgColors[type]} ${className}`}>
      {title && <h4 className={`font-semibold ${textColors[type]} mb-1`}>{title}</h4>}
      <p className={textColors[type]}>{message}</p>
    </div>
  );
};

export const Badge = ({ children, variant = 'primary', size = 'sm' }) => {
  const variants = {
    primary: 'bg-slate-300 text-slate-900',
    success: 'bg-emerald-400 text-slate-900',
    danger: 'bg-red-400 text-slate-900',
    warning: 'bg-amber-400 text-slate-900',
    gray: 'bg-slate-500/70 text-white',
  };

  const sizes = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base',
  };

  return (
    <span className={`inline-block rounded-full font-semibold ${variants[variant]} ${sizes[size]}`}>
      {children}
    </span>
  );
};

export const LoadingSkeleton = ({ className = '' }) => (
  <div className={`skeleton rounded-md ${className}`} />
);

export const Modal = ({ isOpen, title, children, onClose, footer }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="glass rounded-2xl max-w-lg w-full mx-4">
        <div className="flex justify-between items-center p-6 border-b border-gray-700">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose} className="text-slate-300 hover:text-white">
            ✕
          </button>
        </div>
        <div className="p-6">{children}</div>
        {footer && <div className="p-6 border-t border-gray-700">{footer}</div>}
      </div>
    </div>
  );
};

export const ProgressBar = ({ progress, className = '' }) => (
  <div className={`w-full bg-gray-800 rounded-full h-2 ${className}`}>
    <div
      className="h-2 rounded-full transition-all duration-300 bg-gray-200"
      style={{ width: `${progress}%` }}
    />
  </div>
);

export const Spinner = ({ size = 'md', className = '' }) => {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  return (
    <div className={`inline-block animate-spin ${sizes[size]} ${className}`}>
      <svg
        className="w-full h-full text-gray-200"
        fill="none"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    </div>
  );
};
