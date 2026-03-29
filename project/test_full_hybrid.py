#!/usr/bin/env python3
"""Direct test of full hybrid pipeline on test scan."""

import sys
sys.path.insert(0, 'd:\\project\\project')

import numpy as np
import SimpleITK as sitk
from pathlib import Path

print("Testing full hybrid pipeline...")

# Check if test scan exists
scan_path = Path('d:\\project\\project\\backend\\uploads\\scans\\scan_4.nii.gz')
if not scan_path.exists():
    print(f"Scan not found at {scan_path}")
    # Try to find any scan file
    import glob
    scans = glob.glob('d:\\project\\project\\backend\\uploads\\scans\\*.nii*', recursive=True)
    if scans:
        scan_path = scans[0]
        print(f"Using: {scan_path}")
    else:
        scans = glob.glob('d:\\project\\project\\data/**/*.nii*', recursive=True)
        if scans:
            scan_path = scans[0]
            print(f"Using: {scan_path}")
        else:
            print("No scans found!")
            sys.exit(1)

print(f"\n1. Loading scan: {scan_path}")
try:
    image = sitk.ReadImage(str(scan_path))
    array = sitk.GetArrayFromImage(image)
    print(f"   ✓ Loaded shape: {array.shape}")
    print(f"   ✓ Value range: [{array.min():.1f}, {array.max():.1f}]")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print(f"\n2. Testing preprocessing...")
try:
    from src.ml.preprocessing import get_preprocessor
    preprocessor = get_preprocessor()
    processed = preprocessor.preprocess(image, apply_segmentation=False)
    proc_array = sitk.GetArrayFromImage(processed)
    print(f"   ✓ Processed shape: {proc_array.shape}")
    print(f"   ✓ Processed range: [{proc_array.min():.1f}, {proc_array.max():.1f}]")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n3. Testing hybrid detector initialization...")
try:
    from src.ml.detection.hybrid_detector import Hybrid3D2DDetector
    detector = Hybrid3D2DDetector(device='cpu')
    print(f"   ✓ Detector initialized")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n4. Running detection (sampling every 5 slices for speed)...")
try:
    detections = detector.detect(
        proc_array,
        voxel_spacing_zyx=(1.0, 1.0, 1.0),
        confidence_threshold=0.3,
        sample_every_n_slices=5  # Every 5th slice to speed up testing
    )
    print(f"   ✓ Detection complete")
    print(f"   ✓ Found {len(detections)} nodules")
    
    if detections:
        for i, det in enumerate(detections[:3]):
            print(f"     Det {i}: center={det['center']}, conf={det['confidence']:.3f}, size={det['size_mm']:.1f}mm")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n✓ Full pipeline test passed!")
