"""
Integration code for risk assessment in API responses.

Add this to backend/app/api/v1/routes.py
"""

# At the top of routes.py, add this import:
# from src.risk_assessment import RiskAssessment, RiskLevel

# Then update the get_results endpoint like this:

def get_results_with_risk(scan_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get analysis results with integrated risk assessment."""
    from src.risk_assessment import RiskAssessment
    
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
        return {
            "total_detections": 0,
            "avg_confidence": 0.0,
            "processing_time": 0.0,
            "detections": [],
            "risk_level": "Low",
            "requires_followup": False,
            "recommendations": ["No nodules detected. Routine surveillance recommended."],
            "nodules_analysis": [],
            "history": [],
        }

    latest = items[0]
    detections_payload = latest.get("detections", [])
    
    # Calculate risk assessment
    risk_analysis = RiskAssessment.assess_detections(detections_payload)
    
    avg_conf = 0.0
    if detections_payload:
        avg_conf = float(np.mean([float(d.get("confidence", 0.0)) for d in detections_payload]))

    return {
        "total_detections": len(detections_payload),
        "avg_confidence": avg_conf,
        "processing_time": None,
        "detections": detections_payload,
        "risk_level": risk_analysis.risk_level.value,
        "requires_followup": risk_analysis.requires_followup,
        "recommendations": risk_analysis.recommendations,
        "max_size_mm": risk_analysis.max_size_mm,
        "avg_size_mm": risk_analysis.avg_size_mm,
        "nodules_analysis": [n.to_dict() for n in risk_analysis.nodules],
        "history": items,
    }
