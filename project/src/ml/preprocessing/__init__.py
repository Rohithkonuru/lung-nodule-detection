"""
Production-grade medical image preprocessing pipeline.

Handles:
- HU (Hounsfield Unit) normalization
- Lung segmentation
- Isotropic resampling (1mm spacing)
- Padding/cropping
"""

import numpy as np
import SimpleITK as sitk
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class LungPreprocessor:
    """Production preprocessing for lung CT scans."""
    
    # Standard preprocessing constants
    TARGET_SPACING = (1.0, 1.0, 1.0)  # 1mm isotropic
    HU_MIN = -1024  # Air threshold
    HU_MAX = 400    # Soft tissue threshold
    LUNG_WINDOW_MIN = -1024
    LUNG_WINDOW_MAX = 400
    
    def __init__(self):
        """Initialize preprocessor."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def normalize_hu(self, image: sitk.Image) -> sitk.Image:
        """
        Normalize HU values to standard range for lung detection.
        
        Clips to lung window [-1024, 400] HU for optimal contrast.
        Then rescales to [0, 1] for model input.
        """
        try:
            # Get image array
            array = sitk.GetArrayFromImage(image)

            # PNG/JPG inputs may be multi-component (e.g., RGB). Convert to single channel.
            if image.GetDimension() == 2 and image.GetNumberOfComponentsPerPixel() > 1 and array.ndim == 3:
                array = np.mean(array, axis=-1)

            array = array.astype(np.float32)
            
            # Clip to lung window
            clipped = np.clip(array, self.LUNG_WINDOW_MIN, self.LUNG_WINDOW_MAX)
            
            # Normalize to [0, 1]
            normalized = (clipped - self.LUNG_WINDOW_MIN) / (self.LUNG_WINDOW_MAX - self.LUNG_WINDOW_MIN)
            
            # Create new image
            output = sitk.GetImageFromArray(normalized)
            if output.GetDimension() == image.GetDimension():
                output.CopyInformation(image)
            else:
                spacing = image.GetSpacing()
                output.SetSpacing(tuple(float(v) for v in spacing[: output.GetDimension()]))
            
            self.logger.debug(f"HU normalization: min={normalized.min():.2f}, max={normalized.max():.2f}")
            return output
            
        except Exception as e:
            self.logger.error(f"HU normalization failed: {str(e)}")
            raise
    
    def resample_to_spacing(self, image: sitk.Image, 
                           target_spacing: Tuple[float, float, float] = None) -> sitk.Image:
        """
        Resample image to isotropic spacing (default 1mm).
        
        Critical for consistent model input and proper spatial analysis.
        """
        if target_spacing is None:
            target_spacing = self.TARGET_SPACING

        if image.GetDimension() != 3:
            self.logger.warning(
                "Received %sD image for preprocessing; skipping isotropic 3D resampling.",
                image.GetDimension(),
            )
            return image
        
        try:
            original_spacing = image.GetSpacing()
            original_size = image.GetSize()
            
            # Calculate new size
            new_size = tuple(int(original_spacing[i] / target_spacing[i] * original_size[i]) 
                           for i in range(3))
            
            # Use linear interpolation for speed, B-spline for quality
            interpolator = sitk.sitkLinear
            
            resampler = sitk.ResampleImageFilter()
            resampler.SetInterpolator(interpolator)
            resampler.SetOutputSpacing(target_spacing)
            resampler.SetSize(new_size)
            resampler.SetOutputOrigin(image.GetOrigin())
            resampler.SetOutputDirection(image.GetDirection())
            
            # Set default pixel value for areas outside image
            resampler.SetDefaultPixelValue(-1024)
            
            resampled = resampler.Execute(image)
            
            self.logger.debug(f"Resampling: {original_spacing} → {target_spacing}, "
                            f"size: {original_size} → {new_size}")
            return resampled
            
        except Exception as e:
            self.logger.error(f"Resampling failed: {str(e)}")
            raise
    
    def lung_segmentation(self, image: sitk.Image, threshold: int = -400) -> sitk.Image:
        """
        Segment lungs using simple thresholding + connected components.
        
        Helps focus detection on lung tissue only, reducing false positives.
        """
        try:
            if image.GetDimension() != 3:
                self.logger.debug(
                    "Skipping lung segmentation for %sD image; returning original image.",
                    image.GetDimension(),
                )
                return image

            arr = sitk.GetArrayFromImage(image)
            min_v = float(np.min(arr))
            max_v = float(np.max(arr))

            # If image is already normalized to [0, 1], convert HU threshold range.
            if min_v >= 0.0 and max_v <= 1.5:
                lower_thr = 0.0
                upper_thr = (threshold - self.LUNG_WINDOW_MIN) / (self.LUNG_WINDOW_MAX - self.LUNG_WINDOW_MIN)
                upper_thr = float(np.clip(upper_thr, 0.0, 1.0))
            else:
                lower_thr = float(self.LUNG_WINDOW_MIN)
                upper_thr = float(threshold)

            # Binary threshold (lungs are darker)
            binary = sitk.BinaryThreshold(
                image,
                lowerThreshold=lower_thr,
                upperThreshold=upper_thr,
                insideValue=1,
                outsideValue=0,
            )
            
            # Connected component labeling
            cc = sitk.ConnectedComponentImageFilter()
            labeled = cc.Execute(binary)
            
            # Get the largest component (main lung regions)
            relabel = sitk.RelabelComponentImageFilter()
            relabel.SetMinimumObjectSize(1000)  # Remove small artifacts
            relabeled = relabel.Execute(labeled)
            
            # Keep only the two main lung regions
            mask = sitk.BinaryThreshold(relabeled, lowerThreshold=1, upperThreshold=2, 
                                       insideValue=1, outsideValue=0)
            
            # Apply mask to original image
            masked = sitk.Mask(image, mask)

            masked_arr = sitk.GetArrayFromImage(masked)
            if float(np.sum(np.abs(masked_arr))) == 0.0:
                self.logger.warning("Lung segmentation produced empty mask; returning unmasked image")
                return image
            
            self.logger.debug("Lung segmentation completed")
            return masked
            
        except Exception as e:
            self.logger.warning(f"Lung segmentation failed (non-critical): {str(e)}")
            return image  # Return original if segmentation fails
    
    def preprocess(self, image: sitk.Image, apply_segmentation: bool = True) -> sitk.Image:
        """
        Complete preprocessing pipeline.
        
        Steps:
        1. HU normalization
        2. Resampling to 1mm isotropic
        3. Lung segmentation (optional)
        """
        try:
            self.logger.info("Starting preprocessing...")
            
            # Step 1: HU normalization
            normalized = self.normalize_hu(image)
            
            # Step 2: Resample to 1mm
            resampled = self.resample_to_spacing(normalized)
            
            # Step 3: Lung segmentation
            if apply_segmentation:
                segmented = self.lung_segmentation(resampled)
                result = segmented
            else:
                result = resampled
            
            self.logger.info("Preprocessing completed successfully")
            return result
            
        except Exception as e:
            self.logger.error(f"Preprocessing failed: {str(e)}")
            raise
    
    def get_image_stats(self, image: sitk.Image) -> dict:
        """Get image statistics for logging/debugging."""
        array = sitk.GetArrayFromImage(image)
        return {
            'shape': array.shape,
            'spacing': image.GetSpacing(),
            'dtype': array.dtype,
            'min': float(array.min()),
            'max': float(array.max()),
            'mean': float(array.mean()),
            'std': float(array.std()),
        }


# Initialize global preprocessor
_preprocessor = None


def get_preprocessor() -> LungPreprocessor:
    """Get singleton preprocessor instance."""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = LungPreprocessor()
    return _preprocessor


def preprocess_scan(image_path: str, apply_segmentation: bool = True) -> np.ndarray:
    """
    Load and preprocess a CT scan image.
    
    Args:
        image_path: Path to .nii, .nii.gz, or .mhd file
        apply_segmentation: Whether to apply lung segmentation
    
    Returns:
        Preprocessed image as numpy array
    """
    try:
        # Load image
        image = sitk.ReadImage(image_path)
        preprocessor = get_preprocessor()
        
        # Preprocess
        processed = preprocessor.preprocess(image, apply_segmentation)
        
        # Convert to numpy
        array = sitk.GetArrayFromImage(processed)
        
        # Log stats
        stats = preprocessor.get_image_stats(processed)
        logger.info(f"Preprocessing complete. Stats: {stats}")
        
        return array
        
    except Exception as e:
        logger.error(f"Failed to preprocess {image_path}: {str(e)}")
        raise


__all__ = ['LungPreprocessor', 'get_preprocessor', 'preprocess_scan']
