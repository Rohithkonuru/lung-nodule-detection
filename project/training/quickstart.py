#!/usr/bin/env python3
"""
🚀 LUNA16 TRAINING QUICK START

This script provides step-by-step guidance for training RetinaNet on LUNA16.

Run with:
    python run_training_quickstart.py
"""

import subprocess
import sys
from pathlib import Path

def print_section(title):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def check_dataset():
    """Check if LUNA16 dataset is properly installed."""
    print_section("STEP 1: Check LUNA16 Dataset")
    
    data_dir = Path("data/LUNA16")
    
    if not data_dir.exists():
        print("❌ LUNA16 directory not found: data/LUNA16/")
        print("\n📥 Download LUNA16 from: https://luna16.grand-challenge.org/")
        print("\n   Instructions:")
        print("   1. Register and accept terms")
        print("   2. Download all subset files (subset0.zip - subset9.zip)")
        print("   3. Download annotations.csv")
        print("   4. Extract to: data/LUNA16/")
        print("\n   Expected structure:")
        print("   data/LUNA16/")
        print("   ├── subset0/  (contains *.mhd and *.raw files)")
        print("   ├── subset1/")
        print("   ├── ...")
        print("   └── annotations.csv")
        return False
    
    # Check for subsets
    subsets = list(data_dir.glob("subset*"))
    annotations = data_dir / "annotations.csv"
    
    print(f"✓ Found {len(subsets)} subsets")
    
    if annotations.exists():
        print(f"✓ Found annotations.csv")
    else:
        print(f"❌ Missing annotations.csv")
        return False
    
    # Count MHD files
    mhd_count = sum(1 for _ in data_dir.glob("*/*.mhd"))
    print(f"✓ Found {mhd_count} MHD files (CT scans)")
    
    return len(subsets) > 0 and annotations.exists()

def run_quick_test():
    """Run quick test training (1 epoch on small subset)."""
    print_section("STEP 2: Quick Test (1 Epoch)")
    
    print("Testing training pipeline with minimal data...")
    print("\nCommand:")
    print("  python training/train_simple.py --epochs 1 --batch-size 1 --subset 0")
    
    try:
        result = subprocess.run([
            sys.executable, "training/train_simple.py",
            "--epochs", "1",
            "--batch-size", "1",
            "--subset", "0",
            "--data-dir", "data/LUNA16",
        ], capture_output=False, text=True)
        
        if result.returncode == 0:
            print("\n✅ Quick test passed!")
            print("   Pipeline works correctly.")
            return True
        else:
            print("\n❌ Quick test failed!")
            return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def run_full_training():
    """Run full training on all subsets."""
    print_section("STEP 3: Full Training (20 Epochs)")
    
    print("Training RetinaNet on LUNA16 dataset...")
    print("\nCommand:")
    print("  python training/train_simple.py --epochs 20 --batch-size 2")
    print("\nExpected:")
    print("  - Time: 4-6 hours on GPU, 24-48 hours on CPU")
    print("  - Output: models/retinanet_lung_best.pth")
    print("  - Loss: Start ~2.0, End ~0.5-1.0")
    
    response = input("\nStart full training? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("⏭️  Skipped full training.")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, "training/train_simple.py",
            "--epochs", "20",
            "--batch-size", "2",
            "--data-dir", "data/LUNA16",
        ], capture_output=False, text=True)
        
        return result.returncode == 0
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def verify_training():
    """Verify training completed successfully."""
    print_section("STEP 4: Verify Model")
    
    model_path = Path("models/retinanet_lung_best.pth")
    
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        return False
    
    print(f"✓ Model found: {model_path}")
    print(f"✓ Size: {model_path.stat().st_size / (1024**2):.1f} MB")
    
    # Try to load
    print("\nLoading model...")
    try:
        import torch
        from torchvision.models.detection import retinanet_resnet50_fpn
        
        model = retinanet_resnet50_fpn(pretrained=False, num_classes=2)
        model.load_state_dict(torch.load(model_path))
        
        print("✓ Model loaded successfully")
        print("✓ Model is ready for inference")
        
        return True
    
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False

def deploy_model():
    """Deploy trained model to backend."""
    print_section("STEP 5: Deploy to Backend")
    
    source = Path("models/retinanet_lung_best.pth")
    dest = Path("models/finetuned/retinanet_lung_best.pth")
    
    if not source.exists():
        print(f"❌ Source model not found: {source}")
        return False
    
    # Create destination directory
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    # Copy model
    import shutil
    shutil.copy2(source, dest)
    
    print(f"✓ Model deployed: {dest}")
    print("\nNext steps:")
    print("  1. Restart backend: python backend/run_server.py")
    print("  2. Test detection: Upload CT scan via http://localhost:3000")
    print("  3. Check results: Backend logs should show detections")
    
    return True

def main():
    """Main quickstart workflow."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "🚀 LUNA16 RetinaNet Training - Quick Start".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Step 1: Check dataset
    if not check_dataset():
        print("\n" + "!" * 70)
        print("Cannot continue without LUNA16 dataset.")
        print("!" * 70)
        return
    
    # Step 2: Quick test
    if not run_quick_test():
        print("\n⚠️  Quick test failed. Check dataset and dependencies.")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response != "yes":
            return
    
    # Step 3: Full training
    success = run_full_training()
    
    if not success:
        print("\n❌ Training failed or skipped.")
        return
    
    # Step 4: Verify
    if not verify_training():
        print("\n❌ Verification failed.")
        return
    
    # Step 5: Deploy
    if deploy_model():
        print_section("✅ Training Complete!")
        print("\n🎉 SUCCESS!")
        print("   - Model trained on LUNA16")
        print("   - Deployed to backend")
        print("   - Ready for detection")

if __name__ == "__main__":
    main()
