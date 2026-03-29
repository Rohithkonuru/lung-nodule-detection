#!/usr/bin/env python3
"""
Quick Setup and Test Script for LUNA16 Training
Verifies environment, dataset, and runs a simple training test
"""

import sys
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def check_python_version():
    """Check Python version compatibility."""
    logger.info("\n" + "=" * 60)
    logger.info("1. Checking Python Version")
    logger.info("=" * 60)
    
    version = sys.version_info
    logger.info(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error("Python 3.8+ is required")
        return False
    
    logger.info("✓ Python version OK\n")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    logger.info("=" * 60)
    logger.info("2. Checking Dependencies")
    logger.info("=" * 60)
    
    required_packages = {
        'torch': 'PyTorch',
        'torchvision': 'TorchVision',
        'SimpleITK': 'SimpleITK',
        'pandas': 'Pandas',
        'numpy': 'NumPy',
    }
    
    all_installed = True
    
    for module, name in required_packages.items():
        try:
            __import__(module)
            version = __import__(module).__version__
            logger.info(f"✓ {name} ({version})")
        except ImportError:
            logger.error(f"✗ {name} not installed")
            all_installed = False
    
    if not all_installed:
        logger.error("\nTo install missing packages, run:")
        logger.error("  pip install -r requirements.txt")
    
    logger.info()
    return all_installed


def check_dataset():
    """Check if LUNA16 dataset exists."""
    logger.info("=" * 60)
    logger.info("3. Checking Dataset Structure")
    logger.info("=" * 60)
    
    data_dir = Path('data')
    
    # Check data directory
    if not data_dir.exists():
        logger.warning(f"Data directory not found: {data_dir}")
        logger.info("Directory structure should be:")
        logger.info("  data/")
        logger.info("    subset0/")
        logger.info("      *.mhd (CT volume)")
        logger.info("      *.raw (CT volumetric data)")
        logger.info("    subset1/")
        logger.info("    ...")
        logger.info("    annotations.csv")
        return False
    
    # Check subsets
    subsets = sorted([d for d in data_dir.iterdir() if d.is_dir() and d.name.startswith('subset')])
    
    if not subsets:
        logger.warning(f"No subset directories found in {data_dir}")
        return False
    
    logger.info(f"✓ Found {len(subsets)} subset directories")
    
    # Check for MHD files
    mhd_files = list(data_dir.glob('**/subset*/*.mhd'))
    
    if not mhd_files:
        logger.warning("No .mhd files found in subset directories")
        return False
    
    logger.info(f"✓ Found {len(mhd_files)} MHD files")
    
    # Check annotations
    annotations_file = data_dir / 'annotations.csv'
    
    if not annotations_file.exists():
        logger.warning(f"Annotations file not found: {annotations_file}")
        logger.info("To create dummy annotations for testing, run:")
        logger.info("  python prepare_luna_annotations.py --create-dummy")
        logger.info("\nFor real training, ensure annotations.csv contains:")
        logger.info("  seriesuid, coordX, coordY, coordZ, diameter_mm")
        return False
    
    logger.info(f"✓ Found annotations file: {annotations_file}")
    
    # Verify annotations format
    try:
        import pandas as pd
        df = pd.read_csv(annotations_file)
        required_cols = ['seriesuid', 'coordX', 'coordY', 'coordZ', 'diameter_mm']
        if all(col in df.columns for col in required_cols):
            logger.info(f"✓ Annotations format correct ({len(df)} nodules)")
            return True
        else:
            logger.error(f"Annotations format incorrect. Missing columns: {set(required_cols) - set(df.columns)}")
            return False
    except Exception as e:
        logger.error(f"Failed to read annotations: {e}")
        return False


def check_models_directory():
    """Check if models directory exists, create if needed."""
    logger.info("=" * 60)
    logger.info("4. Checking Models Directory")
    logger.info("=" * 60)
    
    models_dir = Path('models')
    
    if not models_dir.exists():
        logger.info(f"Creating models directory: {models_dir}")
        models_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"✓ Models directory ready: {models_dir}\n")
    return True


def run_quick_test():
    """Run a quick test to verify training setup."""
    logger.info("=" * 60)
    logger.info("5. Running Quick Training Test")
    logger.info("=" * 60)
    
    logger.info("\nStarting training with minimal epochs (1 epoch, small batch)...")
    logger.info("This may take a few minutes depending on your hardware.\n")
    
    try:
        from train_luna16 import LUNARetinaNetTrainer
        
        trainer = LUNARetinaNetTrainer(
            data_dir='data',
            annotations_file='data/annotations.csv',
            model_save_path='models/retinanet_lung_real_test.pth',
            epochs=1,  # Just 1 epoch for testing
            batch_size=1,  # Smaller batch
        )
        
        trainer.train()
        
        logger.info("\n✓ Quick test completed successfully!")
        logger.info("Training is working correctly. You can now run full training:")
        logger.info("  python train_luna16.py --epochs 10 --batch-size 2")
        
        return True
    
    except Exception as e:
        logger.error(f"Quick test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all checks."""
    logger.info("\n" + "=" * 60)
    logger.info("LUNA16 Training Setup Verification")
    logger.info("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Dataset", check_dataset),
        ("Model Directory", check_models_directory),
    ]
    
    all_passed = True
    
    for name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            logger.error(f"Error in check {name}: {e}")
            all_passed = False
    
    # Summary
    logger.info("=" * 60)
    if all_passed:
        logger.info("✓ All checks passed!")
        logger.info("\nYou can now start training:")
        logger.info("  python train_luna16.py")
        logger.info("\nOr run with custom parameters:")
        logger.info("  python train_luna16.py --epochs 10 --batch-size 2 --learning-rate 1e-4")
        
        # Ask about quick test
        logger.info("\nWould you like to run a quick test (1 epoch)?")
        logger.info("Run: python train_luna16.py --epochs 1 --batch-size 1")
    else:
        logger.error("✗ Some checks failed. Please fix the issues above.")
        logger.error("\nCommon fixes:")
        logger.error("  1. Install missing packages: pip install -r requirements.txt")
        logger.error("  2. Download LUNA16 dataset to data/ directory")
        logger.error("  3. Create/validate annotations: python prepare_luna_annotations.py")
        sys.exit(1)
    
    logger.info("=" * 60 + "\n")


if __name__ == "__main__":
    main()
