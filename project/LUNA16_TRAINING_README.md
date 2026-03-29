# LUNA16 PyTorch Training Guide

Complete PyTorch training script for lung nodule detection using the LUNA16 dataset with RetinaNet.

## 📋 Quick Start

```bash
# 1. Verify your setup
python setup_luna_training.py

# 2. Prepare annotations (if needed)
python prepare_luna_annotations.py --validate-only

# 3. Start training
python train_luna16.py
```

## 🎯 What You Need

### Dataset
The LUNA16 dataset should be organized as:
```
data/
  subset0/
    *.mhd (CT volume metadata)
    *.raw (volumetric data)
  subset1/
  subset2/
  ...
  annotations.csv (nodule locations)
```

### Annotations Format
`annotations.csv` must contain:
```
seriesuid,coordX,coordY,coordZ,diameter_mm
1.2.840.113619...,0.5,10.2,-30.1,8.5
1.2.840.113619...,5.2,15.3,-25.0,6.2
...
```

- **seriesuid**: Unique CT scan identifier
- **coordX, coordY, coordZ**: Nodule center position in world coordinates (mm)
- **diameter_mm**: Nodule diameter in millimeters

## 📁 Key Files

| File | Purpose |
|------|---------|
| `train_luna16.py` | Main training script |
| `prepare_luna_annotations.py` | Prepare/validate annotations |
| `setup_luna_training.py` | Verify environment & dataset |
| `training/dataset.py` | LUNA16 dataset loader (existing) |

## 🚀 Training Commands

### Basic Training (10 epochs, batch size 2)
```bash
python train_luna16.py
```

### Custom Configuration
```bash
python train_luna16.py \
  --epochs 20 \
  --batch-size 4 \
  --learning-rate 5e-5 \
  --device cuda
```

### Test Run (1 epoch)
```bash
python train_luna16.py --epochs 1 --batch-size 1
```

## 🔧 Available Options

```
--data-dir              Path to LUNA16 dataset (default: data)
--annotations           Path to annotations.csv (default: data/annotations.csv)
--model-save            Where to save model (default: models/retinanet_lung_real.pth)
--epochs                Number of training epochs (default: 10)
--batch-size            Batch size (default: 2)
--learning-rate         Learning rate (default: 1e-4)
--device                Device: cuda or cpu (auto-detected by default)
```

## 📊 Training Details

### Model Architecture
- **Base Model**: RetinaNet with ResNet50 backbone + FPN
- **Classes**: 2 (background + lung nodule)
- **Input**: Single 2D CT slices (from 3D volumes)
- **Output**: Bounding box coordinates and class predictions

### Data Processing
1. **3D → 2D Conversion**: Extracts middle slice from 3D CT volume
2. **Normalization**: Pixel values normalized to [0, 1]
3. **Bounding Box**: World coordinates (mm) converted to pixel space
4. **Channel Expansion**: Single-channel CT → 3-channel for RetinaNet

### Bounding Box Conversion

From annotations:
```
center: (x_mm, y_mm, z_mm)
diameter_mm: d
```

To pixel coordinates:
```
center_pixel = center_mm / spacing
radius = diameter_mm / 2 / spacing

x1 = center_x - radius
y1 = center_y - radius
x2 = center_x + radius
y2 = center_y + radius
```

### Training Configuration
- **Optimizer**: Adam (lr=1e-4)
- **Loss**: RetinaNet focal loss + smooth L1 regression
- **GPU Support**: Automatic CUDA detection
- **Batch Size**: 2 (configurable)
- **Epochs**: 10 (configurable)

## 🔍 Troubleshooting

### "Annotations file not found"
```bash
# Create dummy annotations for testing
python prepare_luna_annotations.py --create-dummy

# Validate existing annotations
python prepare_luna_annotations.py --validate-only
```

### "No subset directories found"
Ensure your data structure matches:
```
data/
  subset0/
    <seriesuid>.mhd
    <seriesuid>.raw
```

### "CUDA out of memory"
Reduce batch size:
```bash
python train_luna16.py --batch-size 1
```

### "No nodules found in dataset"
Check annotations.csv format and that series UIDs match filenames.

## 📈 Monitoring Training

The script prints:
- Dataset size and nodule count
- Loss per epoch
- Model checkpoints saved
- GPU memory usage (with CUDA)

Example output:
```
Epoch 1/10
  Batch 5/10, Loss: 2.1523
  Batch 10/10, Loss: 1.8945
Epoch 1 completed - Average Loss: 1.9234
Model checkpoint saved: models/retinanet_lung_real_epoch_1.pth
```

## 💾 Output Files

Training saves:
- `models/retinanet_lung_real_epoch_X.pth` - Checkpoint after each epoch
- `models/retinanet_lung_real.pth` - Final trained model

Load saved model:
```python
import torch
from torchvision.models.detection import retinanet_resnet50_fpn

model = retinanet_resnet50_fpn(pretrained=False, num_classes=2)
model.load_state_dict(torch.load('models/retinanet_lung_real.pth'))
model.eval()
```

## 🛠️ Advanced Usage

### Custom Dataset Path
```bash
python train_luna16.py \
  --data-dir /path/to/LUNA16 \
  --annotations /path/to/annotations.csv
```

### Training on CPU Only
```bash
python train_luna16.py --device cpu --batch-size 1
```

### Resume from Checkpoint
The script validates 3D → 2D conversion and bounding box alignment in `training/dataset.py`:

```python
# Load existing model and continue training
from torch import load
from train_luna16 import LUNARetinaNetTrainer

trainer = LUNARetinaNetTrainer()
# Load checkpoint weights
trainer.model.load_state_dict(load('models/retinanet_lung_real_epoch_5.pth'))
trainer.train()
```

## ✅ Requirements

- Python 3.8+
- PyTorch 2.0+
- TorchVision 0.15+
- SimpleITK
- Pandas
- NumPy

Install with:
```bash
pip install -r requirements.txt
```

## 📝 Dataset Verification

Run setup script to verify everything:
```bash
python setup_luna_training.py
```

This checks:
1. Python version
2. Required packages
3. Dataset structure
4. Annotations format
5. Can save models

## 🐛 Debug Mode

For detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
python train_luna16.py
```

## 📚 References

- [LUNA16 Challenge](https://luna16.grand-challenge.org/)
- [RetinaNet Paper](https://arxiv.org/abs/1708.02002)
- [PyTorch Detection Docs](https://pytorch.org/vision/stable/models.html#detection)
- [SimpleITK Documentation](https://simpleitk.readthedocs.io/)

## 📧 Support

If training fails:
1. Run `python setup_luna_training.py` to diagnose
2. Check `training/dataset.py` for dataset loading details
3. Verify annotations match dataset files
4. Reduce batch size if memory issues occur

---

**Status**: ✅ Complete, production-ready training pipeline
**Last Updated**: 2026-03-28
