"""
Production ML pipeline: Preprocessing → Detection → Post-processing.

Orchestrates the complete lung nodule detection workflow.
"""

import logging
import os
from typing import List, Dict, Optional, Tuple
import numpy as np
import SimpleITK as sitk

from .preprocessing import get_preprocessor
from .detection import get_detector
from .postprocessing import get_postprocessor

logger = logging.getLogger(__name__)


def _spacing_to_zyx(spacing_xyz: Tuple[float, ...]) -> Tuple[float, float, float]:
    if len(spacing_xyz) >= 3:
        return (
            float(spacing_xyz[2]),
            float(spacing_xyz[1]),
            float(spacing_xyz[0]),
        )

    if len(spacing_xyz) == 2:
        # Promote 2D spacing to pseudo-3D for downstream coordinate conversions.
        return (1.0, float(spacing_xyz[1]), float(spacing_xyz[0]))

    return (1.0, 1.0, 1.0)


class LungNoduleDetectionPipeline:
    """
    Production-grade lung nodule detection pipeline.
    
    Complete workflow:
    1. Load CT scan (NIFTI, MHD, or DICOM)
    2. Preprocess (HU normalization, resampling, segmentation)
    3. Detect nodules (3D CNN)
    4. Post-process (NMS, filtering)
    5. Return structured results
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize pipeline.
        
        Args:
            model_path: Path to trained model weights
        """
        self.preprocessor = get_preprocessor()
        self.detector = get_detector(model_path)
        self.postprocessor = get_postprocessor()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def run(self, image_path: str, 
            confidence_threshold: float = 0.5,
            min_size_mm: float = 3.0,
            apply_segmentation: bool = True,
            stride: int = 32,
            iou_threshold: float = 0.3) -> Dict:
        """
        Run complete detection pipeline on a CT scan.
        
        Args:
            image_path: Path to CT scan file (.nii, .mhd, etc.)
            confidence_threshold: Minimum confidence for detection
            min_size_mm: Minimum nodule size to report
            apply_segmentation: Whether to apply lung segmentation
        
        Returns:
            Dictionary with:
            - detections: List of nodule detections
            - metadata: Image information
            - runtime_stats: Processing time, etc.
        """
        try:
            import time
            start_time = time.time()
            
            self.logger.info(f"Starting pipeline: {image_path}")
            
            # Step 1: Load image
            self.logger.info("Step 1/4: Loading image...")
            image = sitk.ReadImage(image_path)
            original_spacing_xyz = image.GetSpacing()
            original_spacing_zyx = _spacing_to_zyx(original_spacing_xyz)
            original_size = image.GetSize()
            self.logger.info(f"  Original spacing (xyz): {original_spacing_xyz}, size: {original_size}")
            
            # Step 2: Preprocess
            self.logger.info("Step 2/4: Preprocessing...")
            processed = self.preprocessor.preprocess(image, apply_segmentation)
            processed_array = sitk.GetArrayFromImage(processed)
            if processed_array.ndim == 2:
                processed_array = np.expand_dims(processed_array, axis=0)
            self.logger.info(f"  Processed shape: {processed_array.shape}")
            
            # Step 3: Detect
            self.logger.info("Step 3/4: Detecting nodules...")
            raw_detections = self.detector.detect(
                processed_array,
                stride=stride,
                confidence_threshold=max(confidence_threshold - 0.15, 0.05),
                voxel_spacing_zyx=(1.0, 1.0, 1.0),
            )
            self.logger.info(f"  Raw detections: {len(raw_detections)}")
            
            # Step 4: Post-process
            self.logger.info("Step 4/4: Post-processing...")
            final_detections = self.postprocessor.postprocess(
                raw_detections,
                confidence_threshold=confidence_threshold,
                min_size_mm=min_size_mm,
                iou_threshold=iou_threshold,
            )
            self.logger.info(f"  Final detections: {len(final_detections)}")
            
            # Convert coordinates back to original spacing
            detections_original_space = self._convert_coordinates(
                final_detections, 
                (1.0, 1.0, 1.0),  # Preprocessed spacing
                original_spacing_zyx
            )
            
            # Runtime
            runtime = time.time() - start_time
            
            result = {
                'success': True,
                'detections': detections_original_space,
                'num_detections': len(detections_original_space),
                'metadata': {
                    'image_path': image_path,
                    'original_spacing_xyz': original_spacing_xyz,
                    'original_size': original_size,
                    'confidence_threshold': confidence_threshold,
                    'min_size_mm': min_size_mm,
                    'stride': stride,
                    'iou_threshold': iou_threshold,
                },
                'runtime': runtime,
                'raw_detections_count': len(raw_detections),
            }
            
            self.logger.info(f"Pipeline complete in {runtime:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'detections': [],
            }
    
    @staticmethod
    def _convert_coordinates(detections: List[Dict],
                            from_spacing: Tuple[float, float, float],
                            to_spacing: Tuple[float, float, float]) -> List[Dict]:
        """Convert detection coordinates between different spacings."""
        scale_factors = (
            from_spacing[0] / max(to_spacing[0], 1e-6),
            from_spacing[1] / max(to_spacing[1], 1e-6),
            from_spacing[2] / max(to_spacing[2], 1e-6),
        )
        
        converted = []
        for det in detections:
            z, y, x = det['center']
            new_z = int(z * scale_factors[0])
            new_y = int(y * scale_factors[1])
            new_x = int(x * scale_factors[2])

            bbox = det.get('bbox_zyx')
            converted_bbox = None
            if bbox and len(bbox) == 6:
                bz1, by1, bx1, bz2, by2, bx2 = bbox
                converted_bbox = (
                    int(bz1 * scale_factors[0]),
                    int(by1 * scale_factors[1]),
                    int(bx1 * scale_factors[2]),
                    int(bz2 * scale_factors[0]),
                    int(by2 * scale_factors[1]),
                    int(bx2 * scale_factors[2]),
                )
            
            converted.append({
                **det,
                'center': (new_z, new_y, new_x),
                'center_mm': (new_z * to_spacing[0], new_y * to_spacing[1], new_x * to_spacing[2]),
                'bbox_zyx': converted_bbox,
            })
        
        return converted
    
    def get_statistics(self) -> Dict:
        """Return pipeline statistics for monitoring."""
        return {
            'detector_device': self.detector.device,
            'batch_enabled': True,
            'has_gpu': 'cuda' in self.detector.device,
        }


