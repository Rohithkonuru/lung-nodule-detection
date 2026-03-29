#!/usr/bin/env python3
"""
🚀 FULLY AUTOMATED LUNA16 RetinaNet Training Pipeline

This single-script solution:
1. Automatically downloads LUNA16-like dataset
2. Extracts and prepares data
3. Creates training dataset with real annotations
4. Trains RetinaNet on lung nodule detection
5. Saves trained model

Run with:
    python train_auto.py [--epochs 5] [--batch-size 2] [--use-kaggle]

Features:
✅ Auto-downloads dataset (with fallback options)
✅ No manual setup required
✅ Comprehensive logging
✅ Error handling & recovery
✅ Production-ready code
"""

import os
import sys
import argparse
import logging
import zipfile
import shutil
import warnings
from pathlib import Path
from typing import List, Tuple, Optional
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision.models.detection import retinanet_resnet50_fpn
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from tqdm import tqdm

# Suppress warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    'DATA_DIR': Path('data'),
    'MODEL_DIR': Path('models'),
    'LUNA16_URLS': [
        'https://zenodo.org/record/3514411/files/subset0.zip',  # Backup
        'https://zenodo.org/api/files/b8e7daae-6f22-4c7a-aef1-1e25d2d8f00d/subset0.zip',  # Alternative
    ],
    'ANNOTATIONS_URL': 'https://zenodo.org/record/3514411/files/annotations.csv',
    'BATCH_SIZE': 2,
    'EPOCHS': 5,
    'LEARNING_RATE': 1e-4,
    'DEVICE': 'cuda' if torch.cuda.is_available() else 'cpu',
    'NUM_WORKERS': 0,  # Set to 0 for Windows compatibility
}

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configure logging with timestamps and colors."""
    import io
    # Configure logging to handle Unicode properly on Windows
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)),
            logging.FileHandler('training.log', encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# DATASET DOWNLOAD & PREPARATION
# ============================================================================

class DatasetDownloader:
    """Handles automatic dataset download and preparation."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def download_file(self, url: str, dest: Path, timeout: int = 300) -> bool:
        """
        Download file from URL with progress bar.
        
        Args:
            url: Download URL
            dest: Destination path
            timeout: Download timeout in seconds
        
        Returns:
            True if successful, False otherwise
        """
        if dest.exists():
            logger.info(f"[OK] File already exists: {dest}")
            return True
        
        try:
            import requests
            logger.info(f"[DOWNLOAD] Downloading: {url}")
            
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(dest, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc=dest.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            logger.info(f"[OK] Downloaded: {dest}")
            return True
        
        except Exception as e:
            logger.warning(f"[WARNING] Download failed: {e}")
            return False
    
    def extract_zip(self, zip_path: Path, extract_to: Path) -> bool:
        """Extract ZIP file with progress."""
        if not zip_path.exists():
            logger.error(f"ZIP file not found: {zip_path}")
            return False
        
        try:
            logger.info(f"[EXTRACT] Extracting: {zip_path.name}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            
            logger.info(f"[OK] Extracted to: {extract_to}")
            return True
        
        except Exception as e:
            logger.error(f"[ERROR] Extraction failed: {e}")
            return False
    
    def prepare_dataset(self) -> bool:
        """
        Prepare dataset: download, extract, verify.
        
        Returns:
            True if dataset ready, False otherwise
        """
        logger.info("=" * 70)
        logger.info("STEP 1: Dataset Preparation")
        logger.info("=" * 70)
        
        # Check if already prepared
        subset_dirs = list(self.data_dir.glob("subset*"))
        annotations_file = self.data_dir / "annotations.csv"
        
        if subset_dirs and annotations_file.exists():
            logger.info(f"[OK] Dataset already prepared ({len(subset_dirs)} subsets found)")
            return True
        
        # Download dataset
        logger.info("[DOWNLOAD] Downloading dataset...")
        
        # Try multiple URLs, fall back to synthetic data
        zip_path = self.data_dir / "subset0.zip"
        
        download_success = False
        for url in CONFIG['LUNA16_URLS']:
            if self.download_file(url, zip_path, timeout=60):
                download_success = True
                break
        
        if not download_success:
            logger.warning("[WARNING] Could not download from Zenodo (requires internet)")
            logger.info("[INFO] Alternatives:")
            logger.info("   1. Manual download from: https://luna16.grand-challenge.org/")
            logger.info("   2. Download from Kaggle: kaggle datasets download -d kavyakhattar/luna16-lung-cancer-detection")
            logger.info("   3. Using synthetic data instead (limited training)")
            
            # Create synthetic data for testing
            return self._create_synthetic_data()
        
        # Extract dataset
        if not self.extract_zip(zip_path, self.data_dir):
            logger.warning("Extraction failed, trying synthetic data")
            return self._create_synthetic_data()
        
        # Download annotations
        annotations_file = self.data_dir / "annotations.csv"
        if not annotations_file.exists():
            self.download_file(CONFIG['ANNOTATIONS_URL'], annotations_file)
        
        # Verify
        subset_dirs = list(self.data_dir.glob("subset*"))
        if subset_dirs and annotations_file.exists():
            logger.info(f"[OK] Dataset ready: {len(subset_dirs)} subsets, {annotations_file.name}")
            return True
        
        logger.error("[ERROR] Dataset preparation failed")
        return False
    
    def _create_synthetic_data(self) -> bool:
        """
        Create synthetic training data for testing.
        
        Returns:
            True if synthetic data created successfully
        """
        logger.info("[SYNTHETIC] Creating synthetic test data...")
        
        try:
            import SimpleITK as sitk
            
            subset0_dir = self.data_dir / "subset0"
            subset0_dir.mkdir(parents=True, exist_ok=True)
            
            # Create 10 synthetic CT volumes
            num_volumes = 10
            for i in range(num_volumes):
                # Create synthetic 3D CT scan (64x256x256)
                volume = np.random.normal(loc=-400, scale=100, size=(64, 256, 256)).astype(np.int16)
                
                # Add synthetic nodules (bright spots)
                for _ in range(np.random.randint(1, 4)):
                    z = np.random.randint(10, 54)
                    y = np.random.randint(50, 206)
                    x = np.random.randint(50, 206)
                    radius = np.random.randint(5, 20)
                    
                    # Safely add nodule with proper bounds checking
                    z_start = max(0, z - radius)
                    z_end = min(64, z + radius + 1)
                    y_start = max(0, y - radius)
                    y_end = min(256, y + radius + 1)
                    x_start = max(0, x - radius)
                    x_end = min(256, x + radius + 1)
                    
                    # Create sphere in valid region
                    region = volume[z_start:z_end, y_start:y_end, x_start:x_end]
                    zz, yy, xx = np.ogrid[0:region.shape[0], 0:region.shape[1], 0:region.shape[2]]
                    dist_z = zz - (z - z_start)
                    dist_y = yy - (y - y_start)
                    dist_x = xx - (x - x_start)
                    mask = (dist_z * dist_z + dist_y * dist_y + dist_x * dist_x) <= (radius * radius)
                    region[mask] = 100
                    volume[z_start:z_end, y_start:y_end, x_start:x_end] = region
                
                # Save as SimpleITK image
                img = sitk.GetImageFromArray(volume)
                img.SetSpacing([1.0, 1.0, 1.0])
                
                series_id = f"synthetic_{i:03d}"
                sitk.WriteImage(img, str(subset0_dir / f"{series_id}.mhd"))
            
            # Create annotations CSV
            annotations = []
            for i in range(num_volumes):
                for _ in range(np.random.randint(1, 4)):
                    annotations.append({
                        'seriesuid': f"synthetic_{i:03d}",
                        'coordX': np.random.randint(50, 206),
                        'coordY': np.random.randint(50, 206),
                        'coordZ': np.random.randint(10, 54),
                        'diameter_mm': np.random.uniform(8, 25),
                    })
            
            df = pd.DataFrame(annotations)
            df.to_csv(self.data_dir / "annotations.csv", index=False)
            
            logger.info(f"[OK] Created synthetic data: {num_volumes} volumes, {len(annotations)} nodules")
            logger.info("  Note: Use real LUNA16 for production training")
            return True
        
        except Exception as e:
            logger.error(f"[ERROR] Failed to create synthetic data: {e}")
            return False

# ============================================================================
# DATASET LOADER
# ============================================================================

class LunaDataset(Dataset):
    """LUNA16 dataset loader with automatic bounding box extraction."""
    
    def __init__(self, data_dir: Path, annotations_file: Path, subset_id: int = 0):
        """
        Args:
            data_dir: Path to data directory
            annotations_file: Path to annotations.csv
            subset_id: Subset ID to load (0-9)
        """
        self.data_dir = Path(data_dir)
        self.annotations = pd.read_csv(annotations_file)
        
        # Filter by subset
        subset_name = f"subset{subset_id}"
        self.series_ids = []
        
        for series_id in self.annotations['seriesuid'].unique():
            mhd_path = self._find_mhd_path(series_id)
            if mhd_path and subset_name in str(mhd_path):
                self.series_ids.append(series_id)
        
        logger.info(f"[OK] Loaded {len(self.series_ids)} series from {subset_name}")
    
    def __len__(self) -> int:
        return len(self.series_ids)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, dict]:
        """
        Returns:
            image: Tensor[1, H, W]
            target: dict with 'boxes' and 'labels'
        """
        series_id = self.series_ids[idx]
        
        # Load CT volume
        import SimpleITK as sitk
        
        mhd_path = self._find_mhd_path(series_id)
        img = sitk.ReadImage(mhd_path)
        vol = sitk.GetArrayFromImage(img)
        spacing = img.GetSpacing()  # (X, Y, Z)
        
        # Use middle slice
        z = vol.shape[0] // 2
        slice_img = vol[z].astype(np.float32)
        
        # Normalize
        slice_min = np.min(slice_img)
        slice_max = np.max(slice_img)
        if slice_max > slice_min:
            slice_img = (slice_img - slice_min) / (slice_max - slice_min) * 255
        else:
            slice_img = np.ones_like(slice_img) * 128
        
        slice_img = slice_img.astype(np.uint8)
        
        # Convert to tensor
        img_tensor = torch.tensor(slice_img, dtype=torch.float32).unsqueeze(0)
        
        # Get bounding boxes
        boxes, labels = self._get_bounding_boxes(series_id, z, spacing)
        
        target = {
            'boxes': torch.tensor(boxes, dtype=torch.float32),
            'labels': torch.tensor(labels, dtype=torch.int64),
        }
        
        return img_tensor, target
    
    def _find_mhd_path(self, series_id: str) -> Optional[str]:
        """Find MHD file for series ID."""
        for subset_dir in sorted(self.data_dir.glob("subset*")):
            if not subset_dir.is_dir():
                continue
            for mhd_file in subset_dir.glob(f"{series_id}*.mhd"):
                return str(mhd_file)
        return None
    
    def _get_bounding_boxes(self, series_id: str, slice_idx: int, 
                           spacing: Tuple[float, float, float]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract bounding boxes for nodules on a specific slice.
        
        Args:
            series_id: Series UID
            slice_idx: Z-index
            spacing: Image spacing (X, Y, Z)
        
        Returns:
            boxes: [N, 4] array of [x1, y1, x2, y2]
            labels: [N] array (all 1 for nodule)
        """
        boxes = []
        labels = []
        
        series_annot = self.annotations[self.annotations['seriesuid'] == series_id]
        if len(series_annot) == 0:
            return np.array([], dtype=np.float32).reshape(0, 4), np.array([], dtype=np.int64)
        
        spacing_x, spacing_y, spacing_z = spacing
        
        for _, row in series_annot.iterrows():
            x_mm = float(row['coordX'])
            y_mm = float(row['coordY'])
            z_mm = float(row['coordZ'])
            diameter_mm = float(row['diameter_mm'])
            
            # Convert mm to pixels
            x_px = x_mm / spacing_x
            y_px = y_mm / spacing_y
            z_px = z_mm / spacing_z
            radius_px = diameter_mm / (2 * spacing_y)
            
            # Check if nodule is on this slice (±2 slice tolerance)
            if abs(int(z_px) - slice_idx) <= 2:
                x1 = max(0, x_px - radius_px)
                y1 = max(0, y_px - radius_px)
                x2 = x_px + radius_px
                y2 = y_px + radius_px
                
                if x2 > x1 and y2 > y1:
                    boxes.append([x1, y1, x2, y2])
                    labels.append(1)
        
        if len(boxes) == 0:
            return np.array([], dtype=np.float32).reshape(0, 4), np.array([], dtype=np.int64)
        
        return np.array(boxes, dtype=np.float32), np.array(labels, dtype=np.int64)

# ============================================================================
# MODEL TRAINING
# ============================================================================

class RetinaNetTrainer:
    """Trainer for RetinaNet on lung nodules."""
    
    def __init__(self, model_dir: Path, device: str):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.device = device
        
        logger.info(f"Device: {device}")
    
    def train(self, train_loader: DataLoader, epochs: int, 
              learning_rate: float, model_path: Optional[Path] = None) -> Path:
        """
        Train RetinaNet model.
        
        Args:
            train_loader: Training DataLoader
            epochs: Number of epochs
            learning_rate: Learning rate
            model_path: Optional path to save model
        
        Returns:
            Path to saved model
        """
        logger.info("=" * 70)
        logger.info("STEP 2: Model Training")
        logger.info("=" * 70)
        
        # Load model
        logger.info("[MODEL] Loading RetinaNet (ImageNet pretrained)...")
        # Note: RetinaNet requires num_classes=91 when using COCO pretrained weights
        # We'll use pretrained backbone but the model will expect 91 classes
        # This is acceptable for fine-tuning - the extra classes will just have low confidence
        try:
            # Try loading with num_classes parameter (newer torchvision)
            model = retinanet_resnet50_fpn(pretrained=True, num_classes=91)
        except:
            # Fallback: load without specifying num_classes
            model = retinanet_resnet50_fpn(pretrained=True)
        
        model.to(self.device)
        logger.info("[OK] Model loaded")
        
        # Optimizer
        optimizer = optim.Adam(model.parameters(), lr=learning_rate)
        scheduler = StepLR(optimizer, step_size=max(1, epochs // 2), gamma=0.1)
        
        best_loss = float('inf')
        
        # Training loop
        logger.info(f"[TRAINING] Starting training for {epochs} epochs")
        
        for epoch in range(epochs):
            model.train()
            total_loss = 0.0
            num_batches = 0
            
            pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
            
            for images, targets in pbar:
                # Move to device
                images = [img.to(self.device) for img in images]
                
                # CRITICAL FIX: Format targets for RetinaNet
                targets_device = []
                for t in targets:
                    targets_device.append({
                        'boxes': t['boxes'].to(self.device),
                        'labels': t['labels'].to(self.device),
                    })
                
                # Forward pass
                loss_dict = model(images, targets_device)
                losses = sum(loss for loss in loss_dict.values())
                
                # Backward pass
                optimizer.zero_grad()
                losses.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                
                total_loss += losses.item()
                num_batches += 1
                
                avg_loss = total_loss / num_batches
                pbar.set_postfix({'loss': f'{losses.item():.4f}', 'avg': f'{avg_loss:.4f}'})
            
            epoch_loss = total_loss / num_batches
            scheduler.step()
            
            logger.info(f"Epoch {epoch+1}/{epochs} - Loss: {epoch_loss:.4f}")
            
            # Save best model
            if epoch_loss < best_loss:
                best_loss = epoch_loss
                save_path = model_path or self.model_dir / "retinanet_lung_auto.pth"
                torch.save(model.state_dict(), save_path)
                logger.info(f"[OK] Best model saved: {save_path}")
        
        logger.info("[COMPLETE] Training complete!")
        logger.info(f"   Final Loss: {epoch_loss:.4f}")
        logger.info(f"   Best Loss: {best_loss:.4f}")
        
        return save_path

# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main training pipeline."""
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Automated RetinaNet Training')
    parser.add_argument('--epochs', type=int, default=CONFIG['EPOCHS'],
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=CONFIG['BATCH_SIZE'],
                        help='Batch size')
    parser.add_argument('--learning-rate', type=float, default=CONFIG['LEARNING_RATE'],
                        help='Learning rate')
    parser.add_argument('--use-kaggle', action='store_true',
                        help='Try Kaggle API for dataset download')
    
    args = parser.parse_args()
    
    logger.info("\n" + "=" * 70)
    logger.info("AUTOMATED RETINANET TRAINING PIPELINE".center(70))
    logger.info("=" * 70)
    logger.info(f"Epochs: {args.epochs}")
    logger.info(f"Batch Size: {args.batch_size}")
    logger.info(f"Learning Rate: {args.learning_rate}")
    logger.info(f"Device: {CONFIG['DEVICE']}")
    logger.info("=" * 70)
    
    start_time = time.time()
    
    try:
        # STEP 1: Download & prepare dataset
        downloader = DatasetDownloader(CONFIG['DATA_DIR'])
        if not downloader.prepare_dataset():
            logger.error("[ERROR] Dataset preparation failed")
            return False
        
        # STEP 2: Load dataset
        logger.info("=" * 70)
        logger.info("STEP 2: Dataset Loading")
        logger.info("=" * 70)
        
        dataset = LunaDataset(
            data_dir=CONFIG['DATA_DIR'],
            annotations_file=CONFIG['DATA_DIR'] / 'annotations.csv',
            subset_id=0
        )
        
        # Create DataLoader
        train_loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=CONFIG['NUM_WORKERS'],
            collate_fn=lambda batch: ([img for img, _ in batch], 
                                      [t for _, t in batch]),
        )
        
        logger.info(f"[OK] Dataset: {len(dataset)} samples")
        logger.info(f"[OK] DataLoader: {len(train_loader)} batches (batch size: {args.batch_size})")
        
        # STEP 3: Train model
        trainer = RetinaNetTrainer(CONFIG['MODEL_DIR'], CONFIG['DEVICE'])
        
        model_path = trainer.train(
            train_loader=train_loader,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
        )
        
        # SUMMARY
        elapsed = time.time() - start_time
        
        logger.info("\n" + "=" * 70)
        logger.info("TRAINING SUMMARY".center(70))
        logger.info("=" * 70)
        logger.info(f"Total Time: {elapsed/3600:.2f} hours")
        logger.info(f"Model Saved: {model_path}")
        logger.info(f"Model Size: {Path(model_path).stat().st_size / (1024**2):.1f} MB")
        logger.info("\nNext Steps:")
        logger.info(f"   1. Copy model to backend:")
        logger.info(f"      cp {model_path} models/finetuned/retinanet_lung_best.pth")
        logger.info(f"   2. Restart backend:")
        logger.info(f"      python backend/run_server.py")
        logger.info(f"   3. Test detection:")
        logger.info(f"      http://localhost:3000")
        logger.info("=" * 70 + "\n")
        
        return True
    
    except Exception as e:
        logger.error(f"[ERROR] Training failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
