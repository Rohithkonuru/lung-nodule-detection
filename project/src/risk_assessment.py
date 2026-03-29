#!/usr/bin/env python3
"""
Smart nodule risk assessment and interpretation.

Adds:
- Risk categorization (Low/Medium/High)
- Size-based severity scoring
- Confidence interpretation
- Clinical recommendations
- Nodule characteristics summary
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np


class RiskLevel(Enum):
    """Pulmonary nodule risk classification based on Lung-RADS."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class NodulesAnalysis:
    """Complete nodule analysis with risk assessment."""
    total_detected: int
    max_size_mm: float
    avg_size_mm: float
    avg_confidence: float
    risk_level: RiskLevel
    requires_followup: bool
    recommendations: List[str]
    nodules: List['NodulesDetails'] = None
    
    def to_dict(self):
        return {
            "total_detected": self.total_detected,
            "max_size_mm": round(self.max_size_mm, 2),
            "avg_size_mm": round(self.avg_size_mm, 2),
            "avg_confidence": round(self.avg_confidence, 3),
            "risk_level": self.risk_level.value,
            "requires_followup": self.requires_followup,
            "recommendations": self.recommendations,
            "nodules": [n.to_dict() for n in (self.nodules or [])]
        }


@dataclass
class NodulesDetails:
    """Individual nodule details."""
    nodule_id: int
    center_x: float
    center_y: float
    center_z: float
    size_mm: float
    confidence: float
    risk_category: str
    follow_up_weeks: Optional[int]
    characteristics: str
    
    def to_dict(self):
        return {
            "nodule_id": self.nodule_id,
            "center": {"x": round(self.center_x, 2), "y": round(self.center_y, 2), "z": round(self.center_z, 2)},
            "size_mm": round(self.size_mm, 2),
            "confidence": round(self.confidence, 3),
            "risk_category": self.risk_category,
            "follow_up_weeks": self.follow_up_weeks,
            "characteristics": self.characteristics
        }


