#!/usr/bin/env python3
"""
Standalone backend launcher script.
Sets up proper paths and launches uvicorn.
"""
import sys
import os
from pathlib import Path

# Get the directory of this script (backend/)
script_dir = Path(__file__).parent.absolute()

# Add backend directory to Python path FIRST
sys.path.insert(0, str(script_dir))

# Now we can import from app module
print(f"Backend directory: {script_dir}")
print(f"Python path: {sys.path[:2]}")

# Test import
try:
    from app.core.config import settings
    print(f"✓ Config loaded. Model: {settings.MODEL_WEIGHTS_PATH}")
except Exception as e:
    print(f"✗ Failed to load config: {e}")
    sys.exit(1)

# Now start uvicorn
import uvicorn

if __name__ == "__main__":
    print("\nStarting backend with new model (transfer_demo.pth)...")
    print(f"Listening on 0.0.0.0:8001")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False  # Disable reload to avoid the import issue with app.py
    )
