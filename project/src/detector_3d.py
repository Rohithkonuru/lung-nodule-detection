"""
3D detection module for handling multi-slice CT scans.

Processes multiple slices and aggregates detections across the 3D volume.
"""

import logging
import numpy as np
from typing import List, Tuple, Dict, Optional
from PIL import Image
from src import infer

logger = logging.getLogger("lung_nodule_3d_detector")


class DetectionResult3D:
    """Represents a 3D detection across multiple slices."""
    
    def __init__(self, x1: float, y1: float, x2: float, y2: float, 
                 slice_idx: int, confidence: float, volume: Optional[np.ndarray] = None):
        """
        Args:
            x1, y1, x2, y2: 2D bounding box coordinates
            slice_idx: Slice index where detection occurs
            confidence: Detection confidence score
            volume: Optional 3D volume for size calculation
        """
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.slice_idx = slice_idx
        self.confidence = confidence
        self.volume = volume
        self._compute_size()
    
    def _compute_size(self):
        """Compute nodule size in pixels."""
        self.width = self.x2 - self.x1
        self.height = self.y2 - self.y1
        self.area = self.width * self.height
        # Approximate diameter (assuming circular)
        self.diameter_px = np.sqrt(self.area / np.pi) * 2
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "x1": float(self.x1),
            "y1": float(self.y1),
            "x2": float(self.x2),
            "y2": float(self.y2),
            "slice": int(self.slice_idx),
            "confidence": float(self.confidence),
            "width": float(self.width),
            "height": float(self.height),
            "diameter_px": float(self.diameter_px),
            "area": float(self.area),
        }
    
    def __repr__(self) -> str:
        return f"<Det3D slice={self.slice_idx} conf={self.confidence:.3f} size=({self.width:.1f}x{self.height:.1f})>"


