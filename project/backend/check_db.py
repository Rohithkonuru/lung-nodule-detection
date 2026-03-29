#!/usr/bin/env python3
"""Check what's actually in the database."""
import sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.db.models import CTScan, DetectionResult, ClinicalReport

print("\n" + "=" * 70)
print("DATABASE CONTENTS")
print("=" * 70)

db = SessionLocal()

# Check scans
scans = db.query(CTScan).all()
print(f"\nScans in database: {len(scans)}")
for s in scans:
    print(f"  - Scan {s.id}: {s.file_name}")

# Check recent detections
detections = db.query(DetectionResult).all()
print(f"\nTotal detections in database: {len(detections)}")

for scan in scans[-3:]:  # Last 3 scans
    dets = db.query(DetectionResult).filter(DetectionResult.scan_id == scan.id).all()
    print(f"\n  Scan {scan.id}: {len(dets)} detections")
    for d in dets[:3]:  # Show first 3
        print(f"    - Det {d.id}: conf={d.confidence_score:.3f}")

# Check reports
reports = db.query(ClinicalReport).all()
print(f"\nReports in database: {len(reports)}")
for r in reports[-2:]:
    print(f"  - Report {r.id} for scan {r.scan_id}")

db.close()
print("\n" + "=" * 70)
