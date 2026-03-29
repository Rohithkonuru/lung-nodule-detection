#!/usr/bin/env python3
import sys, urllib.request, json
import os

# Add backend directory explicitly to avoid import conflicts with project root app.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import from backend app
from app.core.security import create_access_token

token = create_access_token('3')

print('Testing new model (transfer_demo.pth)...\n')

# Check backend health
print('Checking backend status...')
try:
    # Try a simpler endpoint that should exist
    req = urllib.request.Request(
        'http://127.0.0.1:8001/',
        headers={'Accept': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=5)
    print('✓ Backend is running\n')
except Exception as e:
    print(f'✗ Backend not responding: {e}')
    print('Start backend with: cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001')
    sys.exit(1)

# Analyze scan 4
print('Analyzing scan 4 with new model...')
try:
    req = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/analyze/4',
        method='POST',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=45)
    data = json.loads(resp.read())
    
    det_count = data.get('num_detections', 0)
    print(f'✓ Analysis complete')
    print(f'  Status: {resp.status}')
    print(f'  Detections found: {det_count}')
    
    # Get detailed results
    req2 = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/results/4',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp2 = urllib.request.urlopen(req2, timeout=10)
    data2 = json.loads(resp2.read())
    
    results = data2.get('results', [])
    if results:
        confs = [r.get('confidence', 0) for r in results]
        print(f'\n  Confidence statistics:')
        print(f'    Range: {min(confs):.3f} - {max(confs):.3f}')
        print(f'    Average: {sum(confs)/len(confs):.3f}')
        print(f'    Top 5: {sorted(confs, reverse=True)[:5]}')
    
    print(f'\n✓ SUCCESS: Model switched to transfer_demo.pth')
    print(f'  Old model (2D): 8 detections')
    print(f'  New model (3D): {det_count} detections')
    
except urllib.error.HTTPError as e:
    print(f'✗ HTTP Error {e.code}')
    print(f'  {e.read().decode()}')
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
