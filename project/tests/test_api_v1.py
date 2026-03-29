import io
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault("SECRET_KEY", "test-secret-key-which-is-long-enough")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(__file__).with_name('test_backend.db')}")
os.environ.setdefault("UPLOAD_DIR", str(Path(__file__).with_name("test_uploads")))
os.environ.setdefault("MODEL_WEIGHTS_PATH", str(Path(__file__).with_name("fake_weights.pth")))

from app.main import app  # type: ignore[reportMissingImports]
from app.api.v1 import routes as v1_routes  # type: ignore[reportMissingImports]
from app.services.pipeline_service import AnalysisResult  # type: ignore[reportMissingImports]
from app.db.base import Base  # type: ignore[reportMissingImports]
from app.db.session import engine  # type: ignore[reportMissingImports]


client = TestClient(app)
Base.metadata.create_all(bind=engine)


def _auth_headers(email: str = "pilot@example.com", password: str = "pilotPass123"):
    register_resp = client.post(
        "/api/v1/auth/register",
        json={"name": "Pilot User", "email": email, "password": password},
    )
    if register_resp.status_code not in (200, 201, 409):
        raise AssertionError(register_resp.text)

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_history_analyze_and_report_flow(monkeypatch):
    headers = _auth_headers()

    monkeypatch.setattr(
        v1_routes,
        "analyze_scan",
        lambda _path: AnalysisResult(
            num_detections=1,
            confidence_score=0.83,
            avg_size_mm=6.5,
            detections=[{"center": [10, 20, 30], "confidence": 0.83, "size_mm": 6.5}],
            runtime=1.23,
        ),
    )
    monkeypatch.setattr(
        v1_routes,
        "generate_report_text",
        lambda detections: ("CLINICAL REPORT\n- Follow-up CT in 6 months", {"count": len(detections)}),
    )

    upload_resp = client.post(
        "/api/v1/upload",
        headers=headers,
        files={"file": ("scan.png", io.BytesIO(b"fake-image-bytes"), "image/png")},
    )
    assert upload_resp.status_code == 201, upload_resp.text
    scan_id = upload_resp.json()["id"]

    analyze_resp = client.post(f"/api/v1/analyze/{scan_id}", headers=headers)
    assert analyze_resp.status_code == 200, analyze_resp.text
    assert analyze_resp.json()["num_detections"] == 1

    report_resp = client.post(f"/api/v1/report/{scan_id}", headers=headers)
    assert report_resp.status_code in (200, 201), report_resp.text

    history_resp = client.get("/api/v1/history", headers=headers)
    assert history_resp.status_code == 200
    rows = history_resp.json()
    assert len(rows) >= 1
    assert "status" in rows[0]
    assert "nodule_count" in rows[0]
