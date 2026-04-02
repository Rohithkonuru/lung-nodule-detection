import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import the Flask app
from app import app

# Vercel serverless handler
def handler(event, context):
    return app
