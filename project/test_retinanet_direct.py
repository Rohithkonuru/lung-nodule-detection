#!/usr/bin/env python3
"""Direct test of RetinaNet detector without backend."""
import sys
sys.path.insert(0, 'd:\\project\\project')

import numpy as np
print("Testing RetinaNet detector directly...")

# Test 1: Import
print("\n1. Testing imports...")
try:
    from src.ml.detection.retinanet_2d import RetinaNet2DDetector
    print("   ✓ RetinaNet2DDetector imported")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

# Test 2: Initialize
print("\n2. Initializing detector...")
try:
    detector = RetinaNet2DDetector(device='cpu')
    print("   ✓ Detector initialized")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Test on synthetic data
print("\n3. Testing on synthetic CT slice...")
try:
    # Create synthetic CT slice data
    synthetic_slice = np.random.randn(256, 256).astype(np.float32) * 100 - 100
    print(f"   Synthetic slice shape: {synthetic_slice.shape}")
    print(f"   Synthetic slice range: [{synthetic_slice.min():.1f}, {synthetic_slice.max():.1f}]")
    
    # Detect
    print("   Running detection...")
    detections = detector.detect(synthetic_slice, confidence_threshold=0.5, slice_index=0)
    print(f"   ✓ Detection complete")
    print(f"   Found {len(detections)} objects (expected: 0-10 for random data)")
    
    if detections:
        for i, det in enumerate(detections[:3]):
            print(f"     Det {i}: confidence={det['confidence']:.3f}, bbox={det['bbox']}")
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All tests passed!")
