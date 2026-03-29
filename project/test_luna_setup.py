#!/usr/bin/env python3
"""
Simple test script to verify LUNA16 training setup works correctly.
Runs minimal training to validate data loading, model, and loss computation.
"""

import sys
import torch
from pathlib import Path


def test_imports():
    """Test if all required packages are available."""
    print("Testing imports...")
    try:
        import torch
        import torchvision
        import SimpleITK
        import pandas
        import numpy
        print("✓ All imports successful\n")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_dataset():
    """Test if dataset can be loaded."""
    print("Testing dataset loading...")
    try:
        from training.dataset import LUNADataset
        
        dataset = LUNADataset(
            data_dir='data',
            annotations_file='data/annotations.csv',
            subset=None,
            cache=False
        )
        
        print(f"✓ Dataset loaded: {len(dataset)} scans")
        
        # Try loading one sample
        print("Loading sample 0...")
        img, target = dataset[0]
        
        print(f"  Image shape: {img.shape}")
        print(f"  Image dtype: {img.dtype}")
        print(f"  Image range: [{img.min():.3f}, {img.max():.3f}]")
        print(f"  Boxes shape: {target['boxes'].shape}")
        print(f"  Labels shape: {target['labels'].shape}")
        print(f"  Series ID: {target.get('series_id', 'N/A')}")
        print("✓ Sample loaded successfully\n")
        
        return True
    except Exception as e:
        print(f"✗ Dataset test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model():
    """Test if RetinaNet model can be created."""
    print("Testing model creation...")
    try:
        from torchvision.models.detection import retinanet_resnet50_fpn
        from torchvision.models.detection.retinanet import RetinaNetClassificationHead
        
        print("Loading pretrained RetinaNet...")
        model = retinanet_resnet50_fpn(pretrained=True)
        
        # Modify for 2 classes
        num_classes = 2
        in_channels = model.backbone.out_channels
        num_anchors = model.head.classification_head.num_anchors
        
        model.head.classification_head = RetinaNetClassificationHead(
            in_channels=in_channels,
            num_anchors=num_anchors,
            num_classes=num_classes,
            prior_probability=0.01
        )
        
        print(f"✓ Model created successfully")
        print(f"  Backbone: ResNet50-FPN")
        print(f"  Classes: {num_classes}")
        print(f"  Total parameters: {sum(p.numel() for p in model.parameters()):,}")
        print(f"  Trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}\n")
        
        return model
    except Exception as e:
        print(f"✗ Model test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_forward_pass(model):
    """Test if forward pass works with dummy data."""
    print("Testing forward pass...")
    try:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Using device: {device}")
        
        model = model.to(device)
        model.eval()
        
        # Create dummy batch
        dummy_img = torch.rand(3, 512, 512, device=device)  # 3-channel image
        dummy_boxes = torch.tensor([[10, 10, 50, 50], [100, 100, 150, 150]], 
                                   dtype=torch.float32, device=device)
        dummy_labels = torch.tensor([1, 1], dtype=torch.int64, device=device)
        
        # Forward pass (inference mode)
        with torch.no_grad():
            output = model([dummy_img])
        
        print(f"✓ Forward pass successful")
        print(f"  Output predictions: {len(output)}")
        print(f"  Predicted boxes: {output[0]['boxes'].shape}")
        print(f"  Predicted scores: {output[0]['scores'].shape}\n")
        
        return True
    except Exception as e:
        print(f"✗ Forward pass test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_training_step(model):
    """Test if training step works."""
    print("Testing training step...")
    try:
        from training.dataset import LUNADataset
        import torch.optim as optim
        
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = model.to(device)
        model.train()
        
        # Load one sample
        dataset = LUNADataset(
            data_dir='data',
            annotations_file='data/annotations.csv',
            cache=False
        )
        
        img, target = dataset[0]
        
        # Process image (single channel → 3 channels)
        if img.shape[0] == 1:
            img = img.repeat(3, 1, 1)
        
        # Normalize
        if img.max() > 1.0:
            img = img / 255.0
        
        # Prepare target
        t = {}
        if len(target['boxes']) > 0:
            t['boxes'] = target['boxes'].to(device)
            t['labels'] = target['labels'].to(device)
        else:
            t['boxes'] = torch.zeros((0, 4), dtype=torch.float32, device=device)
            t['labels'] = torch.zeros((0,), dtype=torch.int64, device=device)
        
        # Forward pass
        img = img.to(device)
        loss_dict = model([img], [t])
        losses = sum(loss for loss in loss_dict.values())
        
        print(f"✓ Training step successful")
        print(f"  Loss components: {list(loss_dict.keys())}")
        print(f"  Total loss: {losses.item():.4f}")
        print(f"  Loss dict:")
        for k, v in loss_dict.items():
            print(f"    {k}: {v.item():.4f}")
        print()
        
        return True
    except Exception as e:
        print(f"✗ Training step test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("LUNA16 Training Setup Test")
    print("=" * 60 + "\n")
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Imports
    tests_total += 1
    if test_imports():
        tests_passed += 1
    
    # Test 2: Dataset loading
    tests_total += 1
    if test_dataset():
        tests_passed += 1
    
    # Test 3: Model creation
    tests_total += 1
    model = test_model()
    if model is not None:
        tests_passed += 1
    
    # Test 4: Forward pass
    if model is not None:
        tests_total += 1
        if test_forward_pass(model):
            tests_passed += 1
    
    # Test 5: Training step
    if model is not None:
        tests_total += 1
        if test_training_step(model):
            tests_passed += 1
    
    # Summary
    print("=" * 60)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    print("=" * 60)
    
    if tests_passed == tests_total:
        print("✓ ALL TESTS PASSED - Ready to train!")
        print("\nRun: python train_luna16.py")
        return 0
    else:
        print("✗ Some tests failed - check output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
