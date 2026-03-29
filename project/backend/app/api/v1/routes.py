import os
import time
import json
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, status, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_user, require_role
from app.api.v1.schemas import AnalyzeResponse, AuthResponse, ReportResponse, ScanOut, UserCreate, UserLogin, UserOut
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db import models
from app.db.session import get_db
from app.services.audit_service import log_audit_event
from app.services.pipeline_service import analyze_scan, detections_to_boxes_text, generate_report_text
from report_generator import generate_pdf_bytes

# Import risk assessment for smart analysis
try:
    from src.risk_assessment import RiskAssessment
    RISK_ASSESSMENT_AVAILABLE = True
except ImportError:
    RISK_ASSESSMENT_AVAILABLE = False

router = APIRouter()


def _allowed_extensions() -> set[str]:
    return {ext.strip().lower() for ext in settings.ALLOWED_UPLOAD_EXTENSIONS.split(",") if ext.strip()}


def _safe_filename(name: str) -> str:
    return Path(name).name.replace("..", "_")


def _resolve_scan_path(file_path: str) -> Path:
    raw = Path(file_path)
    if raw.exists():
        return raw

    if not raw.is_absolute():
        cwd_candidate = Path.cwd() / raw
        if cwd_candidate.exists():
            return cwd_candidate

        backend_root = Path(__file__).resolve().parents[3]
        backend_candidate = backend_root / raw
        if backend_candidate.exists():
            return backend_candidate

        upload_candidate = backend_root / settings.UPLOAD_DIR / raw.name
        if upload_candidate.exists():
            return upload_candidate

    raise FileNotFoundError(f"Scan file not found: {file_path}")


