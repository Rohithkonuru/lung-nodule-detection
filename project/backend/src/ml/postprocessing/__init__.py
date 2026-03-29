"""
Post-processing for nodule detections.

Handles:
- Non-Maximum Suppression (NMS)
- Confidence filtering
- Duplicate removal
- Size filtering
"""

import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class DetectionPostProcessor:
    """Post-processing for nodule detections."""
    
    def __init__(self):
        """Initialize post-processor."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @staticmethod
    def nms_3d(detections: List[Dict], iou_threshold: float = 0.3) -> List[Dict]:
        """
        Apply Non-Maximum Suppression in 3D.
        
        Removes overlapping detections, keeping highest confidence ones.
        
        Args:
            detections: List of {center, confidence, size_mm}
            iou_threshold: IoU threshold for overlap detection
        
        Returns:
            Filtered detections after NMS
        """
        if not detections:
            return []
        
        # Sort by confidence descending
        sorted_dets = sorted(detections, key=lambda x: x['confidence'], reverse=True)
        keep = []
        
        for i, det in enumerate(sorted_dets):
            # Check overlap with already kept detections
            keep_this = True
            for kept_det in keep:
                iou = DetectionPostProcessor._compute_3d_iou(det, kept_det)
                if iou > iou_threshold:
                    keep_this = False
                    break
            
            if keep_this:
                keep.append(det)
        
        logger.debug(f"NMS: {len(sorted_dets)} → {len(keep)} detections")
        return keep
    
    @staticmethod
    def _compute_3d_iou(det1: Dict, det2: Dict) -> float:
        """Compute 3D IoU between two detection spheres."""
        center1 = np.array(det1['center'], dtype=np.float32)
        center2 = np.array(det2['center'], dtype=np.float32)
        
        # Sphere radius in voxels (approximate from size_mm at 1mm spacing)
        r1 = det1['size_mm'] / 2.0
        r2 = det2['size_mm'] / 2.0
        
        # Distance
        distance = np.linalg.norm(center1 - center2)
        
        # Overlap
        if distance >= r1 + r2:
            return 0.0
        
        # Intersection volume (simplified)
        if distance <= abs(r1 - r2):
            # One sphere inside another
            smaller_r = min(r1, r2)
            intersection = (4/3) * np.pi * smaller_r**3
        else:
            # Partial overlap
            a = r1
            b = r2
            h = (a + b - distance) / 2
            intersection = (np.pi / 12) * h**2 * (3*a + 3*b - h)
        
        # Union volume
        v1 = (4/3) * np.pi * r1**3
        v2 = (4/3) * np.pi * r2**3
        union = v1 + v2 - intersection
        
        iou = intersection / max(union, 1e-6)
        return float(iou)
    
    @staticmethod
    def filter_by_confidence(detections: List[Dict], threshold: float = 0.5) -> List[Dict]:
        """Filter detections by confidence threshold."""
        filtered = [d for d in detections if d['confidence'] >= threshold]
        logger.debug(f"Confidence filtering: {len(detections)} → {len(filtered)} "
                    f"(threshold={threshold})")
        return filtered
    
    @staticmethod
    def filter_by_size(detections: List[Dict], 
                      min_size_mm: float = 3.0, 
                      max_size_mm: float = 100.0) -> List[Dict]:
        """
        Filter detections by size.
        
        Clinical context:
        - < 3mm: Below detection threshold
        - 3-5mm: Nodule, monitor
        - 5-10mm: Significant, recommend followup
        - > 10mm: High risk, immediate attention
        """
        filtered = [d for d in detections 
                   if min_size_mm <= d['size_mm'] <= max_size_mm]
        logger.debug(f"Size filtering: {len(detections)} → {len(filtered)} "
                    f"(size {min_size_mm}-{max_size_mm}mm)")
        return filtered
    
    @staticmethod
    def remove_duplicates(detections: List[Dict], distance_threshold_mm: float = 10.0) -> List[Dict]:
        """Remove duplicate detections that are too close."""
        if not detections:
            return []
        
        unique = []
        for det in detections:
            is_duplicate = False
            for unique_det in unique:
                center1 = np.array(det['center'], dtype=np.float32)
                center2 = np.array(unique_det['center'], dtype=np.float32)
                distance = np.linalg.norm(center1 - center2)
                
                if distance < distance_threshold_mm:
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if det['confidence'] > unique_det['confidence']:
                        unique.remove(unique_det)
                        unique.append(det)
                    break
            
            if not is_duplicate:
                unique.append(det)
        
        logger.debug(f"Duplicate removal: {len(detections)} → {len(unique)}")
        return unique
    
    def postprocess(self, detections: List[Dict], 
                   confidence_threshold: float = 0.5,
                   min_size_mm: float = 3.0,
                   iou_threshold: float = 0.3) -> List[Dict]:
        """
        Complete post-processing pipeline.
        
        Steps:
        1. Filter by confidence
        2. Filter by size
        3. Remove duplicates
        4. Apply NMS
        """
        try:
            self.logger.info(f"Post-processing {len(detections)} detections...")
            
            # Apply filters
            filtered = self.filter_by_confidence(detections, confidence_threshold)
            filtered = self.filter_by_size(filtered, min_size_mm=min_size_mm)
            filtered = self.remove_duplicates(filtered)
            
            # NMS
            final = self.nms_3d(filtered, iou_threshold)
            
            self.logger.info(f"Post-processing complete: {len(detections)} → {len(final)} detections")
            return final
            
        except Exception as e:
            self.logger.error(f"Post-processing failed: {str(e)}")
            return detections  # Return unprocessed if error


# Global post-processor instance
_postprocessor = None


def get_postprocessor() -> DetectionPostProcessor:
    """Get singleton post-processor instance."""
    global _postprocessor
    if _postprocessor is None:
        _postprocessor = DetectionPostProcessor()
    return _postprocessor


__all__ = ['DetectionPostProcessor', 'get_postprocessor']
