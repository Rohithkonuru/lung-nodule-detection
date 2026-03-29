#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '..')
from pathlib import Path

# Find the database
db_path = Path('app/db/database.py')
if db_path.exists():
    from app.db.database import SessionLocal
    from app.db.models import CTScan
    
    session = SessionLocal()
    scan = session.query(CTScan).filter(CTScan.id == 4).first()
    if scan:
        print(f'Scan 4 file_path: {scan.file_path}')
        full_path = Path(scan.file_path)
        print(f'Absolute exists: {full_path.exists()}')
        
        # Try relative to project root
        proj_path = Path(scan.file_path)
        if proj_path.exists():
            print(f'Found at: {proj_path.absolute()}')
    else:
        print('Scan 4 not found in DB')
    session.close()
else:
    print('DB module not found')