class RiskAssessment:
    """
    Automatic risk assessment for detected nodules.
    Based on Lung-RADS guidelines (American College of Radiology).
    """
    
    # Size thresholds (mm) for risk classification
    SIZE_THRESHOLDS = {
        "trivial": 3,      # <3mm
        "small": 6,        # 3-6mm
        "medium": 8,       # 6-8mm
        "moderate": 15,    # 8-15mm
        "large": 30,       # 15-30mm
    }
    
    # Follow-up intervals based on Lung-RADS
    FOLLOWUP_WEEKS = {
        "Low": None,           # No follow-up
        "Medium": 12,          # 12 weeks (3 months)
        "High": 4,             # 4 weeks (1 month)
        "Critical": 1,         # 1 week (urgent)
    }
    
    @staticmethod
    def classify_nodule_size(size_mm: float) -> str:
        """Classify nodule based on size."""
        if size_mm < 3:
            return "Trivial"
        elif size_mm < 6:
            return "Small"
        elif size_mm < 8:
            return "Medium"
        elif size_mm < 15:
            return "Moderate"
        elif size_mm < 30:
            return "Large"
        else:
            return "Very Large"
    
    @staticmethod
    def assess_confidence_quality(confidence: float) -> str:
        """Interpret model confidence."""
        if confidence < 0.5:
            return "Low confidence - may be false positive"
        elif confidence < 0.7:
            return "Moderate confidence - recommend radiologist review"
        elif confidence < 0.85:
            return "High confidence - likely genuine nodule"
        else:
            return "Very high confidence - definite nodule"
    
    @staticmethod
    def calculate_risk_level(
        size_mm: float,
        confidence: float,
        nodule_count: int = 1
    ) -> RiskLevel:
        """
        Calculate risk level based on nodule characteristics.
        
        Risk is determined by:
        1. Size (primary)
        2. Confidence / likelihood of malignancy
        3. Number of nodules (solitary vs multiple)
        """
        
        # Base risk assessment on size
        if size_mm < 3:
            base_risk = RiskLevel.LOW
        elif size_mm < 6:
            base_risk = RiskLevel.LOW if confidence < 0.7 else RiskLevel.MEDIUM
        elif size_mm < 8:
            base_risk = RiskLevel.MEDIUM
        elif size_mm < 15:
            base_risk = RiskLevel.MEDIUM if confidence < 0.8 else RiskLevel.HIGH
        elif size_mm < 30:
            base_risk = RiskLevel.HIGH
        else:
            base_risk = RiskLevel.CRITICAL
        
        # Adjust for confidence
        if base_risk != RiskLevel.LOW and confidence < 0.6:
            # Low confidence reduces risk by one level
            risk_levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
            curr_idx = risk_levels.index(base_risk)
            if curr_idx > 0:
                base_risk = risk_levels[curr_idx - 1]
        
        return base_risk
    
    @staticmethod
    def generate_characteristics(size_mm: float, confidence: float) -> str:
        """Generate human-readable nodule characteristics."""
        size_class = RiskAssessment.classify_nodule_size(size_mm)
        
        characteristics = []
        
        # Size characteristic
        characteristics.append(f"{size_class} nodule ({size_mm:.1f}mm)")
        
        # Growth potential
        if size_mm < 5:
            characteristics.append("Low growth potential")
        elif size_mm < 10:
            characteristics.append("Moderate growth potential")
        else:
            characteristics.append("Higher growth potential")
        
        # Confidence assessment
        if confidence > 0.9:
            characteristics.append("High detection confidence")
        elif confidence > 0.7:
            characteristics.append("Moderate detection confidence")
        
        # Morphology (determined from confidence pattern)
        if confidence > 0.8 and size_mm > 5:
            characteristics.append("Suspect features present")
        else:
            characteristics.append("Benign features likely")
        
        return ", ".join(characteristics)
    
    @staticmethod
    def assess_detections(
        detections: List[dict]
    ) -> NodulesAnalysis:
        """
        Complete assessment of all detected nodules.
        
        Args:
            detections: List of detection dicts with 'size_mm' and 'confidence' keys
        
        Returns:
            NodulesAnalysis with risk assessment and recommendations
        """
        if not detections:
            return NodulesAnalysis(
                total_detected=0,
                max_size_mm=0,
                avg_size_mm=0,
                avg_confidence=0,
                risk_level=RiskLevel.LOW,
                requires_followup=False,
                recommendations=["No nodules detected. Routine surveillance recommended."],
                nodules=[]
            )
        
        # Extract metrics
        sizes = [d.get('size_mm', 0) for d in detections]
        confidences = [d.get('confidence', 0) for d in detections]
        
        max_size = max(sizes)
        avg_size = np.mean(sizes)
        avg_confidence = np.mean(confidences)
        
        # Determine overall risk (based on largest nodule)
        overall_risk = RiskAssessment.calculate_risk_level(
            max_size,
            max(confidences),
            len(detections)
        )
        
        # Generate recommendations
        recommendations = RiskAssessment._generate_recommendations(
            overall_risk,
            len(detections),
            max_size,
            avg_confidence
        )
        
        # Assess individual nodules
        nodules_details = []
        for i, det in enumerate(detections, 1):
            size = det.get('size_mm', 0)
            conf = det.get('confidence', 0.5)
            risk = RiskAssessment.calculate_risk_level(size, conf)
            
            detail = NodulesDetails(
                nodule_id=i,
                center_x=det.get('center_x', 0),
                center_y=det.get('center_y', 0),
                center_z=det.get('center_z', 0),
                size_mm=size,
                confidence=conf,
                risk_category=risk.value,
                follow_up_weeks=RiskAssessment.FOLLOWUP_WEEKS.get(risk.value),
                characteristics=RiskAssessment.generate_characteristics(size, conf)
            )
            nodules_details.append(detail)
        
        return NodulesAnalysis(
            total_detected=len(detections),
            max_size_mm=max_size,
            avg_size_mm=avg_size,
            avg_confidence=avg_confidence,
            risk_level=overall_risk,
            requires_followup=overall_risk in [RiskLevel.HIGH, RiskLevel.CRITICAL],
            recommendations=recommendations,
            nodules=nodules_details
        )
    
    @staticmethod
    def _generate_recommendations(
        risk_level: RiskLevel,
        nodule_count: int,
        max_size: float,
        avg_confidence: float
    ) -> List[str]:
        """Generate clinical recommendations based on assessment."""
        recommendations = []
        
        if risk_level == RiskLevel.LOW:
            recommendations.append("✓ No suspicious findings")
            recommendations.append("Routine follow-up imaging in 12 months recommended")
            recommendations.append("Continue smoking cessation if applicable")
        
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.append(f"⚠ {nodule_count} nodule(s) detected")
            recommendations.append(f"Largest nodule: {max_size:.1f}mm")
            recommendations.append("Follow-up CT imaging in 3 months recommended")
            recommendations.append("Close radiologist review advised")
        
        elif risk_level == RiskLevel.HIGH:
            recommendations.append(f"⚠⚠ {nodule_count} lung nodule(s) detected")
            recommendations.append(f"Maximum size: {max_size:.1f}mm (REQUIRES FOLLOW-UP)")
            recommendations.append("Urgent: CT follow-up imaging within 1 month")
            recommendations.append("Recommend consultation with pulmonologist")
            recommendations.append("Consider additional imaging: PET-CT or biopsy")
        
        elif risk_level == RiskLevel.CRITICAL:
            recommendations.append(f"🚨 CRITICAL: Large nodule(s) detected ({max_size:.1f}mm)")
            recommendations.append("URGENT: Immediate radiologist review required")
            recommendations.append("Clinical correlation with patient symptoms essential")
            recommendations.append("Recommend urgent specialist evaluation")
            recommendations.append("Consider advanced imaging: PET-CT, MRI, or biopsy")
            recommendations.append("This finding may warrant urgent clinical intervention")
        
        # Add confidence note
        if avg_confidence < 0.65:
            recommendations.append("\nNote: Some detections have lower confidence scores. Recommend radiologist confirmation.")
        
        return recommendations


