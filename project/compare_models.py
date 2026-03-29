#!/usr/bin/env python3
import sys, os, torch
sys.path.insert(0, 'src')
os.environ['PYTHONPATH'] = 'src'

from src.ml.detection import NoduleDetector
from src.ml.preprocessing import preprocess_scan
from pathlib import Path
import SimpleITK as sitk

# Test scan path
scan_path = Path('data/processed/images/scan_4.nii.gz')
if not scan_path.exists():
    print(f'Scan not found: {scan_path}')
    sys.exit(1)

print('Testing both models on scan_4...\n')

# Load and preprocess scan once
print('Loading CT scan...')
try:
    # Use preprocess_scan from preprocessing module
    volume = preprocess_scan(str(scan_path), apply_segmentation=False)
    # Get spacing from original image
    img = sitk.ReadImage(str(scan_path))
    spacing = tuple(img.GetSpacing())
    print(f'  Shape: {volume.shape}, Spacing: {spacing}')
except Exception as e:
    print(f'  Error preprocessing: {e}')
    sys.exit(1)

# Test Model 1: Legacy 2D (retinanet_best.pth)
print('\n=== Model 1: Legacy 2D (retinanet_best.pth) ===')
try:
    detector_2d = NoduleDetector(model_path='models/retinanet_best.pth')
    print(f'Model type: {detector_2d.model_kind}')
    detections_2d = detector_2d.detect(volume, stride=32, confidence_threshold=0.5, voxel_spacing_zyx=spacing)
    print(f'Detections found: {len(detections_2d)}')
    if detections_2d:
        confs = [d['confidence'] for d in detections_2d]
        print(f'Confidence range: {min(confs):.3f} - {max(confs):.3f}')
        print(f'Top 3 confidences: {sorted(confs, reverse=True)[:3]}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

# Test Model 2: Modern 3D (transfer_demo.pth)
print('\n=== Model 2: Modern 3D (transfer_demo.pth) ===')
try:
    detector_3d = NoduleDetector(model_path='models/transfer_demo.pth')
    print(f'Model type: {detector_3d.model_kind}')
    detections_3d = detector_3d.detect(volume, stride=32, confidence_threshold=0.5, voxel_spacing_zyx=spacing)
    print(f'Detections found: {len(detections_3d)}')
    if detections_3d:
        confs = [d['confidence'] for d in detections_3d]
        print(f'Confidence range: {min(confs):.3f} - {max(confs):.3f}')
        print(f'Top 3 confidences: {sorted(confs, reverse=True)[:3]}')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

print('\n=== Summary ===')
try:
    print(f'Legacy 2D: {len(detections_2d)} detections')
    print(f'Modern 3D: {len(detections_3d)} detections')
    diff = len(detections_2d) - len(detections_3d)
    print(f'Difference: {diff:+d} (2D has {abs(diff)} more)' if diff else 'Same count')
except:
    pass
