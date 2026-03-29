#!/usr/bin/env python3
"""Test the new risk assessment integrated API."""
import sys, urllib.request, json, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.security import create_access_token

token = create_access_token('3')

print('\n' + '=' * 70)
print('SMART RESULTS WITH RISK ASSESSMENT')
print('=' * 70 + '\n')

try:
    req = urllib.request.Request(
        'http://127.0.0.1:8001/api/v1/results/4',
        headers={'Authorization': f'Bearer {token}'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    
    print(f"Total Detections: {data.get('total_detections', 0)}")
    print(f"Average Confidence: {data.get('avg_confidence', 0):.1%}")
    
    if 'risk_level' in data:
        print(f"\n✓ Risk Assessment Available (NEW!)")
        print(f"  Risk Level: {data.get('risk_level', 'Unknown')}")
        print(f"  Requires Follow-up: {data.get('requires_followup', False)}")
        print(f"  Max Size: {data.get('max_size_mm', 0):.1f}mm")
        print(f"  Avg Size: {data.get('avg_size_mm', 0):.1f}mm")
        
        if data.get('recommendations'):
            print(f"\n  Recommendations ({len(data['recommendations'])} items):")
            for i, rec in enumerate(data['recommendations'][:3], 1):
                print(f"    {i}. {rec}")
        
        if data.get('nodules_analysis'):
            print(f"\n  Detailed Nodule Analysis:")
            for nodule in data['nodules_analysis'][:2]:
                print(f"    #{nodule['nodule_id']}: {nodule['size_mm']}mm, Risk={nodule['risk_category']}")
    else:
        print(f"  (Risk assessment not yet integrated)")
    
    print('\n' + '=' * 70)
    print('✅ SMART RESULTS TEST COMPLETE')
    print('=' * 70)
    
except Exception as e:
    print(f'✗ Error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