def _load_preview_image(scan_path: Path) -> Image.Image:
    ext = scan_path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
        with Image.open(scan_path) as im:
            return im.convert("RGB")

    try:
        import SimpleITK as sitk
    except Exception as exc:
        raise RuntimeError("Preview for volumetric scans requires SimpleITK.") from exc

    image = sitk.ReadImage(str(scan_path))
    arr = sitk.GetArrayFromImage(image)

    if arr.ndim == 2:
        slice_arr = arr
    elif arr.ndim >= 3:
        slice_arr = arr[arr.shape[0] // 2]
    else:
        raise RuntimeError("Unsupported scan dimensionality for preview rendering.")

    slice_arr = slice_arr.astype(np.float32)
    min_v = float(np.min(slice_arr))
    max_v = float(np.max(slice_arr))
    denom = max(max_v - min_v, 1e-6)
    norm = ((slice_arr - min_v) / denom * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(norm, mode="L").convert("RGB")


def _extract_boxes_2d(detections: list[dict], width: int, height: int) -> list[dict]:
    boxes = []
    for det in detections:
        bbox = det.get("bbox_zyx")
        conf = float(det.get("confidence", 0.0))

        if bbox and isinstance(bbox, (list, tuple)) and len(bbox) == 6:
            _z1, y1, x1, _z2, y2, x2 = bbox
            x1 = int(max(0, min(width - 1, x1)))
            y1 = int(max(0, min(height - 1, y1)))
            x2 = int(max(0, min(width - 1, x2)))
            y2 = int(max(0, min(height - 1, y2)))
            if x2 > x1 and y2 > y1:
                boxes.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": conf})
                continue

        center = det.get("center")
        if center and isinstance(center, (list, tuple)) and len(center) >= 3:
            cx = int(center[2])
            cy = int(center[1])
            half = 18
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(width - 1, cx + half)
            y2 = min(height - 1, cy + half)
            if x2 > x1 and y2 > y1:
                boxes.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": conf})

    boxes = sorted(boxes, key=lambda b: float(b.get("confidence", 0.0)), reverse=True)
    return boxes[:12]


def _render_overlay(image: Image.Image, detections: list[dict]) -> Image.Image:
    out = image.copy()
    draw = ImageDraw.Draw(out)
    boxes = _extract_boxes_2d(detections, out.width, out.height)

    for idx, box in enumerate(boxes, start=1):
        draw.rectangle((box["x1"], box["y1"], box["x2"], box["y2"]), outline=(255, 64, 64), width=3)
        if idx <= 6:
            label = f"Cand {idx} ({box['confidence'] * 100:.1f}%)"
            text_y = max(0, box["y1"] - 16)
            draw.rectangle((box["x1"], text_y, min(out.width - 1, box["x1"] + 170), text_y + 14), fill=(255, 64, 64))
            draw.text((box["x1"] + 4, text_y), label, fill=(255, 255, 255))

    return out


def _build_pdf_bytes(scan_id: int, report_text: str, preview_image: Image.Image, detections: list[dict]) -> bytes:
    return generate_pdf_bytes(
        detections=detections,
        scan_id=str(scan_id),
        report_text=report_text,
        preview_image=preview_image,
    )


@router.post("/auth/register", response_model=AuthResponse)
def register(payload: UserCreate, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    exists = db.query(models.User).filter(models.User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=409, detail="User already exists")

    user = models.User(
        name=payload.name,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Log audit event in background
    background_tasks.add_task(
        log_audit_event,
        db,
        user_id=user.id,
        action="REGISTER",
        entity="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )

    token = create_access_token(str(user.id))
    return {"token": token, "user": user}


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Fast login endpoint - audit logging happens in background"""
    import logging
    logger = logging.getLogger("login_profiler")
    
    t_start = time.time()
    
    # Profile user lookup
    t_query = time.time()
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    t_query_end = time.time()
    logger.info(f"[LOGIN] User lookup took {(t_query_end - t_query)*1000:.2f}ms")
    
    if not user:
        logger.warning(f"[LOGIN] User not found for email: {payload.email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Profile password verification
    t_pwd = time.time()
    pwd_valid = verify_password(payload.password, user.password_hash)
    t_pwd_end = time.time()
    logger.info(f"[LOGIN] Password verification took {(t_pwd_end - t_pwd)*1000:.2f}ms")
    
    if not pwd_valid:
        logger.warning(f"[LOGIN] Invalid password for user: {user.email}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Log audit event in background (doesn't block response)
    background_tasks.add_task(
        log_audit_event,
        db,
        user_id=user.id,
        action="LOGIN",
        entity="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )

    # Profile token creation
    t_token = time.time()
    token = create_access_token(str(user.id))
    t_token_end = time.time()
    logger.info(f"[LOGIN] Token creation took {(t_token_end - t_token)*1000:.2f}ms")
    
    t_end = time.time()
    logger.info(f"[LOGIN] Total time: {(t_end - t_start)*1000:.2f}ms (user: {user.email})")
    
    return {"token": token, "user": user}


@router.post("/auth/logout")
def logout(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()):
    # Log audit event in background (doesn't block logout)
    background_tasks.add_task(
        log_audit_event,
        db,
        user_id=current_user.id,
        action="LOGOUT",
        entity="user",
        entity_id=current_user.id,
        metadata={"email": current_user.email},
    )
    return {"message": "Logged out successfully"}


@router.get("/user/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/user/profile", response_model=UserOut)
def user_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.put("/user/profile", response_model=UserOut)
def update_profile(
    payload: dict,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_name = payload.get("name")
    if isinstance(new_name, str) and new_name.strip():
        current_user.name = new_name.strip()
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        log_audit_event(
            db,
            user_id=current_user.id,
            action="UPDATE_PROFILE",
            entity="user",
            entity_id=current_user.id,
            metadata={"name": current_user.name},
        )
    return current_user


@router.get("/user/stats")
def user_stats(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan_ids = [
        scan_id
        for (scan_id,) in db.query(models.CTScan.id).filter(models.CTScan.owner_id == current_user.id).all()
    ]

    total_scans = len(scan_ids)

    if not scan_ids:
        return {
            "total_scans": 0,
            "total_detections": 0,
            "total_nodules": 0,
            "total_reports": 0,
            "recent_scans": [],
        }

    latest_detection_subq = (
        db.query(
            models.DetectionResult.scan_id.label("scan_id"),
            func.max(models.DetectionResult.id).label("latest_id"),
        )
        .filter(models.DetectionResult.scan_id.in_(scan_ids))
        .group_by(models.DetectionResult.scan_id)
        .subquery()
    )

    latest_detections = (
        db.query(models.DetectionResult.scan_id, models.DetectionResult.boxes_text)
        .join(latest_detection_subq, models.DetectionResult.id == latest_detection_subq.c.latest_id)
        .all()
    )

    total_nodules = 0
    for _, boxes_text in latest_detections:
        if not boxes_text:
            continue
        try:
            total_nodules += len(json.loads(boxes_text))
        except Exception:
            continue

    total_reports = (
        db.query(func.count(func.distinct(models.ClinicalReport.scan_id)))
        .filter(models.ClinicalReport.scan_id.in_(scan_ids))
        .scalar()
        or 0
    )

    return {
        "total_scans": int(total_scans),
        "total_detections": int(len(latest_detections)),
        "total_nodules": int(total_nodules),
        "total_reports": int(total_reports),
        "recent_scans": [],
    }


@router.get("/scans", response_model=list[ScanOut])
def list_scans(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scans = (
        db.query(models.CTScan)
        .filter(models.CTScan.owner_id == current_user.id)
        .order_by(models.CTScan.upload_date.desc())
        .all()
    )
    results = []
    for scan in scans:
        last_detection = (
            db.query(models.DetectionResult)
            .filter(models.DetectionResult.scan_id == scan.id)
            .order_by(models.DetectionResult.id.desc())
            .first()
        )
        has_report = db.query(models.ClinicalReport.id).filter(models.ClinicalReport.scan_id == scan.id).first() is not None
        nodule_count = 0
        if last_detection and last_detection.boxes_text:
            try:
                nodule_count = len(json.loads(last_detection.boxes_text))
            except Exception:
                nodule_count = 0

        results.append(
            {
                "id": scan.id,
                "file_name": scan.file_name,
                "upload_date": scan.upload_date,
                "status": "completed" if last_detection else "uploaded",
                "nodule_count": nodule_count,
                "has_report": has_report,
            }
        )
    return results


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    last_detection = (
        db.query(models.DetectionResult)
        .filter(models.DetectionResult.scan_id == scan.id)
        .order_by(models.DetectionResult.id.desc())
        .first()
    )
    has_report = db.query(models.ClinicalReport.id).filter(models.ClinicalReport.scan_id == scan.id).first() is not None

    nodule_count = 0
    if last_detection and last_detection.boxes_text:
        try:
            nodule_count = len(json.loads(last_detection.boxes_text))
        except Exception:
            nodule_count = 0

    return {
        "id": scan.id,
        "file_name": scan.file_name,
        "upload_date": scan.upload_date,
        "status": "completed" if last_detection else "uploaded",
        "nodule_count": nodule_count,
        "has_report": has_report,
    }


@router.get("/scans/{scan_id}/preview")
def scan_preview(
    scan_id: int,
    with_boxes: bool = Query(default=True),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        path = _resolve_scan_path(scan.file_path)
        image = _load_preview_image(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detections = []
    if with_boxes:
        latest_detection = (
            db.query(models.DetectionResult)
            .filter(models.DetectionResult.scan_id == scan_id)
            .order_by(models.DetectionResult.id.desc())
            .first()
        )
        if latest_detection and latest_detection.boxes_text:
            try:
                detections = json.loads(latest_detection.boxes_text)
            except Exception:
                detections = []

    if with_boxes and detections:
        image = _render_overlay(image, detections)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="image/png")


@router.delete("/scans/{scan_id}")
def delete_scan(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        if os.path.exists(scan.file_path):
            os.remove(scan.file_path)
    except OSError:
        pass

    db.delete(scan)
    db.commit()

    log_audit_event(
        db,
        user_id=current_user.id,
        action="DELETE_SCAN",
        entity="ct_scan",
        entity_id=scan_id,
        metadata={},
    )
    return {"message": "Scan deleted successfully"}


@router.post("/scans/upload", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
def upload_scan(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    filename = _safe_filename(file.filename)
    file_name_lower = filename.lower()
    allowed = _allowed_extensions()
    if not any(file_name_lower.endswith(ext) for ext in allowed):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    content = file.file.read()
    max_bytes = max(1, settings.MAX_UPLOAD_SIZE_MB) * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

    stored_name = f"scan_{current_user.id}_{int(time.time())}_{filename}"
    path = upload_dir / stored_name

    with path.open("wb") as out:
        out.write(content)

    scan = models.CTScan(file_name=filename, file_path=str(path), owner_id=current_user.id)
    db.add(scan)
    db.commit()
    db.refresh(scan)

    log_audit_event(
        db,
        user_id=current_user.id,
        action="UPLOAD_SCAN",
        entity="ct_scan",
        entity_id=scan.id,
        metadata={"file_name": scan.file_name},
    )

    return scan


@router.post("/analyze/{scan_id}", response_model=AnalyzeResponse)
async def analyze_endpoint(
    scan_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        result = await run_in_threadpool(analyze_scan, scan.file_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    det = models.DetectionResult(
        scan_id=scan.id,
        confidence_score=result.confidence_score,
        lesion_size=result.avg_size_mm,
        boxes_text=detections_to_boxes_text(result.detections),
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    log_audit_event(
        db,
        user_id=current_user.id,
        action="ANALYZE_SCAN",
        entity="ct_scan",
        entity_id=scan.id,
        metadata={"num_detections": result.num_detections, "runtime": result.runtime},
    )

    return {
        "id": det.id,
        "scan_id": scan.id,
        "num_detections": result.num_detections,
        "confidence_score": result.confidence_score,
        "avg_size_mm": result.avg_size_mm,
        "detections": result.detections,
        "runtime": result.runtime,
    }


@router.post("/reports/{scan_id}", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    scan_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    detection = (
        db.query(models.DetectionResult)
        .filter(models.DetectionResult.scan_id == scan.id)
        .order_by(models.DetectionResult.id.desc())
        .first()
    )
    if not detection:
        raise HTTPException(status_code=400, detail="Analyze scan before generating report")

    detections = json.loads(detection.boxes_text)
    report_text, _structured = generate_report_text(detections)

    report = models.ClinicalReport(scan_id=scan.id, report_text=report_text)
    db.add(report)
    db.commit()
    db.refresh(report)

    log_audit_event(
        db,
        user_id=current_user.id,
        action="GENERATE_REPORT",
        entity="clinical_report",
        entity_id=report.id,
        metadata={"scan_id": scan.id},
    )

    return report


@router.get("/results/{scan_id}")
def get_results(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    detections = (
        db.query(models.DetectionResult)
        .filter(models.DetectionResult.scan_id == scan_id)
        .order_by(models.DetectionResult.id.desc())
        .all()
    )

    items = []
    for d in detections:
        items.append(
            {
                "id": d.id,
                "scan_id": d.scan_id,
                "confidence_score": d.confidence_score,
                "lesion_size": d.lesion_size,
                "created_date": d.created_date.isoformat() if d.created_date else None,
                "detections": json.loads(d.boxes_text) if d.boxes_text else [],
            }
        )
    
    if not items:
        response = {
            "total_detections": 0,
            "avg_confidence": 0.0,
            "processing_time": 0.0,
            "detections": [],
            "history": [],
        }
        # Add risk assessment if available
        if RISK_ASSESSMENT_AVAILABLE:
            risk_analysis = RiskAssessment.assess_detections([])
            response.update({
                "risk_level": risk_analysis.risk_level.value,
                "requires_followup": risk_analysis.requires_followup,
                "recommendations": risk_analysis.recommendations,
                "max_size_mm": 0,
                "avg_size_mm": 0,
            })
        return response

    latest = items[0]
    detections_payload = latest.get("detections", [])
    avg_conf = 0.0
    if detections_payload:
        avg_conf = float(np.mean([float(d.get("confidence", 0.0)) for d in detections_payload]))

    response = {
        "total_detections": len(detections_payload),
        "avg_confidence": avg_conf,
        "processing_time": None,
        "detections": detections_payload,
        "history": items,
    }
    
    # Add risk assessment if available
    if RISK_ASSESSMENT_AVAILABLE and detections_payload:
        try:
            risk_analysis = RiskAssessment.assess_detections(detections_payload)
            response.update({
                "risk_level": risk_analysis.risk_level.value,
                "requires_followup": risk_analysis.requires_followup,
                "recommendations": risk_analysis.recommendations,
                "max_size_mm": float(risk_analysis.max_size_mm),
                "avg_size_mm": float(risk_analysis.avg_size_mm),
                "nodules_analysis": [n.to_dict() for n in risk_analysis.nodules],
            })
        except Exception as e:
            # Risk assessment failed, but don't break detection response
            import logging
            logging.warning(f"Risk assessment failed: {e}")
    
    return response



@router.get("/report/{scan_id}", response_model=ReportResponse)
def get_report(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    report = (
        db.query(models.ClinicalReport)
        .filter(models.ClinicalReport.scan_id == scan_id)
        .order_by(models.ClinicalReport.id.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/report/{scan_id}/download")
def download_report(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = get_report(scan_id, current_user, db)
    scan = (
        db.query(models.CTScan)
        .filter(models.CTScan.id == scan_id, models.CTScan.owner_id == current_user.id)
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    latest_detection = (
        db.query(models.DetectionResult)
        .filter(models.DetectionResult.scan_id == scan_id)
        .order_by(models.DetectionResult.id.desc())
        .first()
    )

    detections = []
    if latest_detection and latest_detection.boxes_text:
        try:
            detections = json.loads(latest_detection.boxes_text)
        except Exception:
            detections = []

    try:
        preview = _load_preview_image(_resolve_scan_path(scan.file_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pdf_bytes = _build_pdf_bytes(scan_id, report.report_text or "", preview, detections)
    headers = {"Content-Disposition": f"attachment; filename=report_{scan_id}.pdf"}
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.post("/generate_report/{scan_id}", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def generate_report_alias(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_report(scan_id, current_user, db)


@router.post("/upload", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
def upload_alias(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upload_scan(file, current_user, db)


@router.post("/report/{scan_id}", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def report_alias(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return create_report(scan_id, current_user, db)


@router.get("/history", response_model=list[ScanOut])
def history_alias(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_scans(current_user, db)


@router.get("/admin/users", response_model=list[UserOut])
def list_all_users(
    _admin: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    users = db.query(models.User).order_by(models.User.id.asc()).all()
    return users


@router.get("/admin/audit-logs")
def list_audit_logs(
    limit: int = 100,
    _admin: models.User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    safe_limit = max(1, min(limit, 500))
    rows = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "metadata": r.meta_json,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
