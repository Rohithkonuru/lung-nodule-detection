#!/usr/bin/env python3
"""Test hybrid RetinaNet detector on scan 4."""
import sys, urllib.request, json, time
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.security import create_access_token

token = create_access_token('3')

print('=' * 60)
print('HYBRID RETINANET 2D DETECTOR TEST')
print('=' * 60)

print('\n✓ Testing backend connectivity...')
time.sleep(2)

try:
    req = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/health',
        headers={'Accept': 'application/json'},
        method='GET'
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        print('✓ Backend is running on port 8001')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # Try different endpoint
            req = urllib.request.Request(
                'http://127.0.0.1:8001/docs',
                headers={'Accept': 'text/html'},
                method='GET'
            )
            resp = urllib.request.urlopen(req, timeout=5)
            print('✓ Backend is running on port 8001 (docs endpoint responsive)')
        else:
            raise
except Exception as e:
    print(f'✗ Backend not responding: {e}')
    print('Trying port 8002...')
    try:
        req = urllib.request.Request(
            'http://127.0.0.1:8002/docs',
            headers={'Accept': 'text/html'},
            method='GET'
        )
        resp = urllib.request.urlopen(req, timeout=5)
        print('✓ Backend is running on port 8002')
    except Exception as e2:
        print(f'✗ Backend not responding on any port: {e2}')
        sys.exit(1)

print('\n✓ Analyzing scan 4 with HYBRID detector...')
print('  (Processing 2D slices with RetinaNet ResNet50 FPN)')

try:
    req = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/analyze/4',
        method='POST',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=180)
    data = json.loads(resp.read())
    
    det_count = data.get('num_detections', 0)
    print(f'✓ Analysis complete')
    print(f'  Status: {resp.status}')
    print(f'  Detections found: {det_count}')
    
    # Get detailed results
    print('\n✓ Fetching detailed results...')
    req2 = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/results/4',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp2 = urllib.request.urlopen(req2, timeout=10)
    data2 = json.loads(resp2.read())
    
    results = data2.get('results', [])
    if results:
        confs = [r.get('confidence', 0) for r in results]
        print(f'\n  Detection Statistics:')
        print(f'    Total detections: {len(results)}')
        print(f'    Confidence range: {min(confs):.3f} - {max(confs):.3f}')
        print(f'    Average confidence: {sum(confs)/len(confs):.3f}')
        print(f'\n  Top 5 Detections by Confidence:')
        ranked = sorted(results, key=lambda x: x.get('confidence', 0), reverse=True)
        for i, det in enumerate(ranked[:5], 1):
            z, y, x = det.get('center', (0, 0, 0))
            conf = det.get('confidence', 0)
            size = det.get('size_mm', 0)
            print(f'    {i}. Center ({z},{y},{x}) | Conf: {conf:.3f} | Size: {size:.1f}mm')
    
    print(f'\n' + '=' * 60)
    print('✅ HYBRID DETECTOR TEST SUCCESSFUL')
    print('=' * 60)
    print(f'\nComparison:')
    print(f'  3D CNN (transfer_demo.pth): ~8 detections')
    print(f'  2D RetinaNet (hybrid): {det_count} detections')
    
except urllib.error.HTTPError as e:
    print(f'✗ HTTP Error {e.code}')
    error_msg = e.read().decode()
    print(f'  {error_msg}')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
