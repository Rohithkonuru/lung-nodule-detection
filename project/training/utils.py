"""
Utility functions for LUNA16 training and evaluation.
"""

import numpy as np
import torch
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def download_luna16():
    """
    Provide instructions for downloading LUNA16 dataset.
    
    LUNA16 requires registration. This function prints the download instructions.
    """
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║           LUNA16 DATASET DOWNLOAD INSTRUCTIONS                 ║
    ╚════════════════════════════════════════════════════════════════╝
    
    1. Visit: https://luna16.grand-challenge.org/
    
    2. Create account and agree to terms
    
    3. Download all subset files:
       - subset0.zip through subset9.zip
       - annotations.csv
    
    4. Extract to: data/LUNA16/
    
       Structure should look like:
       
       data/LUNA16/
       ├── subset0/
       │   ├── 1.3.6.1.4.1.14519.5.2.1.*.mhd
       │   ├── 1.3.6.1.4.1.14519.5.2.1.*.raw
       │   └── ...
       ├── subset1/
       ├── ...
       ├── subset9/
       └── annotations.csv
    
    5. Verify download:
       python -c "from dataset import LUNADataset; ds = LUNADataset('data/LUNA16', 'data/LUNA16/annotations.csv'); print(f'✓ {len(ds)} series loaded')"
    
    6. Start training:
       python train.py --data-dir data/LUNA16 --epochs 20
    
    ╔════════════════════════════════════════════════════════════════╗
    ║                 DATASET SPECIFICATIONS                         ║
    ╚════════════════════════════════════════════════════════════════╝
    
    Name: LUNA16 (Lung Nodule Analysis 16)
    Scans: 888 low-dose CT scans
    Nodules: ~1,200 annotated nodules
    Size: ~100 GB (compressed)
    
    Citation:
    Setio AAA, Traverso A, de Bel T, et al. "Validation, comparison, and 
    combination of algorithms for automatic detection of pulmonary nodules 
    in computed tomography images: the LUNA16 challenge." Medical Image 
    Analysis 2017;42:1-13.
    """)


def check_luna16_installation(data_dir):
    """
    Check if LUNA16 is properly installed.
    
    Args:
        data_dir: Path to LUNA16 directory
    
    Returns:
        bool: True if dataset is properly installed
    """
    data_path = Path(data_dir)
    
    # Check if directory exists
    if not data_path.exists():
        logger.error(f"Data directory not found: {data_dir}")
        return False
    
    # Check for annotations
    annotations_path = data_path / 'annotations.csv'
    if not annotations_path.exists():
        logger.error(f"Annotations file not found: {annotations_path}")
        return False
    
    # Check for at least one subset
    subsets = list(data_path.glob("subset*"))
    if not subsets:
        logger.error("No subset directories found in data directory")
        return False
    
    # Check for MHD files
    mhd_files = list(data_path.glob("*/*.mhd"))
    if not mhd_files:
        logger.error("No MHD files found in subset directories")
        return False
    
    logger.info(f"✓ Found {len(subsets)} subsets")
    logger.info(f"✓ Found {len(mhd_files)} MHD files")
    logger.info(f"✓ Annotations file loaded ({len(pd.read_csv(annotations_path))} nodules)")
    
    return True


def calculate_iou(box1, box2):
    """
    Calculate Intersection over Union (IoU) between two boxes.
    
    Args:
        box1: [x1, y1, x2, y2]
        box2: [x1, y1, x2, y2]
    
    Returns:
        float: IoU score [0, 1]
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


def nms(boxes, scores, iou_threshold=0.5):
    """
    Non-Maximum Suppression.
    
    Args:
        boxes: List of [x1, y1, x2, y2]
        scores: List of confidence scores
        iou_threshold: IoU threshold for suppression
    
    Returns:
        list: Indices of boxes to keep
    """
    if len(boxes) == 0:
        return []
    
    indices = np.argsort(scores)[::-1]  # Sort by score descending
    keep = []
    
    while len(indices) > 0:
        current_idx = indices[0]
        keep.append(current_idx)
        
        if len(indices) == 1:
            break
        
        current_box = boxes[current_idx]
        remaining_boxes = boxes[indices[1:]]
        
        ious = np.array([calculate_iou(current_box, box) for box in remaining_boxes])
        indices = indices[1:][ious < iou_threshold]
    
    return keep


class AverageMeter:
    """Track average metric values."""
    
    def __init__(self, name):
        """Initialize meter."""
        self.name = name
        self.reset()
    
    def reset(self):
        """Reset values."""
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
    
    def update(self, val, n=1):
        """Update with new value."""
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count
    
    def __str__(self):
        return f"{self.name}: {self.avg:.4f}"


def get_training_config():
    """Get recommended training configuration."""
    return {
        'epochs': 20,
        'batch_size': 2,
        'learning_rate': 1e-4,
        'weight_decay': 1e-4,
        'num_workers': 0,
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
    }


def log_config(config):
    """Log configuration."""
    logger.info("╔════════════════════════════════════════╗")
    logger.info("║         TRAINING CONFIGURATION         ║")
    logger.info("╚════════════════════════════════════════╝")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")


__all__ = [
    'download_luna16',
    'check_luna16_installation',
    'calculate_iou',
    'nms',
    'AverageMeter',
    'get_training_config',
    'log_config',
]
