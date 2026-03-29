"""
Complete PyTorch Training Script for LUNA16 Lung Nodule Detection
Uses RetinaNet with real LUNA16 dataset and annotations
"""

import os
import sys
import logging
import torch
import torch.optim as optim
from pathlib import Path
from torch.utils.data import DataLoader
import torchvision
from torchvision.models.detection import retinanet_resnet50_fpn

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the LUNA dataset loader
try:
    from training.dataset import LUNADataset, get_luna_dataloader
except ImportError:
    logger.error("Failed to import LUNA dataset loader. Ensure training/dataset.py exists.")
    sys.exit(1)


class LUNARetinaNetTrainer:
    """
    Complete trainer for LUNA16 lung nodule detection using RetinaNet.
    """
    
    def __init__(self, 
                 data_dir=r"D:\project\data\LUNA16",
                 annotations_file=r"D:\project\data\LUNA16\annotations.csv",
                 model_save_path=r"D:\project\models\retinanet_lung_real.pth",
                 best_model_path=r"D:\project\models\retinanet_lung_best.pth",
                 epochs=20,
                 batch_size=2,
                 learning_rate=1e-4,
                 preferred_subset_max=5,
                 hard_negative_ratio=0.5,
                 device=None):
        """
        Initialize trainer.
        
        Args:
            data_dir: Path to LUNA16 dataset (containing subset0, subset1, etc.)
            annotations_file: Path to annotations.csv
            model_save_path: Where to save trained model
            epochs: Number of training epochs
            batch_size: Batch size for training
            learning_rate: Learning rate for optimizer
            device: Device to use ('cuda' or 'cpu'), auto-detected if None
        """
        self.data_dir = Path(data_dir)
        self.annotations_file = Path(annotations_file)
        self.model_save_path = Path(model_save_path)
        self.best_model_path = Path(best_model_path)
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.preferred_subset_max = int(preferred_subset_max)
        self.hard_negative_ratio = float(max(0.0, hard_negative_ratio))
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        logger.info(f"Using device: {self.device}")
        
        # Validate dataset paths
        self._validate_paths()
        
        # Initialize model and optimizer
        self.model = self._create_model()
        self.model.to(self.device)
        
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.best_loss = float('inf')
        
        # Dataset and dataloader
        self.train_loader = None
        self.dataset = None
        self.total_nodules = 0
    
    def _validate_paths(self):
        """Validate that dataset paths exist."""
        if not self.data_dir.exists():
            logger.error(f"Data directory not found: {self.data_dir}")
            sys.exit(1)
        
        # Discover subset* folders dynamically
        subset_dirs = [p for p in self.data_dir.iterdir() if p.is_dir() and p.name.lower().startswith("subset")]
        subset_dirs.sort()
        self.existing_subsets = [p.name for p in subset_dirs]
        if not self.existing_subsets:
            logger.warning(f"No subset* folders found in {self.data_dir}. Nothing to train.")
        else:
            logger.info(f"Detected subset folders: {self.existing_subsets}")

        # Prefer subset0..subset5 as a strong minimum signal budget when available.
        recommended = [f"subset{i}" for i in range(self.preferred_subset_max + 1)]
        existing_set = set(self.existing_subsets)
        recommended_available = [s for s in recommended if s in existing_set]

        if recommended_available:
            self.active_subsets = recommended_available
        else:
            self.active_subsets = self.existing_subsets

        if len(recommended_available) < (self.preferred_subset_max + 1):
            logger.warning(
                "Recommended training data is subset0..subset%d; found only %d/%d recommended subsets.",
                self.preferred_subset_max,
                len(recommended_available),
                self.preferred_subset_max + 1,
            )

        logger.info(f"Training will use subsets: {self.active_subsets}")
        
        if not self.annotations_file.exists():
            logger.warning(f"Annotations file not found: {self.annotations_file}")
            logger.info(f"Expected format: seriesuid, coordX, coordY, coordZ, diameter_mm")
        
        # Create model save directory
        self.model_save_path.parent.mkdir(parents=True, exist_ok=True)
        self.best_model_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _create_model(self):
        """
        Create RetinaNet model with 1 class (lung nodule).
        
        Returns:
            Modified RetinaNet model
        """
        logger.info("Loading pretrained RetinaNet ResNet50-FPN...")
        
        # Load pretrained model
        model = retinanet_resnet50_fpn(pretrained=True)
        
        # RetinaNet outputs for background + N classes
        # Default is 81 classes (COCO)
        # We need: background (0) + nodule (1) = 2 classes
        
        # Modify the classification head
        num_classes = 2  # background + nodule
        in_channels = model.backbone.out_channels
        
        # Replace the head with custom number of classes
        model.num_classes = num_classes
        
        # Access the classification head
        num_anchors = model.head.classification_head.num_anchors
        
        # Replace classification head
        from torchvision.models.detection.retinanet import RetinaNetClassificationHead
        
        model.head.classification_head = RetinaNetClassificationHead(
            in_channels=in_channels,
            num_anchors=num_anchors,
            num_classes=num_classes,
            prior_probability=0.01
        )
        
        logger.info(f"Model created with {num_classes} classes (background + nodule)")
        return model
    
    def _load_dataset(self):
        """Load LUNA16 dataset."""
        logger.info("Loading LUNA16 dataset...")
        
        try:
            self.dataset = LUNADataset(
                data_dir=str(self.data_dir),
                annotations_file=str(self.annotations_file),
                subset_folders=self.active_subsets,
                cache=False,  # Don't cache to save memory
                hard_negative_ratio=self.hard_negative_ratio,
            )
        except FileNotFoundError as e:
            logger.error(f"Dataset loading failed: {e}")
            logger.error(f"Please ensure:")
            logger.error(f"  1. Data directory exists: {self.data_dir}")
            logger.error(f"  2. Annotations file exists: {self.annotations_file}")
            logger.error(f"  3. Format: seriesuid, coordX, coordY, coordZ, diameter_mm")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error loading dataset: {e}")
            sys.exit(1)
        
        dataset_size = len(self.dataset)
        self.total_nodules = sum(len(self.dataset.annotations[self.dataset.annotations['seriesuid'] == sid]) for sid in self.dataset.series_with_nodules)
        logger.info(f"Dataset root: {self.data_dir}")
        logger.info(f"Available subset folders: {self.existing_subsets}")
        logger.info(f"Active subset folders: {self.active_subsets}")
        logger.info(f"Hard negative ratio: {self.hard_negative_ratio:.2f}")
        logger.info(f"Loaded scans: {len(self.dataset.series_with_nodules)}")
        logger.info(f"Total nodules: {self.total_nodules}")
        logger.info(f"Training samples (slices): {dataset_size}")
        
        # Create dataloader
        def collate_fn(batch):
            """Custom collate function for detection data."""
            images = []
            targets = []
            for img, target in batch:
                images.append(img)
                targets.append(target)
            return images, targets
        
        self.train_loader = DataLoader(
            self.dataset,
            batch_size=self.batch_size,
            shuffle=True,
            collate_fn=collate_fn,
            num_workers=0
        )
        
        logger.info(f"DataLoader created with batch size {self.batch_size}")
    
    def _preprocess_images(self, images):
        """
        Preprocess images for RetinaNet.
        
        RetinaNet expects 3-channel (RGB) images.
        Convert single-channel CT slices to 3-channel.
        """
        processed = []
        for img in images:
            if img.shape[0] == 1:
                # Convert single channel to 3 channels (grayscale to RGB)
                img = img.repeat(3, 1, 1)
            
            # Ensure values are in [0, 1]
            if img.max() > 1.0:
                img = img / 255.0
            
            processed.append(img)
        
        return processed
    
    def train(self):
        """
        Execute training loop.
        """
        logger.info("=" * 60)
        logger.info("Starting LUNA16 RetinaNet Training")
        logger.info("=" * 60)
        
        # Load dataset
        self._load_dataset()
        
        if len(self.dataset) == 0:
            logger.error("Dataset is empty! Cannot train.")
            return
        
        # Training loop
        self.model.train()
        
        for epoch in range(self.epochs):
            epoch_loss = 0
            num_batches = 0
            
            logger.info(f"\nEpoch {epoch + 1}/{self.epochs}")
            logger.info("-" * 60)
            
            try:
                for batch_idx, (images, targets) in enumerate(self.train_loader):
                    # Preprocess images (convert to 3 channels)
                    images = self._preprocess_images(images)
                    
                    # Move to device
                    images = [img.to(self.device) for img in images]
                    
                    # Prepare targets
                    processed_targets = []
                    for target in targets:
                        t = {}
                        if len(target['boxes']) > 0:
                            t['boxes'] = target['boxes'].to(self.device)
                            t['labels'] = target['labels'].to(self.device)
                        else:
                            # Handle empty targets
                            t['boxes'] = torch.zeros((0, 4), dtype=torch.float32, device=self.device)
                            t['labels'] = torch.zeros((0,), dtype=torch.int64, device=self.device)
                        processed_targets.append(t)
                    
                    # Forward pass
                    self.optimizer.zero_grad()
                    
                    # RetinaNet loss computation
                    loss_dict = self.model(images, processed_targets)
                    losses = sum(loss for loss in loss_dict.values())
                    
                    # Backward pass
                    losses.backward()
                    self.optimizer.step()
                    
                    epoch_loss += losses.item()
                    num_batches += 1
                    
                    if (batch_idx + 1) % 5 == 0:
                        avg_loss = epoch_loss / num_batches
                        logger.info(f"  Batch {batch_idx + 1}/{len(self.train_loader)}, Loss: {avg_loss:.4f}")
            
            except KeyboardInterrupt:
                logger.info("Training interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error during training: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Log epoch results
            if num_batches > 0:
                avg_epoch_loss = epoch_loss / num_batches
                logger.info(f"Epoch {epoch + 1} completed - Average Loss: {avg_epoch_loss:.4f}")
                if avg_epoch_loss < self.best_loss:
                    self.best_loss = avg_epoch_loss
                    self._save_model(epoch, best=True)
            
            # Save checkpoint
            self._save_model(epoch)
        
        logger.info("\n" + "=" * 60)
        logger.info("Training Complete!")
        logger.info("=" * 60)
        
        # Final save
        self._save_model(final=True)
        
        logger.info(f"Model saved to: {self.model_save_path}")
        logger.info(f"Best model saved to: {self.best_model_path}")
    
    def _save_model(self, epoch=None, final=False, best=False):
        """
        Save model weights.
        
        Args:
            epoch: Epoch number (for checkpoints)
            final: If True, save as final model
            best: If True, save as best model
        """
        if best:
            save_path = self.best_model_path
        elif final:
            save_path = self.model_save_path
        else:
            save_path = self.model_save_path.parent / f"retinanet_lung_real_epoch_{epoch + 1}.pth"
        
        try:
            torch.save(self.model.state_dict(), save_path)
            logger.info(f"Model checkpoint saved: {save_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {e}")


def main():
    """Main training entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Train RetinaNet for LUNA16 lung nodule detection'
    )
    parser.add_argument('--data-dir', type=str, default=r"D:\project\data\LUNA16",
                        help='Path to LUNA16 dataset directory')
    parser.add_argument('--annotations', type=str, default=r"D:\project\data\LUNA16\annotations.csv",
                        help='Path to annotations.csv')
    parser.add_argument('--model-save', type=str, default=r"D:\project\models\retinanet_lung_real.pth",
                        help='Path to save final model')
    parser.add_argument('--best-model', type=str, default=r"D:\project\models\retinanet_lung_best.pth",
                        help='Path to save best (lowest loss) model')
    parser.add_argument('--epochs', type=int, default=20,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=2,
                        help='Batch size for training')
    parser.add_argument('--learning-rate', type=float, default=1e-4,
                        help='Learning rate')
    parser.add_argument('--preferred-subset-max', type=int, default=5,
                        help='Prefer subset0..subsetN for training when available (default: 5)')
    parser.add_argument('--hard-negative-ratio', type=float, default=0.5,
                        help='Extra background-only samples ratio (e.g., 0.5 adds 50% hard negatives)')
    parser.add_argument('--device', type=str, default=None,
                        help='Device to use (cuda or cpu)')
    
    args = parser.parse_args()
    
    # Create trainer
    trainer = LUNARetinaNetTrainer(
        data_dir=args.data_dir,
        annotations_file=args.annotations,
        model_save_path=args.model_save,
        best_model_path=args.best_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        preferred_subset_max=args.preferred_subset_max,
        hard_negative_ratio=args.hard_negative_ratio,
        device=args.device
    )
    
    # Start training
    trainer.train()


if __name__ == "__main__":
    main()