def generate_smart_report(analysis: NodulesAnalysis) -> str:
    """Generate formatted clinical report with risk assessment."""
    risk_icon = {
        "Low": "✓",
        "Medium": "⚠",
        "High": "⚠⚠",
        "Critical": "🚨"
    }
    
    lines = [
        "=" * 70,
        "LUNG NODULE DETECTION - RISK ASSESSMENT REPORT",
        "=" * 70,
        "",
        "SUMMARY",
        "-" * 70,
        f"Nodules Detected:     {analysis.total_detected}",
        f"Risk Level:           {risk_icon.get(analysis.risk_level.value, '?')} {analysis.risk_level.value}",
        f"Max Nodule Size:      {analysis.max_size_mm:.1f} mm",
        f"Average Size:         {analysis.avg_size_mm:.1f} mm",
        f"Model Confidence:     {analysis.avg_confidence:.1%}",
        "",
    ]
    
    if analysis.total_detected > 0:
        lines.extend([
            "NODULE DETAILS",
            "-" * 70,
        ])
        
        for nodule in analysis.nodules:
            lines.extend([
                f"#{nodule.nodule_id}: {nodule.characteristics}",
                f"   Location: ({nodule.center_x:.0f}, {nodule.center_y:.0f}, {nodule.center_z:.0f})",
                f"   Size: {nodule.size_mm:.1f}mm | Confidence: {nodule.confidence:.1%}",
                f"   Risk: {nodule.risk_category}",
                f"   Follow-up: {nodule.follow_up_weeks or 'None'} weeks" if nodule.follow_up_weeks else "   Follow-up: None required",
                ""
            ])
    
    lines.extend([
        "RECOMMENDATIONS",
        "-" * 70,
    ])
    
    for i, rec in enumerate(analysis.recommendations, 1):
        if rec.startswith("\n"):
            lines.append(rec)
        else:
            lines.append(f"{i}. {rec}")
    
    lines.extend([
        "",
        "=" * 70,
        f"Risk Level: {analysis.risk_level.value} | Follow-up Required: {'Yes' if analysis.requires_followup else 'No'}",
        "=" * 70,
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    sample_detections = [
        {"size_mm": 8.5, "confidence": 0.92, "center_x": 100, "center_y": 150, "center_z": 45},
        {"size_mm": 5.2, "confidence": 0.78, "center_x": 200, "center_y": 180, "center_z": 85},
        {"size_mm": 3.1, "confidence": 0.65, "center_x": 120, "center_y": 200, "center_z": 120},
    ]
    
    analysis = RiskAssessment.assess_detections(sample_detections)
    report = generate_smart_report(analysis)
    print(report)
    print("\n\nJSON Output:")
    print(analysis.to_dict())
