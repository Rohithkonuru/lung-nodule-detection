#!/usr/bin/env python3
"""
Quick diagnostic test script for RetinaNet detection.

Usage:
    python quick_test.py

Tests if the model is outputting detections at all.
"""

import requests
import json
from pathlib import Path
import time

# Configuration
BACKEND_URL = "http://127.0.0.1:8001/api/v1"
UPLOAD_DIR = Path("../uploads/test_scans")

def test_health():
    """Check if backend is alive."""
    try:
        response = requests.get(f"{BACKEND_URL.replace('/api/v1', '')}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend Health: OK")
            return True
        else:
            print(f"❌ Backend Health: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend Health: {e}")
        return False

def test_upload_and_detect(scan_path: str):
    """Upload a scan and test detection."""
    try:
        # Check file exists
        if not Path(scan_path).exists():
            print(f"❌ Scan file not found: {scan_path}")
            return None
        
        print(f"\n📤 Uploading: {scan_path}")
        
        # Upload file
        with open(scan_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{BACKEND_URL}/scans/upload",
                files=files,
                timeout=120
            )
        
        if response.status_code != 200:
            print(f"❌ Upload failed: {response.status_code}")
            print(response.text)
            return None
        
        result = response.json()
        scan_id = result.get('scan_id')
        print(f"✅ Upload successful: {scan_id}")
        
        return scan_id
    
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return None

def test_analysis(scan_id: str):
    """Run detection analysis on uploaded scan."""
    try:
        print(f"\n🔍 Analyzing ({scan_id})...")
        
        response = requests.post(
            f"{BACKEND_URL}/scans/{scan_id}/analyze",
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ Analysis failed: {response.status_code}")
            print(response.text)
            return None
        
        result = response.json()
        detections = result.get('detections', [])
        confidence = result.get('confidence_score', 0)
        
        print(f"\n📊 DETECTION RESULTS:")
        print(f"   Detections: {len(detections)}")
        print(f"   Avg Confidence: {confidence:.2f}")
        
        if detections:
            print(f"\n   Top detections:")
            for i, det in enumerate(detections[:3], 1):
                print(f"   {i}. Confidence: {det.get('confidence', 0):.3f}, "
                      f"Size: {det.get('size_mm', 0):.1f}mm")
        else:
            print(f"   ⚠️  No detections found!")
        
        return result
    
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        return None

def main():
    print("=" * 70)
    print("🧪 QUICK RETINANET DIAGNOSTIC TEST")
    print("=" * 70)
    
    # Step 1: Health check
    print("\n[1/3] Checking backend health...")
    if not test_health():
        print("\n❌ Backend is not running. Start it with:")
        print("   cd backend && python run_server.py")
        return
    
    # Step 2: List available scans
    print("\n[2/3] Looking for test scans...")
    test_scans = list(UPLOAD_DIR.glob("*.mhd")) + list(UPLOAD_DIR.glob("*.nii.gz"))
    
    if not test_scans:
        print(f"⚠️  No test scans found in {UPLOAD_DIR}")
        print("\n📝 To test:")
        print("   1. Upload a CT scan via the UI at http://localhost:3000")
        print("   2. Check backend logs for detection output")
        print("   3. Look for messages like: '[Slice X] Raw model output: Y detections'")
        return
    
    print(f"✅ Found {len(test_scans)} test scans")
    
    # Step 3: Test first scan
    print("\n[3/3] Running detection test...")
    scan_path = test_scans[0]
    scan_id = test_upload_and_detect(str(scan_path))
    
    if scan_id:
        result = test_analysis(scan_id)
        
        if result:
            print("\n" + "=" * 70)
            print("✅ DIAGNOSTIC SUMMARY")
            print("=" * 70)
            
            num_dets = len(result.get('detections', []))
            
            if num_dets > 0:
                print(f"✅ Model IS detecting objects ({num_dets} found)")
                print(f"   → This is GOOD! Model is working.")
                print(f"   → Next: Train on LUNA16 to improve accuracy")
                print(f"\n   📚 See: training/README.md")
            else:
                print(f"⚠️  Model found ZERO detections")
                print(f"   → Try one of these:")
                print(f"      1. Lower CONFIDENCE_THRESHOLD more (0.1)")
                print(f"      2. Enable DISABLE_FILTERS_FOR_TESTING = True")
                print(f"      3. Check backend logs for errors")
                print(f"\n   See: DIAGNOSIS_AND_FIX.md")

if __name__ == "__main__":
    main()
