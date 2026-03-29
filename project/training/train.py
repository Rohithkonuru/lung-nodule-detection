"""
Training script for RetinaNet on LUNA16 dataset.

Usage:
    python train.py --data-dir data/LUNA16 --output-dir models/

The script will:
1. Load LUNA16 dataset
2. Train RetinaNet model
3. Save best checkpoint
4. Log training metrics
"""

import argparse
import logging
import os
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from torchvision.models.detection import retinanet_resnet50_fpn
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
import time

from dataset import LUNADataset

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RetinaNetTrainer:
    """Trainer class for RetinaNet on lung nodule detection."""
    
    def __init__(self, model, device, output_dir):
        """
        Initialize trainer.
        
        Args:
            model: RetinaNet model
            device: torch device
            output_dir: Directory to save checkpoints
        """
        self.model = model
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.best_loss = float('inf')
        self.checkpoint_path = self.output_dir / "retinanet_lung_best.pth"
    
    def train_epoch(self, loader, optimizer):
        """
        Train for one epoch.
        
        Args:
            loader: DataLoader
            optimizer: Optimizer
        
        Returns:
            float: Average loss for epoch
        """
        self.model.train()
        total_loss = 0
        num_batches = 0
        
        for batch_idx, (images, targets) in enumerate(loader):
            # Move to device
            images = [img.to(self.device) for img in images]
            
            # IMPORTANT: Format targets for RetinaNet (only boxes and labels)
            targets_device = []
            for t in targets:
                targets_device.append({
                    'boxes': t['boxes'].to(self.device),
                    'labels': t['labels'].to(self.device),
                })
            
            # Forward pass
            loss_dict = self.model(images, targets_device)
            losses = sum(loss for loss in loss_dict.values())
            
            # Backward pass
            optimizer.zero_grad()
            losses.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            optimizer.step()
            
            total_loss += losses.item()
            num_batches += 1
            
            if (batch_idx + 1) % 10 == 0:
                avg_loss = total_loss / num_batches
                logger.info(f"  Batch {batch_idx + 1}/{len(loader)}, Loss: {avg_loss:.4f}")
        
        return total_loss / num_batches
    
    def validate_epoch(self, loader):
        """
        Validate on validation set.
        
        Args:
            loader: DataLoader
        
        Returns:
            float: Average loss for epoch
        """
        self.model.eval()
        total_loss = 0
        num_batches = 0
        
        with torch.no_grad():
            for images, targets in loader:
                # Move to device
                images = [img.to(self.device) for img in images]
                
                # IMPORTANT: Format targets for RetinaNet (only boxes and labels)
                targets_device = []
                for t in targets:
                    targets_device.append({
                        'boxes': t['boxes'].to(self.device),
                        'labels': t['labels'].to(self.device),
                    })
                
                # Forward pass
                loss_dict = self.model(images, targets_device)
                losses = sum(loss for loss in loss_dict.values())
                
                total_loss += losses.item()
                num_batches += 1
        
        return total_loss / num_batches
    
    def fit(self, train_loader, val_loader, epochs, lr, weight_decay=1e-4):
        """
        Train model.
        
        Args:
            train_loader: Training DataLoader
            val_loader: Validation DataLoader
            epochs: Number of epochs
            lr: Learning rate
            weight_decay: Weight decay for optimizer
        """
        # Setup optimizer
        params = [p for p in self.model.parameters() if p.requires_grad]
        optimizer = optim.Adam(params, lr=lr, weight_decay=weight_decay)
        scheduler = StepLR(optimizer, step_size=max(1, epochs // 3), gamma=0.1)
        
        logger.info(f"Starting training for {epochs} epochs")
        logger.info(f"Learning rate: {lr}, Weight decay: {weight_decay}")
        logger.info(f"Device: {self.device}")
        
        for epoch in range(epochs):
            epoch_start = time.time()
            
            # Training
            logger.info(f"\nEpoch {epoch + 1}/{epochs}")
            train_loss = self.train_epoch(train_loader, optimizer)
            logger.info(f"  Train Loss: {train_loss:.4f}")
            
            # Validation
            val_loss = self.validate_epoch(val_loader)
            logger.info(f"  Val Loss: {val_loss:.4f}")
            
            # Save checkpoint if best
            if val_loss < self.best_loss:
                self.best_loss = val_loss
                self.save_checkpoint(epoch)
                logger.info(f"  ✓ Saved best checkpoint (loss: {val_loss:.4f})")
            
            # Step scheduler
            scheduler.step()
            
            epoch_time = time.time() - epoch_start
            logger.info(f"  Epoch time: {epoch_time:.2f}s")
        
        logger.info(f"\n✓ Training complete!")
        logger.info(f"Best checkpoint saved to: {self.checkpoint_path}")
    
    def save_checkpoint(self, epoch):
        """
        Save model checkpoint.
        
        Args:
            epoch: Current epoch
        """
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'best_loss': self.best_loss,
        }
        torch.save(checkpoint, self.checkpoint_path)


def main():
    """Main training script."""
    parser = argparse.ArgumentParser(description='Train RetinaNet on LUNA16')
    parser.add_argument('--data-dir', type=str, default='data/LUNA16',
                        help='Path to LUNA16 data directory')
    parser.add_argument('--output-dir', type=str, default='models',
                        help='Directory to save checkpoints')
    parser.add_argument('--epochs', type=int, default=20,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=2,
                        help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-4,
                        help='Learning rate')
    parser.add_argument('--weight-decay', type=float, default=1e-4,
                        help='Weight decay')
    parser.add_argument('--subset', type=int, default=None,
                        help='Restrict to specific subset (0-9)')
    parser.add_argument('--hard-negative-ratio', type=float, default=0.5,
                        help='Extra background-only samples ratio (e.g., 0.5 adds 50% hard negatives)')
    parser.add_argument('--num-workers', type=int, default=0,
                        help='Number of data loading workers')
    
    args = parser.parse_args()
    
    # Check if data directory exists
    if not Path(args.data_dir).exists():
        logger.error(f"Data directory not found: {args.data_dir}")
        logger.info("Download LUNA16 dataset from: https://luna16.grand-challenge.org/")
        return
    
    # Check if annotations file exists
    annotations_file = Path(args.data_dir) / 'annotations.csv'
    if not annotations_file.exists():
        logger.error(f"Annotations file not found: {annotations_file}")
        return
    
    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")
    
    # Load dataset
    logger.info(f"Loading LUNA16 dataset from {args.data_dir}")
    subset_dirs = sorted([p.name for p in Path(args.data_dir).glob('subset*') if p.is_dir()])

    if args.subset is not None:
        train_subset_folders = [f"subset{args.subset}"]
    else:
        recommended = [f"subset{i}" for i in range(6)]
        train_subset_folders = [s for s in recommended if s in subset_dirs]
        if not train_subset_folders:
            train_subset_folders = subset_dirs

    logger.info(f"Training subsets: {train_subset_folders}")

    train_dataset = LUNADataset(
        data_dir=args.data_dir,
        annotations_file=str(annotations_file),
        subset_folders=train_subset_folders,
        hard_negative_ratio=max(0.0, float(args.hard_negative_ratio)),
    )
    
    # Create DataLoaders
    def collate_fn(batch):
        images = [img for img, _ in batch]
        targets = [t for _, t in batch]
        return images, targets
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )
    
    # Prefer a validation subset not used by train (subset6 if available).
    val_subset = None
    for candidate in ["subset6", "subset7", "subset8", "subset9", "subset1"]:
        if candidate in subset_dirs and candidate not in train_subset_folders:
            val_subset = candidate
            break

    if val_subset is None and subset_dirs:
        val_subset = subset_dirs[0]

    logger.info(f"Validation subset: {val_subset}")

    val_dataset = LUNADataset(
        data_dir=args.data_dir,
        annotations_file=str(annotations_file),
        subset_folders=[val_subset] if val_subset else None,
        hard_negative_ratio=0.0,
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        collate_fn=collate_fn,
    )
    
    logger.info(f"Training samples: {len(train_dataset)}")
    logger.info(f"Validation samples: {len(val_dataset)}")
    
    # Load model
    logger.info("Loading RetinaNet model...")
    model = retinanet_resnet50_fpn(pretrained=True, num_classes=2)  # 1 class (nodule) + background
    model.to(device)
    
    # Create trainer and train
    trainer = RetinaNetTrainer(model, device, args.output_dir)
    trainer.fit(
        train_loader=train_loader,
        val_loader=val_loader,
        epochs=args.epochs,
        lr=args.lr,
        weight_decay=args.weight_decay,
    )


if __name__ == '__main__':
    main()
