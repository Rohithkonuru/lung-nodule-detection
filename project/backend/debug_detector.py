#!/usr/bin/env python3
"""Debug: Check what the 3D detector actually returns."""
import sys, os
import torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
import numpy as np
from app.core.config import settings

print('=' * 70)
print('DIRECT 3D DETECTOR TEST')
print('=' * 70)

# Load the 3D model directly
model_path = settings.MODEL_WEIGHTS_PATH
print(f'\nLoading model: {model_path}')
print(f'Model exists: {Path(model_path).exists()}')

try:
    model_weights = torch.load(model_path, map_location='cpu')
    print(f'✓ Model loaded successfully')
    print(f'  Keys: {list(model_weights.keys())[:5]}...')
    print(f'  Model type: {type(model_weights)}')
except Exception as e:
    print(f'✗ Error loading model: {e}')
    sys.exit(1)

# Load sample CT scan
scan_path = Path('data/raw/luna16/sample_scan.mhd')
if not scan_path.exists():
    print(f'✗ Sample scan not found at {scan_path}')
    sys.exit(1)

print(f'\nLoading scan: {scan_path}')

try:
    import SimpleITK as sitk
    scan = sitk.ReadImage(str(scan_path))
    image = sitk.GetArrayFromImage(scan)
    
    print(f'✓ Scan loaded')
    print(f'  Shape: {image.shape}')
    print(f'  Spacing: {scan.GetSpacing()}')
    print(f'  Range: {image.min():.1f} to {image.max():.1f}')
    
except Exception as e:
    print(f'✗ Error loading scan: {e}')
    sys.exit(1)

# Try the main detector (3D)
print(f'\nTesting main detection pipeline...')

try:
    from app.services.ml_service import detect_nodules
    
    results = detect_nodules(image)
    print(f'✓ Detection complete')
    print(f'  Detections: {len(results)}')
    
    if results:
        print(f'\n  Sample detections:')
        for i, det in enumerate(results[:3], 1):
            print(f'    {i}. {det}')
    else:
        print(f'  (No detections returned)')
        
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()

print('\n' + '=' * 70)
