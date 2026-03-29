import json
import os
import sys
import pytest

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.services.pipeline_service import detections_to_boxes_text


def test_detections_to_boxes_text_roundtrip():
    detections = [
        {"center": [10, 20, 30], "confidence": 0.9, "size_mm": 7.2},
        {"center": [12, 22, 32], "confidence": 0.7, "size_mm": 4.8},
    ]
    payload = detections_to_boxes_text(detections)
    parsed = json.loads(payload)
    assert len(parsed) == 2
    assert parsed[0]["confidence"] == pytest.approx(0.9)


def test_analyze_scan_missing_file_raises():
    from app.services.pipeline_service import analyze_scan

    with pytest.raises(FileNotFoundError):
        analyze_scan("missing_scan_file_that_does_not_exist.nii.gz")
