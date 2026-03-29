#!/usr/bin/env python3
"""Properly inspect response from /api/v1/results/{scan_id}."""
import sys, urllib.request, json, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.security import create_access_token

token = create_access_token('3')

print('\n' + '=' * 70)
print('API RESULTS INSPECTION - /api/v1/results/4')
print('=' * 70)

# Get detailed results
req = urllib.request.Request(
    'http://127.0.0.1:8001/api/v1/results/4',
    headers={'Authorization': f'Bearer {token}'}
)
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read())

print(f'\nPayload keys: {list(data.keys())}')
print(f'Total detections: {data.get("total_detections", 0)}')
print(f'Avg confidence: {data.get("avg_confidence", 0):.3f}')
print(f'Processing time: {data.get("processing_time") or 0:.1f} sec')

detections = data.get('detections', [])
print(f'\nDetections array length: {len(detections)}')

if detections:
    print('\nDetection Details:')
    print('-' * 70)
    for i, det in enumerate(detections, 1):
        print(f'\n{i}. {det}')
        if isinstance(det, dict):
            for key, val in det.items():
                if isinstance(val, (int, float)):
                    print(f'      {key}: {val:.2f}' if isinstance(val, float) else f'      {key}: {val}')
                else:
                    print(f'      {key}: {val}')

print('\n' + '=' * 70)
print('✅ RESULTS INSPECTION COMPLETE')
print('=' * 70)
print(f'\nSummary:')
print(f'  ✓ Backend: Running')
print(f'  ✓ Results endpoint: OK')
print(f'  ✓ Total detections (from DB): {data.get("total_detections", 0)}')
print(f'  ✓ Average confidence: {data.get("avg_confidence", 0):.3f}')
print(f'\nNext: Generate and download report from /api/v1/report/4/download')
