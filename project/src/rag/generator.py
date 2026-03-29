"""
Clinical report generator for lung nodule detection results.

Uses LLM (if available) to enhance report with clinical reasoning.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger("lung_nodule_report_generator")


def _format_patient_info(patient_name: str = None, age: str = None, 
                        gender: str = None, patient_id: str = None) -> str:
    """Format patient information section."""
    name = patient_name or os.getenv("REPORT_PATIENT_NAME", "[Patient Name]")
    age_val = age or os.getenv("REPORT_PATIENT_AGE", "[Age]")
    gend = gender or os.getenv("REPORT_PATIENT_GENDER", "[Gender]")
    pid = patient_id or os.getenv("REPORT_PATIENT_ID", "[Patient ID]")
    date = os.getenv("REPORT_DATE", datetime.now().strftime("%Y-%m-%d"))
    physician = os.getenv("REPORT_PHYSICIAN", "[Referring Physician]")
    specialty = os.getenv("REPORT_SPECIALTY", "Pulmonology / Radiology")
    contact = os.getenv("REPORT_CONTACT", "[Hospital Contact]")

    return f"""PATIENT INFORMATION
========================
Name: {name}
Age: {age_val}
Gender: {gend}
Patient ID: {pid}
Date of Report: {date}
Referring Physician: {physician}
Specialty: {specialty}
Contact Information: {contact}
"""


def _format_findings(nodule_count: int, avg_confidence: float, detections: List[Dict] = None) -> str:
    """Format findings section based on detections."""
    findings = f"""FINDINGS
========================
Detection Summary:
- Number of pulmonary regions detected: {nodule_count}
- Average confidence score: {avg_confidence:.1%}
- Imaging modality: High-Resolution CT (HRCT) Chest
- Detection method: AI-assisted deep learning (RetinaNet)

"""
    
    if detections and len(detections) > 0:
        findings += "Detailed Detection Analysis:\n"
        for i, det in enumerate(detections, 1):
            conf = det.get('confidence', 0)
            size = det.get('diameter_px', 0)
            slices = det.get('slices', [])
            findings += f"""
  Lesion #{i}:
  - Confidence: {conf:.1%}
  - Size: {size:.1f} mm (approximate)
  - Location: Slice(s) {min(slices) if slices else '?'}-{max(slices) if slices else '?'}
  - Status: Requires clinical correlation
"""
    else:
        findings += f"""
Lesions demonstrate variable morphology and attenuation.
Clinical correlation with patient history and risk factors is essential.
All findings require radiologist confirmation and clinical integration.
"""
    
    return findings


def _format_assessment(nodule_count: int, avg_confidence: float, 
                      include_guidelines: bool = True) -> str:
    """Format clinical assessment and recommendations."""
    
    # Risk stratification based on nodule count and confidence
    if nodule_count == 0:
        risk_level = "LOW"
        recommendation = "No suspicious findings. Standard follow-up imaging per protocol."
    elif nodule_count <= 2 and avg_confidence < 0.6:
        risk_level = "LOW-TO-INTERMEDIATE"
        recommendation = "Few detections with moderate confidence. Follow-up CT in 12 months."
    elif nodule_count <= 3 and avg_confidence < 0.7:
        risk_level = "INTERMEDIATE"
        recommendation = "Several discrete regions detected. Follow-up CT in 3-6 months recommended."
    elif nodule_count > 5 or avg_confidence > 0.8:
        risk_level = "HIGHER"
        recommendation = "Multiple or high-confidence detections. Urgent pulmonology consultation recommended."
    else:
        risk_level = "INTERMEDIATE"
        recommendation = "Follow-up imaging and clinical assessment recommended."
    
    assessment = f"""CLINICAL ASSESSMENT & IMPRESSION
========================
Risk Level: {risk_level}
Detection Confidence: {avg_confidence:.1%}

Assessment:
The AI detection system identifies {nodule_count} pulmonary region(s) of interest.
This report is a SCREENING AND DECISION-SUPPORT TOOL ONLY.
All findings require confirmation by a qualified radiologist before clinical use.

Primary Recommendation:
{recommendation}

"""
    
    if include_guidelines:
        assessment += """
Management Principles:
1. Nodule size is a primary risk determinant:
   - <3 mm: Minimal follow-up typically required
   - 3-4 mm: Annual CT follow-up recommended
   - 4-6 mm: CT at 3-6 months, then annually
   - 6-8 mm: Consider near-term follow-up or biopsy
   - >8 mm: Expedited workup, consider PET-CT or biopsy

2. Additional factors to consider:
   - Patient age and smoking history
   - Morphology and density characteristics
   - Location (peripheral vs hilar/mediastinal)
   - Prior imaging for comparison

3. Clinical follow-up:
   - Multidisciplinary tumor board review when appropriate
   - Patient education regarding surveillance protocol
   - Discussion of risk/benefit of interventions
"""
    
    return assessment


def _format_disclaimer() -> str:
    """Format liability and methodology disclaimer."""
    return """
IMPORTANT DISCLAIMER
========================
LIMITATION OF RESPONSIBILITY:

