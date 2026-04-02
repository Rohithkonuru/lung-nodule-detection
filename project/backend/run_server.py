#!/usr/bin/env python3
"""
Clean backend startup with proper port handling.
Uses port 8001, with fallback to 8002 if port is busy.
"""
import sys
import os
from pathlib import Path
import socket

# Add backend dir to path
script_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(script_dir))

print("=" * 70)
print("LUNG NODULE DETECTION BACKEND - HYBRID RETINANET 2D MODE")
print("=" * 70)

# Check config
try:
    from app.core.config import settings
    print(f"\n✓ Configuration loaded:")
    print(f"  Detector Type: {settings.DETECTOR_TYPE}")
    print(f"  RetinaNet: {settings.RETINANET_MODEL_PATH}")
except Exception as e:
    print(f"\n✗ Config error: {e}")
    sys.exit(1)

# Find available port
def find_available_port(preferred: int = 8000) -> int:
    """Find available port, starting with preferred."""
    for port in [preferred, preferred + 1, preferred + 10, preferred + 100]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    raise RuntimeError("No available ports found")

env_port = os.environ.get("PORT")
preferred_port = int(env_port) if env_port else 8001
port = find_available_port(preferred_port)
print(f"\n✓ Using port: {port}")

# Start uvicorn
print(f"\n{'='*70}")
print("Starting FastAPI server...")
print(f"{'='*70}\n")

import uvicorn

try:
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
except Exception as e:
    print(f"\n✗ Failed to start server: {e}")
    sys.exit(1)
