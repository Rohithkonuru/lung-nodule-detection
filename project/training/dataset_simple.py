"""
LUNA16 Dataset Loader - Simple & Fast Version
Loads CT scans and extracts real nodule bounding boxes from annotations.csv
"""

import os
import pandas as pd
import torch
import SimpleITK as sitk
from torch.utils.data import Dataset
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LUNADataset(Dataset):
    """
    LUNA16 Dataset for lung nodule detection.
    Loads slices with real bounding box annotations.
    """
    
    def __init__(self, data_dir, annotations_file, subset=None):
        """
        Args:
            data_dir: Path to LUNA16 data directory (contains subset0, subset1, etc.)
            annotations_file: Path to annotations.csv
            subset: Optional subset ID (0-9) to load specific subset only
        """
        self.data_dir = Path(data_dir)
        self.annotations_file = Path(annotations_file)
        self.subset = subset
        
        # Load annotations
        if not self.annotations_file.exists():
            raise FileNotFoundError(f"Annotations file not found: {annotations_file}")
        
        self.annotations = pd.read_csv(annotations_file)
        self.series_ids = sorted(self.annotations['seriesuid'].unique().tolist())
        
        # Filter by subset if specified
        if subset is not None:
            subset_str = f"subset{subset}"
            self.series_ids = [
                sid for sid in self.series_ids 
                if self._find_mhd_path(sid) and subset_str in str(self._find_mhd_path(sid))
            ]
        
        logger.info(f"✓ Loaded {len(self.series_ids)} series from LUNA16")
    
    def __len__(self):
        return len(self.series_ids)
    
    def __getitem__(self, idx):
        """
        Returns:
            image: Tensor[1, H, W] - single CT slice
            target: dict with 'boxes' [N, 4] and 'labels' [N]
        """
        series_id = self.series_ids[idx]
        
        # Load CT volume
        mhd_path = self._find_mhd_path(series_id)
        img = sitk.ReadImage(mhd_path)
        vol = sitk.GetArrayFromImage(img)
        spacing = img.GetSpacing()  # (X, Y, Z)
        
        # Use middle slice
        z = vol.shape[0] // 2
        slice_img = vol[z].astype(np.float32)
        
        # Normalize to [0, 255]
        slice_min = np.min(slice_img)
        slice_max = np.max(slice_img)
        if slice_max > slice_min:
            slice_img = (slice_img - slice_min) / (slice_max - slice_min) * 255
        else:
            slice_img = np.ones_like(slice_img) * 128
        
        slice_img = slice_img.astype(np.uint8)
        
        # Convert to tensor
        img_tensor = torch.tensor(slice_img, dtype=torch.float32).unsqueeze(0)
        
        # Get bounding boxes for this slice
        boxes, labels = self._get_bounding_boxes(series_id, z, spacing)
        
        # Create target dict
        target = {
            "boxes": torch.tensor(boxes, dtype=torch.float32),
            "labels": torch.tensor(labels, dtype=torch.int64),
        }
        
        return img_tensor, target
    
    def _find_mhd_path(self, series_id):
        """Find MHD file for a given series ID."""
        # Speed up: cache results
        if not hasattr(self, '_mhd_cache'):
            self._mhd_cache = {}
        
        if series_id in self._mhd_cache:
            return self._mhd_cache[series_id]
        
        # Search in subsets
        for subset_dir in sorted(self.data_dir.glob("subset*")):
            if not subset_dir.is_dir():
                continue
            for mhd_file in subset_dir.glob(f"{series_id}*.mhd"):
                result = str(mhd_file)
                self._mhd_cache[series_id] = result
                return result
        
        self._mhd_cache[series_id] = None
        return None
    
    def _get_bounding_boxes(self, series_id, slice_idx, spacing):
        """
        Extract bounding boxes for nodules on a specific slice.
        
        Args:
            series_id: Series UID
            slice_idx: Z-index of slice
            spacing: image spacing (X, Y, Z) in mm
        
        Returns:
            boxes: [N, 4] array of [x1, y1, x2, y2]
            labels: [N] array of class labels (all 1 for nodule)
        """
        boxes = []
        labels = []
        
        # Get annotations for this series
        series_annot = self.annotations[self.annotations['seriesuid'] == series_id]
        if len(series_annot) == 0:
            return np.array([], dtype=np.float32).reshape(0, 4), np.array([], dtype=np.int64)
        
        # Convert spacing from (X, Y, Z) to mm_per_pixel
        spacing_x = spacing[0]  # X spacing
        spacing_y = spacing[1]  # Y spacing
        spacing_z = spacing[2]  # Z spacing
        
        # Extract nodules on this slice
        for _, row in series_annot.iterrows():
            x_mm = float(row['coordX'])
            y_mm = float(row['coordY'])
            z_mm = float(row['coordZ'])
            diameter_mm = float(row['diameter_mm'])
            
            # Convert world coords (mm) to pixel coords
            x_pixel = x_mm / spacing_x
            y_pixel = y_mm / spacing_y
            z_pixel = z_mm / spacing_z
            radius_pixel = diameter_mm / (2 * spacing_y)
            
            # Check if nodule is on this slice (within ±2 slices tolerance)
            if abs(int(z_pixel) - slice_idx) <= 2:
                x1 = max(0, x_pixel - radius_pixel)
                y1 = max(0, y_pixel - radius_pixel)
                x2 = x_pixel + radius_pixel
                y2 = y_pixel + radius_pixel
                
                if x2 > x1 and y2 > y1:
                    boxes.append([x1, y1, x2, y2])
                    labels.append(1)
        
        if len(boxes) == 0:
            return np.array([], dtype=np.float32).reshape(0, 4), np.array([], dtype=np.int64)
        
        return np.array(boxes, dtype=np.float32), np.array(labels, dtype=np.int64)


def get_luna_dataloader(data_dir, annotations_file, batch_size=2, shuffle=True, 
                        num_workers=0, subset=None):
    """Create DataLoader for LUNA16."""
    from torch.utils.data import DataLoader
    
    dataset = LUNADataset(data_dir, annotations_file, subset=subset)
    
    def collate_fn(batch):
        """Collate function for detection - keeps batching flexible."""
        images = []
        targets = []
        for img, target in batch:
            images.append(img)
            targets.append(target)
        return images, targets
    
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        collate_fn=collate_fn,
    )


__all__ = ['LUNADataset', 'get_luna_dataloader']
