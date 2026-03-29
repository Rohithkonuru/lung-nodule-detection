#!/usr/bin/env python3
"""Test if hybrid detector imports correctly."""
import sys
sys.path.insert(0, 'd:\\project\\project')

print('Testing imports...')

try:
    print('1. Importing RetinaNet2DDetector...')
    from src.ml.detection.retinanet_2d import RetinaNet2DDetector
    print('   ✓ RetinaNet2DDetector imported')
except Exception as e:
    print(f'   ✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print('2. Importing DetectionAggregator...')
    from src.ml.detection.aggregator_3d import DetectionAggregator
    print('   ✓ DetectionAggregator imported')
except Exception as e:
    print(f'   ✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print('3. Importing Hybrid3D2DDetector...')
    from src.ml.detection.hybrid_detector import Hybrid3D2DDetector
    print('   ✓ Hybrid3D2DDetector imported')
except Exception as e:
    print(f'   ✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

print('\n✓ All imports successful!')
print('\nTesting detector initialization...')

try:
    print('Initializing RetinaNet detector...')
    detector = RetinaNet2DDetector(device='cpu')
    print('✓ RetinaNet2DDetector initialized')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