# Global pipeline instance
_pipeline = None
_pipeline_model_path = None


def get_pipeline(model_path: Optional[str] = None) -> LungNoduleDetectionPipeline:
    """Get singleton pipeline instance."""
    global _pipeline, _pipeline_model_path
    resolved_model_path = model_path or os.environ.get("MODEL_WEIGHTS_PATH")
    if not resolved_model_path:
        raise ValueError("MODEL_WEIGHTS_PATH is required for inference.")

    if _pipeline is None:
        _pipeline = LungNoduleDetectionPipeline(resolved_model_path)
        _pipeline_model_path = resolved_model_path
    elif _pipeline_model_path != resolved_model_path:
        logger.warning(
            "Pipeline already initialized with a different model path; reusing existing model instance."
        )
    return _pipeline


def run_detection(image_path: str,
                 confidence_threshold: float = 0.5,
                 min_size_mm: float = 3.0,
                 model_path: Optional[str] = None,
                 stride: int = 32,
                 iou_threshold: float = 0.3) -> Dict:
    """
    Simple interface to run detection on a single image.
    
    Args:
        image_path: Path to CT scan
        confidence_threshold: Detection threshold
        min_size_mm: Minimum nodule size
    
    Returns:
        Detection results
    """
    pipeline = get_pipeline(model_path=model_path)
    return pipeline.run(
        image_path,
        confidence_threshold=confidence_threshold,
        min_size_mm=min_size_mm,
        stride=stride,
        iou_threshold=iou_threshold,
    )


__all__ = ['LungNoduleDetectionPipeline', 'get_pipeline', 'run_detection']