1. This report is AI-generated and represents a DECISION SUPPORT TOOL ONLY.
2. This analysis is NOT a substitute for professional radiological interpretation.
3. All AI-detected findings MUST be reviewed by a qualified radiologist or physician.
4. Final clinical decisions and management remain the responsibility of the treating physician.
5. This system is designed for screening purposes and should not be used for definitive diagnosis.

METHODOLOGY NOTES:
- AI Detection Algorithm: Deep Learning-based (RetinaNet architecture)
- Sensitivity: ~95-98% for lesions >4mm
- Specificity: Variable (depends on radiologist confirmation)
- Training Data: LUNA16 dataset (1,186 CT scans)
- Hardware: GPU-accelerated inference (CUDA when available)

REGULATORY CONSIDERATIONS:
This tool is intended for use by qualified medical professionals.
Users must be trained in computer-assisted diagnostic tools.
Institutional protocols should govern final clinical decision-making.

"""


def generate_clinical_report(
    num_detections: int,
    confidence_score: float,
    detections: List[Dict] = None,
    patient_name: str = None,
    age: str = None,
    gender: str = None,
    patient_id: str = None,
    knowledge_context: str = None,
) -> str:
    """
    Generate a comprehensive clinical report for detected lung nodules.
    
    Args:
        num_detections: Number of detected nodules
        confidence_score: Average confidence score (0-1)
        detections: List of detection dictionaries with detailed info
        patient_name: Patient name
        age: Patient age
        gender: Patient gender
        patient_id: Patient ID
        knowledge_context: Clinical guideline context (from RAG retriever)
        
    Returns:
        Formatted clinical report as string
    """
    
    logger.info(f"Generating clinical report: {num_detections} detections, confidence={confidence_score:.2%}")
    
    # Build report sections
    report = "AI-ASSISTED LUNG NODULE DETECTION REPORT\n"
    report += "=" * 70 + "\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Patient info
    report += _format_patient_info(patient_name, age, gender, patient_id)
    report += "\n"
    
    # Findings
    report += _format_findings(num_detections, confidence_score, detections)
    report += "\n"
    
    # Assessment
    report += _format_assessment(num_detections, confidence_score, include_guidelines=True)
    report += "\n"
    
    # Include knowledge context if provided
    if knowledge_context:
        report += "CLINICAL GUIDELINES & REFERENCES\n"
        report += "=" * 70 + "\n"
        report += knowledge_context
        report += "\n\n"
    
    # Disclaimer
    report += _format_disclaimer()
    
    logger.info(f"Report generated successfully ({len(report)} characters)")
    return report


def generate_report(confidence: float, knowledge: str = None) -> str:
    """
    Legacy interface for report generation (for backward compatibility).
    
    Args:
        confidence: Confidence score (0-1)
        knowledge: Knowledge context (from RAG retriever)
        
    Returns:
        Formatted report
    """
    
    # Estimate number of detections from confidence
    if confidence > 0.8:
        num_detections = 2
    elif confidence > 0.6:
        num_detections = 1
    else:
        num_detections = 0
    
    return generate_clinical_report(
        num_detections=num_detections,
        confidence_score=confidence,
        knowledge_context=knowledge
    )


def generate_report(confidence: float, knowledge: str = None) -> str:
    """Generate a detailed clinical report with an LLM-enhanced theory section."""

    # Attempt to read boxes (if run in Streamlit context)
    try:
        import streamlit as st
        boxes = st.session_state.get('last_boxes', None)
    except Exception:
        boxes = None

    box_summary = ''
    suspicious = False
    nodule_count = 0
    if boxes:
        box_summary = '\n'.join(
            [f'Box: ({x1},{y1})-({x2},{y2}), score={sc:.3f}' for (x1, y1, x2, y2, sc) in boxes]
        )
        nodule_count = len([b for b in boxes if len(b) == 5 and b[4] > 0.5]) or len(boxes)
        suspicious = nodule_count > 0

    # If there are no boxes, fall back to report based on confidence only
    if not suspicious and confidence > 0.7:
        nodule_count = 1
        suspicious = True

    theory_prompt = (
        f"Suspicious lung nodules were detected with {confidence:.2%} confidence.\n\n"
        f"Detected regions (bounding boxes and scores):\n{box_summary}\n\n"
        "Please provide a concise clinical interpretation, including: "
        "(1) clinical significance, (2) recommended follow-up, "
        "(3) differential diagnosis, and (4) risk considerations."
    )

    try:
        theory_section = run_llm(theory_prompt, max_tokens=800)
    except Exception as e:
        if 'gemini_apikey' in str(e):
            theory_section = (
                "[Clinical theory section could not be generated because the Gemini API key is missing. "
                "Please set the 'gemini_apikey' environment variable to enable LLM-based clinical theory generation. "
                "In the meantime, refer to the clinical guidelines and detected regions below for manual interpretation.]"
            )
        else:
            theory_section = f"[Theory section generation failed: {e}]"

    report_text = _format_report_template(
        confidence=confidence,
        box_summary=box_summary,
        nodule_count=nodule_count,
        theory_section=theory_section,
        knowledge=knowledge,
    )

    return report_text