def detect_in_volume(
    model,
    ct_volume: np.ndarray,
    conf_thresh: float = 0.3,
    apply_nms: bool = True,
    iou_thresh: float = 0.3,
    sample_rate: int = 1,
) -> List[DetectionResult3D]:
    """
    Detect lung nodules across a 3D CT volume.
    
    Args:
        model: Trained detection model
        ct_volume: 3D numpy array (slices, height, width) with values in range [0, 1]
        conf_thresh: Confidence threshold for detections
        apply_nms: Whether to apply NMS within each slice
        iou_thresh: IoU threshold for NMS
        sample_rate: Process every Nth slice (1=all slices, 2=every other, etc.)
        
    Returns:
        List of DetectionResult3D objects
    """
    logger.info(f"Starting 3D detection on volume shape {ct_volume.shape}, sample_rate={sample_rate}")
    
    detections_3d = []
    total_slices = ct_volume.shape[0]
    processed_slices = 0
    
    # Process slices
    for slice_idx in range(0, total_slices, sample_rate):
        slice_data = ct_volume[slice_idx]
        
        # Convert to PIL Image for detection
        slice_pil = _array_to_pil(slice_data)
        
        # Detect in this slice
        slice_boxes = infer.detect_boxes_with_options(
            model, slice_pil,
            conf_thresh=conf_thresh,
            apply_nms=apply_nms,
            iou_thresh=iou_thresh
        )
        
        # Convert to 3D detections
        for box in slice_boxes:
            det_3d = DetectionResult3D(
                x1=box[0],
                y1=box[1],
                x2=box[2],
                y2=box[3],
                slice_idx=slice_idx,
                confidence=box[4] if len(box) >= 5 else 0.5,
                volume=ct_volume
            )
            detections_3d.append(det_3d)
            logger.debug(f"Slice {slice_idx}: {det_3d}")
        
        processed_slices += 1
        if processed_slices % max(1, total_slices // 10) == 0:
            logger.info(f"Processed {processed_slices}/{total_slices} slices, {len(detections_3d)} detections so far")
    
    logger.info(f"Finished 3D detection: {len(detections_3d)} detections across {processed_slices} slices")
    
    return detections_3d


def aggregate_detections(
    detections: List[DetectionResult3D],
    spatial_merge_threshold: float = 25.0,
    confidence_weight: float = 0.7,
) -> List[Dict]:
    """
    Merge detections across adjacent slices into unified detections.
    
    Args:
        detections: List of 3D detections
        spatial_merge_threshold: Maximum distance in pixels for merging
        confidence_weight: How to weight confidence across slices
        
    Returns:
        List of aggregated detection dictionaries
    """
    if not detections:
        return []
    
    logger.info(f"Aggregating {len(detections)} detections...")
    
    # Sort by slice
    detections_sorted = sorted(detections, key=lambda d: d.slice_idx)
    
    merged = []
    used = set()
    
    for i, det1 in enumerate(detections_sorted):
        if i in used:
            continue
        
        # Start a new cluster
        cluster = [det1]
        used.add(i)
        
        # Find nearby detections in adjacent slices
        for j, det2 in enumerate(detections_sorted[i+1:], start=i+1):
            if j in used:
                continue
            
            # Check if adjacent in slice index
            if det2.slice_idx - cluster[-1].slice_idx > 3:
                break  # Too far in slice direction
            
            # Check spatial overlap
            iou = _compute_2d_iou(cluster[-1], det2)
            if iou > 0.1 or _compute_centroid_distance(cluster[-1], det2) < spatial_merge_threshold:
                cluster.append(det2)
                used.add(j)
        
        # Aggregate cluster
        if cluster:
            agg_det = _aggregate_cluster(cluster, confidence_weight)
            merged.append(agg_det)
            logger.debug(f"Merged cluster of {len(cluster)} detections: {agg_det}")
    
    logger.info(f"Aggregated to {len(merged)} detections")
    return merged


def _array_to_pil(array: np.ndarray, size: int = 256) -> Image.Image:
    """Convert float32 numpy array to PIL Image for inference."""
    # Ensure range [0, 1]
    array = np.clip(array, 0.0, 1.0)
    
    # Convert to uint8
    array_uint8 = (array * 255).astype(np.uint8)
    
    # Create PIL Image and resize
    img = Image.fromarray(array_uint8, mode='L')
    img = img.resize((size, size), Image.BILINEAR)
    
    # Convert to RGB for model compatibility
    return img.convert('RGB')


def _compute_2d_iou(det1: DetectionResult3D, det2: DetectionResult3D) -> float:
    """Compute 2D intersection over union."""
    x1_inter = max(det1.x1, det2.x1)
    y1_inter = max(det1.y1, det2.y1)
    x2_inter = min(det1.x2, det2.x2)
    y2_inter = min(det1.y2, det2.y2)
    
    if x2_inter < x1_inter or y2_inter < y1_inter:
        return 0.0
    
    inter_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
    union_area = det1.area + det2.area - inter_area
    
    return inter_area / (union_area + 1e-8)


def _compute_centroid_distance(det1: DetectionResult3D, det2: DetectionResult3D) -> float:
    """Compute 2D centroid distance."""
    cx1 = (det1.x1 + det1.x2) / 2
    cy1 = (det1.y1 + det1.y2) / 2
    cx2 = (det2.x1 + det2.x2) / 2
    cy2 = (det2.y1 + det2.y2) / 2
    
    return np.sqrt((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2)


def _aggregate_cluster(cluster: List[DetectionResult3D], confidence_weight: float) -> Dict:
    """Aggregate a cluster of detections into a single detection."""
    slices = [d.slice_idx for d in cluster]
    confidences = [d.confidence for d in cluster]
    
    # Use weighted average confidence
    avg_confidence = np.mean(confidences)
    max_confidence = max(confidences)
    weighted_confidence = confidence_weight * avg_confidence + (1 - confidence_weight) * max_confidence
    
    # Average bounding box coordinates
    avg_x1 = np.mean([d.x1 for d in cluster])
    avg_y1 = np.mean([d.y1 for d in cluster])
    avg_x2 = np.mean([d.x2 for d in cluster])
    avg_y2 = np.mean([d.y2 for d in cluster])
    
    return {
        "x1": float(avg_x1),
        "y1": float(avg_y1),
        "x2": float(avg_x2),
        "y2": float(avg_y2),
        "confidence": float(weighted_confidence),
        "slice_start": int(min(slices)),
        "slice_end": int(max(slices)),
        "slice_center": int(np.mean(slices)),
        "num_slices": int(len(cluster)),
        "avg_confidence_per_slice": float(np.mean(confidences)),
        "max_confidence": float(max_confidence),
        "slices": [int(s) for s in slices],
    }
