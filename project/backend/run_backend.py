#!/usr/bin/env python3
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    print("Starting backend with new model (transfer_demo.pth)...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
