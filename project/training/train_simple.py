#!/usr/bin/env python3
"""
LUNA16 RetinaNet Training Script - Simple & Direct

Trains RetinaNet on LUNA16 CT slices with real bounding box annotations.

Usage:
    python train_simple.py --data-dir data/LUNA16 --epochs 10 --batch-size 2
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.models.detection import retinanet_resnet50_fpn
from torch.optim.lr_scheduler import StepLR
from tqdm import tqdm
import argparse
from pathlib import Path
import logging
import time
from dataset_simple import get_luna_dataloader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def train_one_epoch(model, train_loader, optimizer, device, epoch, num_epochs):
    """
    Train for one epoch.
    
    Args:
        model: RetinaNet model
        train_loader: DataLoader
        optimizer: Optimizer
        device: torch.device
        epoch: current epoch number
        num_epochs: total number of epochs
    """
    model.train()
    total_loss = 0.0
    
    pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}")
    
    for batch_idx, (images, targets) in enumerate(pbar):
        # Move images to device
        images = [img.to(device) for img in images]
        
        # IMPORTANT FIX: Properly format targets for RetinaNet
        # Targets must be a list of dicts, each with 'boxes' and 'labels' tensors
        targets_device = []
        for target in targets:
            targets_device.append({
                'boxes': target['boxes'].to(device),
                'labels': target['labels'].to(device),
            })
        
        # Forward pass
        loss_dict = model(images, targets_device)
        losses = sum(loss for loss in loss_dict.values())
        
        # Backward pass
        optimizer.zero_grad()
        losses.backward()
        
        # Gradient clipping to prevent explosion
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        
        total_loss += losses.item()
        
        # Update progress bar
        avg_loss = total_loss / (batch_idx + 1)
        pbar.set_postfix({'loss': f'{losses.item():.4f}', 'avg': f'{avg_loss:.4f}'})
    
    return total_loss / len(train_loader)


def main():
    parser = argparse.ArgumentParser(description='Train RetinaNet on LUNA16')
    parser.add_argument('--data-dir', type=str, default='data/LUNA16',
                        help='Path to LUNA16 data directory')
    parser.add_argument('--annotations', type=str, default='data/LUNA16/annotations.csv',
                        help='Path to annotations.csv')
    parser.add_argument('--output-dir', type=str, default='models',
                        help='Directory to save checkpoints')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of epochs')
    parser.add_argument('--batch-size', type=int, default=2,
                        help='Batch size')
    parser.add_argument('--learning-rate', type=float, default=1e-4,
                        help='Learning rate')
    parser.add_argument('--num-workers', type=int, default=0,
                        help='Number of data loading workers')
    parser.add_argument('--subset', type=int, default=None,
                        help='Optional: Use only specific subset (0-9)')
    
    args = parser.parse_args()
    
    # Setup
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 70)
    logger.info("LUNA16 RetinaNet Training")
    logger.info("=" * 70)
    logger.info(f"Device: {device}")
    logger.info(f"Data: {args.data_dir}")
    logger.info(f"Epochs: {args.epochs}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Learning rate: {args.learning_rate}")
    logger.info("=" * 70)
    
    # Load dataset
    logger.info("\n📦 Loading dataset...")
    try:
        train_loader = get_luna_dataloader(
            data_dir=args.data_dir,
            annotations_file=args.annotations,
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=args.num_workers,
            subset=args.subset,
        )
        logger.info(f"✓ Dataset loaded ({len(train_loader)} batches)")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        logger.error("❌ Make sure LUNA16 is downloaded to data/LUNA16/")
        logger.error("   See: training/README.md for download instructions")
        return
    
    # Load model
    logger.info("\n🧠 Loading RetinaNet model...")
    model = retinanet_resnet50_fpn(pretrained=True, num_classes=2)  # 1=nodule, 0=background
    model.to(device)
    logger.info("✓ Model loaded (ImageNet pretrained)")
    
    # Optimizer and scheduler
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    scheduler = StepLR(optimizer, step_size=5, gamma=0.1)
    
    # Training loop
    logger.info("\n🚀 Starting training...\n")
    
    best_loss = float('inf')
    start_time = time.time()
    
    for epoch in range(args.epochs):
        epoch_loss = train_one_epoch(model, train_loader, optimizer, device, epoch, args.epochs)
        scheduler.step()
        
        logger.info(f"\nEpoch {epoch+1}/{args.epochs} Loss: {epoch_loss:.4f}")
        
        # Save best checkpoint
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            checkpoint_path = output_dir / "retinanet_lung_best.pth"
            torch.save(model.state_dict(), checkpoint_path)
            logger.info(f"✓ Best checkpoint saved: {checkpoint_path}")
        
        # Save periodic checkpoint
        if (epoch + 1) % 5 == 0:
            checkpoint_path = output_dir / f"retinanet_lung_epoch_{epoch+1}.pth"
            torch.save(model.state_dict(), checkpoint_path)
            logger.info(f"✓ Checkpoint saved: {checkpoint_path}")
    
    # Final save
    elapsed_time = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ Training complete!")
    logger.info(f"   Best Loss: {best_loss:.4f}")
    logger.info(f"   Time: {elapsed_time/3600:.1f} hours")
    logger.info(f"   Best Model: {output_dir / 'retinanet_lung_best.pth'}")
    logger.info("=" * 70)
    
    # Verify model can be loaded
    logger.info("\n🔍 Verifying model...")
    try:
        test_model = retinanet_resnet50_fpn(pretrained=False, num_classes=2)
        test_model.load_state_dict(torch.load(output_dir / "retinanet_lung_best.pth"))
        logger.info("✓ Model verified - can be loaded successfully")
    except Exception as e:
        logger.error(f"❌ Model verification failed: {e}")


if __name__ == "__main__":
    main()
