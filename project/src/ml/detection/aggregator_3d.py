"""
3D aggregation of 2D RetinaNet detections.
Converts per-slice detections to 3D nodule localization.
"""

import numpy as np
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def _conf(det: Dict) -> float:
    """Read confidence value from either 'confidence' or 'score' key."""
    return float(det.get('confidence', det.get('score', 0.0)))


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """
    Calculate IoU (Intersection over Union) between two 2D boxes.
    
    Args:
        box1: [x1, y1, x2, y2]
        box2: [x1, y1, x2, y2]
    
    Returns:
        IoU score [0, 1]
    """
    x1_inter = max(box1[0], box2[0])
    y1_inter = max(box1[1], box2[1])
    x2_inter = min(box1[2], box2[2])
    y2_inter = min(box1[3], box2[3])
    
    inter_area = max(0, x2_inter - x1_inter) * max(0, y2_inter - y1_inter)
    
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0


def remove_duplicate_detections(
    all_detections: List[Dict],
    iou_threshold: float = 0.5,
) -> List[Dict]:
    """
    Remove duplicate detections based on bounding box IoU.
    
    If two detections have high IoU (>threshold), keep the one with higher confidence.
    
    Args:
        all_detections: List of detections with 'bbox' and 'confidence' fields
        iou_threshold: IoU threshold for considering detections as duplicates
    
    Returns:
        Filtered list with duplicates removed
    """
    if not all_detections:
        return []
    
    # Sort by confidence descending
    sorted_dets = sorted(all_detections, key=_conf, reverse=True)
    
    filtered = []
    suppressed = set()
    
    for i, det in enumerate(sorted_dets):
        if i in suppressed:
            continue
        
        filtered.append(det)
        
        # Check against all other detections
        for j in range(i + 1, len(sorted_dets)):
            if j in suppressed:
                continue
            
            other = sorted_dets[j]
            
            # Calculate IoU between bboxes
            iou = calculate_iou(det['bbox'], other['bbox'])
            
            # If IoU is high, suppress the lower confidence one
            if iou > iou_threshold:
                logger.debug(f"Suppressing duplicate: IoU={iou:.3f}, conf={_conf(other):.3f}")
                suppressed.add(j)
    
    return filtered


