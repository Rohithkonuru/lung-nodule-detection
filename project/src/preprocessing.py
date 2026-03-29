import numpy as np
from PIL import Image
import logging
from typing import Tuple

logger = logging.getLogger("lung_nodule_preprocessing")



def hu_window(slice_or_volume: np.ndarray, level: float = -600.0, width: float = 1600.0) -> np.ndarray:
    """Apply HU windowing to a single slice or a volume.

    Args:
        slice_or_volume: numpy array with CT values in Hounsfield Units (HU).
        level: window center (WL), e.g., -600 for lung window.
        width: window width (WW), e.g., 1600.

    Returns:
        Windowed image(s) scaled to range [0.0, 1.0].
    """
    lower = level - (width / 2.0)
    upper = level + (width / 2.0)
    w = np.clip(slice_or_volume, lower, upper)
    # scale to 0..1
    w = (w - lower) / (upper - lower)
    return w.astype(np.float32)


def standardize(img: np.ndarray, mean: float = 0.5, std: float = 0.25) -> np.ndarray:
    """Standardize image to zero-mean unit-variance using provided stats.

    Defaults are conservative values for windowed CT slices; you can
    compute dataset mean/std and pass them here for better results.
    """
    return (img - mean) / (std + 1e-8)


def resize_slice(slice_img: np.ndarray, size: int = 256) -> np.ndarray:
    """Resize a single slice (float in [0,1]) to `(size,size)` and keep float32 range [0,1]."""
    arr = (np.clip(slice_img, 0.0, 1.0) * 255.0).astype(np.uint8)
    im = Image.fromarray(arr)
    logger.debug(f"Resizing slice to {size}x{size}")
    im = im.resize((size, size), resample=Image.BILINEAR)
    arr2 = np.array(im).astype(np.float32) / 255.0
    return arr2


def segment_lungs_simple(slice_img: np.ndarray, threshold: float = 0.3) -> np.ndarray:
    """
    Simple lung segmentation using threshold.
    
    Args:
        slice_img: Single CT slice (float32, range [0, 1])
        threshold: Threshold for lung tissue
        
    Returns:
        Binary mask (1=lung, 0=background)
    """
    # Lung tissue is typically darker (lower HU values = lower intensity after windowing)
    # We use threshold to distinguish lungs from body
    mask = (slice_img > threshold).astype(np.float32)
    
    # Apply morphological operations to clean up
    try:
        from scipy import ndimage
        mask_binary = ndimage.binary_closing(mask > 0.5, iterations=2)
        mask_binary = ndimage.binary_opening(mask_binary, iterations=1)
        mask = mask_binary.astype(np.float32)
    except Exception as e:
        logger.debug(f"Scipy morphology unavailable, using basic mask: {e}")
    
    return mask


def apply_lung_mask(slice_img: np.ndarray, mask: np.ndarray, 
                   preserve_edges: bool = True) -> np.ndarray:
    """
    Apply lung mask to slice, optionally preserving edge regions.
    
    Args:
        slice_img: CT slice
        mask: Binary lung mask
        preserve_edges: If True, keep a border of original image
        
    Returns:
        Masked slice
    """
    result = slice_img * mask
    
    if preserve_edges:
        # Preserve 5 pixel border
        result[:5, :] = slice_img[:5, :]
        result[-5:, :] = slice_img[-5:, :]
        result[:, :5] = slice_img[:, :5]
        result[:, -5:] = slice_img[:, -5:]
    
    return result


def preprocess_scan(scan: np.ndarray, size: int = None, window_level: float = -600.0, window_width: float = 1600.0,
                    mean: float = 0.5, std: float = 0.25, standardize_output: bool = True,
                    apply_lung_seg: bool = False) -> np.ndarray:
    """Full preprocessing pipeline for a CT volume.

    Steps:
    - Apply HU windowing (defaults to lung window)
    - Optionally apply lung segmentation
    - Resize each slice to `size` x `size`
    - Optionally standardize using `mean` and `std`

    Args:
        scan: 3D numpy array (slices, H, W) in HU units.
        size: output spatial size for each slice.
        window_level: HU window center (WL).
        window_width: HU window width (WW).
        mean: mean to use for standardization (after windowing to [0,1]).
        std: std to use for standardization.
        standardize_output: whether to apply standardization.
        apply_lung_seg: whether to apply lung segmentation.

    Returns:
        numpy array of shape (slices, size, size) dtype float32 ready for model input.
    """
    import os
    # HIGH_RES flag from environment or default
    HIGH_RES = bool(os.environ.get('HIGH_RES', False))
    if size is None:
        size = 512 if HIGH_RES else 256
    
    logger.info(f"Preprocessing scan: shape={scan.shape}, size={size}, HIGH_RES={HIGH_RES}, lung_seg={apply_lung_seg}")
    
    processed = []
    
    # Apply windowing to the whole volume for speed/consistency
    windowed = hu_window(scan, level=window_level, width=window_width)
    
    for idx, slice_img in enumerate(windowed):
        # Apply lung segmentation if requested
        if apply_lung_seg:
            mask = segment_lungs_simple(slice_img)
            slice_img = apply_lung_mask(slice_img, mask)
        
        # Resize slice
        slice_resized = resize_slice(slice_img, size=size)
        
        # Standardize if requested
        if standardize_output:
            slice_resized = standardize(slice_resized, mean=mean, std=std)
        
        processed.append(slice_resized)
        
        if (idx + 1) % max(1, len(windowed) // 5) == 0:
            logger.debug(f"Processed {idx + 1}/{len(windowed)} slices")
    
    result = np.array(processed, dtype=np.float32)
    logger.info(f"Preprocessing complete: output shape={result.shape}, dtype={result.dtype}")
    return result


def normalize_hounsfield(scan: np.ndarray, clip_hu: bool = True) -> np.ndarray:
    """
    Normalize Hounsfield units to reasonable range for lung imaging.
    
    Args:
        scan: 3D CT volume in HU
        clip_hu: Whether to clip extreme values
        
    Returns:
        Normalized volume
    """
    scan = scan.astype(np.float32)
    
    if clip_hu:
        # Clip to typical HU range for CT imaging
        # Air: -1000, Water: 0, Fat: -100, Bone: 400+
        # We keep wider range to preserve detail
        scan = np.clip(scan, -1000, 3000)
    
    return scan


def resample_volume(volume: np.ndarray, target_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
                   original_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0)) -> np.ndarray:
    """
    Resample volume to uniform voxel spacing.
    
    Note: This requires scipy.ndimage.zoom. If scipy is unavailable, returns original volume.
    
    Args:
        volume: 3D CT volume
        target_spacing: Target voxel spacing (z, y, x) in mm
        original_spacing: Original voxel spacing (z, y, x) in mm
        
    Returns:
        Resampled volume
    """
    try:
        from scipy import ndimage
        
        # Calculate zoom factors
        zoom_factors = tuple(np.array(original_spacing) / np.array(target_spacing))
        logger.info(f"Resampling with zoom factors: {zoom_factors}")
        
        resampled = ndimage.zoom(volume, zoom_factors, order=1)  # Bilinear interpolation
        logger.info(f"Resampling complete: {volume.shape} -> {resampled.shape}")
        return resampled
        
    except ImportError:
        logger.warning("scipy.ndimage not available, skipping resampling")
        return volume
    except Exception as e:
        logger.error(f"Resampling failed: {e}, returning original volume")
        return volume
