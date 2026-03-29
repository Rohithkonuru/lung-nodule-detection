import React from 'react';

export default function Loader({ label = 'Analyzing CT Scan...' }) {
  const dotDelays = ['0ms', '120ms', '240ms'];

  return (
    <div className="flex flex-col items-center justify-center gap-4 text-center">
      <div className="flex items-center gap-2">
        {dotDelays.map((delay) => (
          <div
            key={delay}
            className="h-3 w-3 rounded-full bg-white animate-pulse"
            style={{ animationDelay: delay }}
          />
        ))}
      </div>
      <p className="text-sm text-gray-300">{label}</p>
    </div>
  );
}