class DetectionAggregator:
    """
    Aggregate 2D detections across slices to 3D nodule locations.
    
    Strategy:
    1. For each slice with detections, store bbox center + confidence
    2. Link detections across adjacent slices (spatial proximity)
    3. Estimate 3D center as average of linked centers
    4. Estimate nodule size from bbox dimensions and z-extent
    """
    
    @staticmethod
    def aggregate_slice_detections(
        slice_detections: List[List[Dict]],
        voxel_spacing_zyx: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        min_slices_for_nodule: int = 1,
        max_xy_distance_voxels: float = 30.0,
    ) -> List[Dict]:
        """
        Aggregate detections from multiple slices into 3D nodules.
        
        Args:
            slice_detections: List of detection lists, one per slice
                Each detection: {'bbox': [x1,y1,x2,y2], 'confidence': float, 'slice': int}
            voxel_spacing_zyx: (z, y, x) spacing in mm
            min_slices_for_nodule: Minimum slices to form a nodule
            max_xy_distance_voxels: Max xy distance to link detections
        
        Returns:
            List of 3D nodule detections: 
                {'center': (z,y,x), 'confidence': float, 'size_mm': float, 'num_slices': int}
        """
        
        # Convert to list of (z, center_y, center_x, conf, bbox) tuples
        all_detections = []
        for z_idx, slice_dets in enumerate(slice_detections):
            logger.debug(f"Slice {z_idx}: {len(slice_dets)} detections")
            for det in slice_dets:
                x1, y1, x2, y2 = det['bbox']
                cy = (y1 + y2) / 2.0
                cx = (x1 + x2) / 2.0
                conf = _conf(det)
                size_y = y2 - y1
                size_x = x2 - x1
                
                all_detections.append({
                    'z': z_idx,
                    'center': (z_idx, cy, cx),
                    'size_xy': (size_y, size_x),
                    'confidence': conf,
                    'bbox': det['bbox'],  # Keep bbox for deduplication
                })
        
        logger.info(f"Total 2D detections before dedup: {len(all_detections)}")
        
        if not all_detections:
            return []
        
        # === CRITICAL: Remove duplicates ===
        all_detections = remove_duplicate_detections(all_detections, iou_threshold=0.5)
        logger.info(f"Total 2D detections after dedup: {len(all_detections)}")
        
        # Link detections across slices using greedy matching
        nodules = []
        used = set()
        
        for i, det in enumerate(all_detections):
            if i in used:
                continue
            
            # Start a new nodule with this detection
            nodule_dets = [det]
            used.add(i)
            current_z = det['z']
            
            # Look forward for nearby detections in next slices
            for j in range(i + 1, len(all_detections)):
                if j in used:
                    continue
                
                other = all_detections[j]
                if other['z'] - current_z > 2:  # Gap too large, stop linking
                    break
                
                # Check xy distance
                cy_last = nodule_dets[-1]['center'][1]
                cx_last = nodule_dets[-1]['center'][2]
                cy_curr = other['center'][1]
                cx_curr = other['center'][2]
                
                xy_dist = np.sqrt((cy_curr - cy_last) ** 2 + (cx_curr - cx_last) ** 2)
                
                if xy_dist < max_xy_distance_voxels:
                    nodule_dets.append(other)
                    used.add(j)
                    current_z = other['z']
            
            # Only include if spans enough slices or has high confidence
            if len(nodule_dets) >= min_slices_for_nodule:
                # Compute 3D center
                centers = np.array([d['center'] for d in nodule_dets])
                avg_center = tuple(centers.mean(axis=0))
                
                # Average confidence
                avg_conf = np.mean([_conf(d) for d in nodule_dets])
                
                # Estimate size
                z_extent = nodule_dets[-1]['z'] - nodule_dets[0]['z'] + 1
                avg_size_xy = np.mean([d['size_xy'] for d in nodule_dets])
                
                # Equivalent diameter (voxels)
                equiv_diam_voxels = np.sqrt(avg_size_xy * z_extent)
                equiv_diam_mm = equiv_diam_voxels * voxel_spacing_zyx[1]  # Use y-spacing as reference
                
                nodules.append({
                    'center': avg_center,
                    'confidence': float(avg_conf),
                    'size_mm': float(max(equiv_diam_mm, 3.0)),  # At least 3mm
                    'num_slices': len(nodule_dets),
                    'z_range': (nodule_dets[0]['z'], nodule_dets[-1]['z']),
                })
        
        logger.info(f"Aggregated {len(all_detections)} 2D detections into {len(nodules)} 3D nodules")
        return nodules
    
    @staticmethod
    def filter_by_confidence(
        nodules: List[Dict],
        confidence_threshold: float = 0.5,
    ) -> List[Dict]:
        """Filter nodules by confidence."""
        return [n for n in nodules if n['confidence'] >= confidence_threshold]
    
    @staticmethod
    def nms_3d(
        nodules: List[Dict],
        iou_threshold: float = 0.3,
    ) -> List[Dict]:
        """
        Non-maximum suppression in 3D using center distance.
        
        Args:
            nodules: List of 3D nodule detections
            iou_threshold: Not used here; using distance-based NMS instead
        
        Returns:
            Filtered nodule list
        """
        if not nodules:
            return []
        
        # Sort by confidence descending
        sorted_nodules = sorted(nodules, key=lambda x: x['confidence'], reverse=True)
        
        kept = []
        suppressed = set()
        
        for i, nodule in enumerate(sorted_nodules):
            if i in suppressed:
                continue
            
            kept.append(nodule)
            
            # Suppress lower-confidence nearby detections
            center_i = np.array(nodule['center'])
            
            for j in range(i + 1, len(sorted_nodules)):
                if j in suppressed:
                    continue
                
                other = sorted_nodules[j]
                center_j = np.array(other['center'])
                
                # 3D distance
                dist = np.linalg.norm(center_i - center_j)
                
                # Suppress if within 50 voxels (rough threshold)
                if dist < 50.0:
                    suppressed.add(j)
        
        return kept


__all__ = ['DetectionAggregator']
