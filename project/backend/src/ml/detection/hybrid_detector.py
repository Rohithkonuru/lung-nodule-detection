"""
Hybrid 3D + 2D detection pipeline.
Combines 3D preprocessing with 2D RetinaNet slice detection.

Pipeline:
1. Load and preprocess 3D CT volume
2. Extract 2D slices
3. Run 2D RetinaNet on each slice
4. Aggregate detections back to 3D
5. Return 3D nodule locations
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class Hybrid3D2DDetector:
    """
    Hybrid detector combining 3D preprocessing with 2D RetinaNet detection.
    """
    
    def __init__(self, retinanet_model_path: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize hybrid detector.
        
        Args:
            retinanet_model_path: Path to fine-tuned RetinaNet checkpoint
            device: 'cuda' or 'cpu'
        """
        from .retinanet_2d import RetinaNet2DDetector
        from .aggregator_3d import DetectionAggregator
        
        self.device = device or ('cuda' if __import__('torch').cuda.is_available() else 'cpu')
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self.detector_2d = RetinaNet2DDetector(model_path=retinanet_model_path, device=self.device)
        self.aggregator = DetectionAggregator()
        
        self.logger.info("Hybrid 3D+2D detector initialized")
    
    def detect(
        self,
        volume: np.ndarray,
        voxel_spacing_zyx: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        confidence_threshold: float = 0.04,
        sample_every_n_slices: int = 1,
        disable_filters: bool = False,
        debug_mid_conf_only: bool = False,
        use_lung_mask: bool = False,
        use_size_filter: bool = False,
        use_roi_filter: bool = False,
        min_size_px: int = 5,
        max_size_px: int = 40,
        roi_min_ratio: float = 0.1,
        roi_max_ratio: float = 0.9,
        nms_iou_threshold: float = 0.3,
        post_filter_score_threshold: float = 0.06,
        top_k_detections_per_slice: int = 3,
        debug_print_raw_outputs: bool = True,
        print_debug_counts: bool = True,
        fallback_to_raw_if_empty: bool = True,
        max_raw_fallback_detections: int = 10,
    ) -> List[Dict]:
        """
        Detect nodules using 2D RetinaNet on extracted slices.
        
        Args:
            volume: Preprocessed 3D CT volume (ZxYxX)
            voxel_spacing_zyx: Voxel spacing in mm
            confidence_threshold: Min confidence for detection
            sample_every_n_slices: Process every Nth slice for speed
            disable_filters: If True, skip spatial filters (for diagnostics)
        
        Returns:
            List of 3D detections:
                [{'center': (z,y,x), 'confidence': float, 'size_mm': float, 'num_slices': int}]
        """
        try:
            self.logger.info(f"=== Starting hybrid detection: volume shape {volume.shape} ===")

            if print_debug_counts:
                vol_bytes = np.ascontiguousarray(volume).tobytes()
                print("Volume shape:", tuple(volume.shape))
                print("Volume sum:", float(np.sum(volume)))
                print("VOLUME HASH:", hash(vol_bytes))
                print("VOLUME SHA1:", hashlib.sha1(vol_bytes).hexdigest()[:16])
            
            z_dim, y_dim, x_dim = volume.shape
            
            # Extract slices to process
            slice_indices = list(range(0, z_dim, sample_every_n_slices))
            self.logger.info(f"Processing {len(slice_indices)} slices (sampling every {sample_every_n_slices})")

            if print_debug_counts:
                if len(slice_indices) <= 20:
                    print("Slice indices:", slice_indices)
                else:
                    print("Slice indices (head):", slice_indices[:20], "...")
            
            # Run 2D detection on each slice - FRESH EACH TIME!
            slice_detections = []  # filtered detections
            raw_slice_detections = []
            
            for z_idx_in_list, z_idx in enumerate(slice_indices):
                slice_img = volume[z_idx, :, :].astype(np.float32)

                if print_debug_counts:
                    print(f"Running fresh detection on slice index: {z_idx}")
                
                # Normalize to [0, 1]
                if slice_img.max() > 1.0:
                    slice_img = (slice_img - slice_img.min()) / (slice_img.max() - slice_img.min() + 1e-6)
                
                # Detect on this slice (NOT reusing previous results)
                dets = self.detector_2d.detect(
                    slice_img,
                    confidence_threshold=confidence_threshold,
                    slice_index=z_idx,
                    disable_filters=disable_filters,
                    debug_mid_conf_only=debug_mid_conf_only,
                    use_lung_mask=use_lung_mask,
                    use_size_filter=use_size_filter,
                    use_roi_filter=use_roi_filter,
                    min_size_px=min_size_px,
                    max_size_px=max_size_px,
                    roi_min_ratio=roi_min_ratio,
                    roi_max_ratio=roi_max_ratio,
                    nms_iou_threshold=nms_iou_threshold,
                    post_filter_score_threshold=post_filter_score_threshold,
                    top_k_detections=top_k_detections_per_slice,
                    debug_print_raw_outputs=debug_print_raw_outputs,
                )

                raw_dets = list(self.detector_2d.last_raw_detections)
                raw_slice_detections.append(raw_dets)
                
                self.logger.debug(f"Slice {z_idx}: Received {len(dets)} detections from model")
                
                # Convert xy coordinates to volume coordinates
                for det in dets:
                    det['slice'] = z_idx  # Store actual z-index
                
                slice_detections.append(dets)
            
            filtered_count = sum(len(d) for d in slice_detections)
            raw_count = sum(len(d) for d in raw_slice_detections)
            self.logger.info(f"Raw 2D detections across all slices: {raw_count}")
            self.logger.info(f"Filtered 2D detections across all slices: {filtered_count}")

            if print_debug_counts:
                print(f"RAW DETECTIONS: {raw_count}")
                print(f"FILTERED DETECTIONS: {filtered_count}")
                for sample_slice in raw_slice_detections:
                    if sample_slice:
                        print(f"RAW SAMPLE DET: {sample_slice[0]}")
                        break
            
            # Aggregate 2D detections to 3D
            nodules_3d = self.aggregator.aggregate_slice_detections(
                slice_detections,
                voxel_spacing_zyx=voxel_spacing_zyx,
            )
            
            self.logger.info(f"After 3D aggregation: {len(nodules_3d)} nodules")
            
            # Convert center coordinates to integers
            nodules_3d_int = []
            for nodule in nodules_3d:
                z, y, x = nodule['center']
                conf = float(nodule.get('confidence', nodule.get('score', 0.0)))
                nodules_3d_int.append({
                    'center': (int(round(z)), int(round(y)), int(round(x))),
                    'confidence': conf,
                    'size_mm': nodule['size_mm'],
                    'num_slices': nodule['num_slices'],
                })
            
            # Apply NMS
            nodules_final = self.aggregator.nms_3d(nodules_3d_int, iou_threshold=0.3)

            if print_debug_counts:
                print(f"FINAL DETECTIONS: {len(nodules_final)}")

            # Demo-safe fallback: if grouping suppresses everything, expose top raw detections.
            if fallback_to_raw_if_empty and len(nodules_final) == 0 and raw_count > 0:
                raw_flat = []
                for slice_raw in raw_slice_detections:
                    raw_flat.extend(slice_raw)

                raw_flat.sort(key=lambda d: float(d.get('confidence', d.get('score', 0.0))), reverse=True)
                fallback = []
                for det in raw_flat[:max(1, int(max_raw_fallback_detections))]:
                    x1, y1, x2, y2 = det['bbox']
                    z = int(det.get('slice', 0))
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    size_mm = float(max(x2 - x1, y2 - y1))
                    conf = float(det.get('confidence', det.get('score', 0.0)))
                    fallback.append({
                        'center': (z, cy, cx),
                        'confidence': conf,
                        'size_mm': size_mm,
                        'num_slices': 1,
                        'bbox_zyx': (z, int(y1), int(x1), z, int(y2), int(x2)),
                    })

                if print_debug_counts:
                    print(f"FALLBACK RAW->FINAL DETECTIONS: {len(fallback)}")
                self.logger.warning(
                    "Aggregation produced 0 detections but raw had %d; returning %d raw fallback detections",
                    raw_count,
                    len(fallback),
                )
                nodules_final = fallback
            
            self.logger.info(f"=== Final result: {len(nodules_final)} nodules ===")
            for i, nodule in enumerate(nodules_final):
                self.logger.info(f"  Nodule {i+1}: center={nodule['center']}, conf={nodule['confidence']:.3f}, size={nodule['size_mm']:.1f}mm")
            
            return nodules_final
        
        except Exception as e:
            self.logger.error(f"Detection failed: {str(e)}")
            raise


__all__ = ['Hybrid3D2DDetector']
