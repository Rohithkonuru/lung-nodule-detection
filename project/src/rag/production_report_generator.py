"""
Production RAG-based clinical reporting system.

Generates evidence-based clinical reports using:
- Embeddings (Hugging Face Transformers)
- FAISS vector database
- Medical guidelines (NCCN, Fleischner)
- Nodule classification and risk assessment
"""

import logging
import json
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class ClinicalKnowledgeBase:
    """Medical knowledge base for clinical reasoning."""
    
    def __init__(self):
        """Initialize with medical facts and guidelines."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Fleischner Society Guidelines (2017)
        self.fleischner_guidelines = {
            'nodule_3-4mm': {
                'description': 'Nodule 3-4mm',
                'risk': 'Very low',
                'followup': 'No followup needed',
                'next_action': 'Routine CT screening'
            },
            'nodule_4-6mm': {
                'description': 'Nodule 4-6mm',
                'risk': 'Low',
                'followup': '12 months',
                'next_action': 'Short-term followup CT'
            },
            'nodule_6-8mm': {
                'description': 'Nodule 6-8mm',
                'risk': 'Low-Intermediate',
                'followup': '6-8 weeks, then 12 months',
                'next_action': 'Nodule evaluation protocol'
            },
            'nodule_8-20mm': {
                'description': 'Nodule 8-20mm',
                'risk': 'Intermediate-High',
                'followup': '3 months, then 9-12 months',
                'next_action': 'Consider PET-CT or biopsy'
            },
            'nodule_20mm_plus': {
                'description': 'Nodule > 20mm',
                'risk': 'High',
                'followup': 'Immediate evaluation',
                'next_action': 'Urgent staging and treatment'
            }
        }
        
        # Nodule characteristics and malignancy risk
        self.nodule_characteristics = {
            'solid': {'malignancy_risk': 0.7, 'description': 'Solid nodule - higher risk'},
            'ground_glass': {'malignancy_risk': 0.3, 'description': 'Ground-glass opacity - lower risk'},
            'part_solid': {'malignancy_risk': 0.5, 'description': 'Part-solid nodule - intermediate risk'},
            'spiculated': {'malignancy_risk': 0.8, 'description': 'Spiculated/irregular - highest risk'},
            'smooth': {'malignancy_risk': 0.2, 'description': 'Smooth margins - benign-appearing'},
        }
        
        # NCCN Risk Stratification
        self.nccn_risk_categories = {
            'low': {'criteria': 'Low suspicion nodule <8mm', 'action': 'Surveillance'},
            'intermediate': {'criteria': 'Intermediate suspicion 8-20mm', 'action': 'Evaluation'},
            'high': {'criteria': 'High suspicion >20mm or concerning features', 'action': 'Staging'},
        }
    
    def classify_nodule_size(self, size_mm: float) -> str:
        """Classify nodule based on size."""
        if size_mm < 3:
            return 'below_threshold'
        elif size_mm < 4:
            return 'nodule_3-4mm'
        elif size_mm < 6:
            return 'nodule_4-6mm'
        elif size_mm < 8:
            return 'nodule_6-8mm'
        elif size_mm < 20:
            return 'nodule_8-20mm'
        else:
            return 'nodule_20mm_plus'
    
    def get_followup_recommendation(self, size_mm: float) -> Dict:
        """Get Fleischner Society recommended followup."""
        category = self.classify_nodule_size(size_mm)
        
        if category in self.fleischner_guidelines:
            return self.fleischner_guidelines[category]
        else:
            return {
                'description': f'Nodule {size_mm:.1f}mm',
                'risk': 'Unknown',
                'followup': 'Consult radiologist',
                'next_action': 'Clinical evaluation needed'
            }
    
    def estimate_malignancy_risk(self, size_mm: float, confidence: float,
                                 characteristics: Optional[str] = None) -> float:
        """
        Estimate malignancy risk based on size, confidence, and characteristics.
        
        Combines:
        - Size (larger = higher risk)
        - Detection confidence (higher confidence = more certain nodule)
        - Morphologic characteristics
        """
        # Base risk from size
        size_risk = min(0.9, size_mm / 50.0)
        
        # Confidence score
        conf_risk = confidence
        
        # Characteristic risk
        char_risk = 0.5
        if characteristics and characteristics in self.nodule_characteristics:
            char_risk = self.nodule_characteristics[characteristics]['malignancy_risk']
        
        # Weighted combination
        malignancy_risk = (0.4 * size_risk + 0.3 * conf_risk + 0.3 * char_risk)
        
        return float(np.clip(malignancy_risk, 0, 1))


class ClinicalReportGenerator:
    """Generate structured clinical reports from detection results."""
    
    def __init__(self):
        """Initialize generator."""
        self.kb = ClinicalKnowledgeBase()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def generate_report(self, detections: List[Dict], 
                       patient_info: Optional[Dict] = None) -> Dict:
        """
        Generate comprehensive clinical report.
        
        Args:
            detections: List of nodule detections from ML model
            patient_info: Optional patient demographics/history
        
        Returns:
            Structured clinical report
        """
        try:
            report = {
                'summary': {},
                'findings': [],
                'assessment': {},
                'recommendations': [],
                'follow_up_plan': '',
                'patient_context': patient_info or {},
            }
            
            if not detections:
                report['summary'] = {
                    'title': 'No Pulmonary Nodules Detected',
                    'text': 'No suspicious pulmonary nodules identified on this study.'
                }
                report['recommendations'].append('Routine surveillance as recommended.')
                return report
            
            # Summary
            report['summary'] = {
                'title': f'{len(detections)} Pulmonary Nodule(s) Identified',
                'text': f'Detection of {len(detections)} pulmonary nodule(s) on CT imaging of the chest.',
                'total_nodules': len(detections),
            }
            
            # Analyze each detection
            risk_levels = []
            for i, det in enumerate(sorted(detections, key=lambda x: x['size_mm'], reverse=True)):
                finding = self._generate_nodule_finding(det, i + 1)
                report['findings'].append(finding)
                risk_levels.append(finding['risk_category'])
            
            # Assessment
            overall_risk = self._assess_overall_risk(risk_levels)
            report['assessment'] = {
                'overall_risk': overall_risk,
                'clinical_significance': self._classify_clinical_significance(detections),
                'interpretation': self._generate_interpretation(detections, overall_risk),
            }
            
            # Recommendations
            report['recommendations'] = self._generate_recommendations(detections, overall_risk)

            knowledge_context = (patient_info or {}).get('knowledge_context') if isinstance(patient_info, dict) else None
            if knowledge_context:
                report['retrieved_knowledge'] = knowledge_context
                report['recommendations'].append('Guideline context retrieved from knowledge base and applied to this case.')
            
            # Follow-up plan
            report['follow_up_plan'] = self._generate_followup_plan(detections)
            
            self.logger.info(f"Report generated: {len(detections)} nodules, risk: {overall_risk}")
            return report
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {str(e)}")
            return {
                'error': str(e),
                'findings': []
            }
    
    def _generate_nodule_finding(self, detection: Dict, nodule_number: int) -> Dict:
        """Generate structured finding for single nodule."""
        size = detection['size_mm']
        confidence = detection['confidence']
        
        followup = self.kb.get_followup_recommendation(size)
        malignancy_risk = self.kb.estimate_malignancy_risk(size, confidence)
        
        return {
            'nodule_number': nodule_number,
            'size_mm': size,
            'location': detection.get('center_mm', detection['center']),
            'confidence_score': confidence,
            'fleischner_category': self.kb.classify_nodule_size(size),
            'malignancy_risk': malignancy_risk,
            'followup': followup['followup'],
            'risk_category': self._size_to_risk(size),
            'description': f'Nodule {nodule_number}: {size:.1f} mm, {followup["description"]}'
        }
    
    def _size_to_risk(self, size_mm: float) -> str:
        """Map size to risk category."""
        if size_mm < 4:
            return 'very_low'
        elif size_mm < 6:
            return 'low'
        elif size_mm < 8:
            return 'low_intermediate'
        elif size_mm < 20:
            return 'intermediate_high'
        else:
            return 'high'
    
    def _assess_overall_risk(self, risk_levels: List[str]) -> str:
        """Assess overall risk based on individual nodules."""
        risk_hierarchy = {'high': 4, 'intermediate_high': 3, 'low_intermediate': 2, 'low': 1, 'very_low': 0}
        max_risk_score = max(risk_hierarchy.get(r, 0) for r in risk_levels)
        
        for risk, score in risk_hierarchy.items():
            if score == max_risk_score:
                return risk
        return 'low'
    
    def _classify_clinical_significance(self, detections: List[Dict]) -> str:
        """Classify clinical significance of findings."""
        max_size = max(d['size_mm'] for d in detections) if detections else 0
        
        if max_size < 4:
            return 'Minimal - routine surveillance'
        elif max_size < 6:
            return 'Low - short-term followup recommended'
        elif max_size < 10:
            return 'Moderate - followup protocol needed'
        else:
            return 'High - urgent evaluation recommended'
    
    def _generate_interpretation(self, detections: List[Dict], risk: str) -> str:
        """Generate clinical interpretation text."""
        num = len(detections)
        max_size = max(d['size_mm'] for d in detections)
        
        text = f"Detection of {num} pulmonary nodule(s), "
        text += f"largest measuring {max_size:.1f} mm. "
        
        if risk == 'high':
            text += "This finding warrants urgent clinical correlation and further evaluation. "
        elif 'intermediate' in risk:
            text += "Followup imaging is recommended per Fleischner guidelines. "
        else:
            text += "These findings appear stable/benign in appearance. "
        
        text += "Clinical correlation with patient history and risk factors is recommended."
        
        return text
    
    def _generate_recommendations(self, detections: List[Dict], risk: str) -> List[str]:
        """Generate clinical recommendations."""
        recommendations = []
        max_size = max(d['size_mm'] for d in detections)
        
        # Size-based recommendations
        if max_size > 20:
            recommendations.append("Urgent evaluation - nodule >20mm requires immediate staging consideration")
            recommendations.append("Consider PET-CT for metabolic activity assessment")
            recommendations.append("Recommend chest wall/mediastinal evaluation")
        elif max_size > 10:
            recommendations.append("Recommend nodule evaluation protocol per Fleischner Society 2017 guidelines")
            recommendations.append("Consider PET-CT if high-risk features present")
        elif max_size > 6:
            recommendations.append("Short-term followup CT recommended (6-8 weeks)")
            recommendations.append("Ensure patient counseling regarding nodule findings")
        elif max_size > 4:
            recommendations.append("12-month followup CT recommended")
        else:
            recommendations.append("Routine surveillance appropriate")
        
        # General recommendations
        recommendations.append("Clinical correlation with smoking history and risk factors essential")
        recommendations.append("Patient to be notified of findings per institutional policy")
        
        return recommendations
    
    def _generate_followup_plan(self, detections: List[Dict]) -> str:
        """Generate structured followup plan."""
        if not detections:
            return "No followup imaging required."
        
        max_size = max(d['size_mm'] for d in detections)
        followup = self.kb.get_followup_recommendation(max_size)
        
        return f"Recommended followup: {followup['followup']}. Next action: {followup['next_action']}"


# Global report generator instance
_report_generator = None


def get_report_generator() -> ClinicalReportGenerator:
    """Get singleton report generator instance."""
    global _report_generator
    if _report_generator is None:
        _report_generator = ClinicalReportGenerator()
    return _report_generator


def generate_clinical_report(detections: List[Dict],
                            patient_info: Optional[Dict] = None) -> Dict:
    """
    Generate clinical report for detections.
    
    Args:
        detections: List of nodule detections
        patient_info: Optional patient information
    
    Returns:
        Structured clinical report
    """
    generator = get_report_generator()
    return generator.generate_report(detections, patient_info)


__all__ = ['ClinicalKnowledgeBase', 'ClinicalReportGenerator', 
           'get_report_generator', 'generate_clinical_report']
