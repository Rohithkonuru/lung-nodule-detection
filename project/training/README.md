# LUNA16 Training Infrastructure

Complete training pipeline for RetinaNet nodule detection on LUNA16 dataset.

## Quick Start

### 1. Download LUNA16 Dataset

```bash
# Run download instructions
python utils.py
```

Visit https://luna16.grand-challenge.org/ and download the full dataset (~100GB).

Extract to `data/LUNA16/` with this structure:
```
data/LUNA16/
├── subset0/
├── subset1/
├── ...
├── subset9/
└── annotations.csv
```

### 2. Verify Installation

```bash
python -c "from utils import check_luna16_installation; check_luna16_installation('data/LUNA16')"
```

Expected output:
```
✓ Found 10 subsets
✓ Found XXX MHD files
✓ Annotations file loaded (NNN nodules)
```

### 3. Train RetinaNet

```bash
# Quick test (1 subset, 5 epochs)
python train.py --data-dir data/LUNA16 --epochs 5 --batch-size 2

# Full training (recommended: 20 epochs)
python train.py --data-dir data/LUNA16 --epochs 20

# Custom configuration
python train.py \
    --data-dir data/LUNA16 \
    --output-dir models/custom \
    --epochs 30 \
    --batch-size 4 \
    --learning-rate 5e-5
```

## Dataset

**LUNA16** (Lung Nodule Analysis 16):
- **Scans**: 888 low-dose CT scans
- **Nodules**: ~1,200 annotated nodules (diameter 3-30mm)
- **Size**: ~100GB (compressed)
- **Split**: Subsets 0-9 (custom train/val split per subset)

### Annotations Format

`annotations.csv` columns:
```
seriesuid,coordX,coordY,coordZ,diameter_mm
1.3.6.1.4.1.14519.5.2.1.XXXX,x,y,z,d
...
```

- **seriesuid**: Unique scan identifier
- **coordX/Y/Z**: 3D nodule center (mm)
- **diameter_mm**: Nodule diameter (3-30mm)

## File Structure

```
training/
├── dataset.py       # LUNA16 dataset loader with real bbox extraction
├── train.py        # Training script with validation and checkpointing
├── utils.py        # Utility functions (IoU, NMS, metrics)
└── README.md       # This file
```

## Dataset Loader (dataset.py)

### LUNADataset Class

Loads LUNA16 with real bounding box annotations.

**Features**:
- Real bbox extraction from annotation centers/diameters
- Automatic spacing conversion (mm to pixel coordinates)
- Per-slice annotation grouping (3D → 2D)
- Slice caching for performance
- Middle slice extraction strategy

**Usage**:

```python
from dataset import LUNADataset, get_luna_dataloader

# Create dataset
dataset = LUNADataset(
    data_dir='data/LUNA16',
    annotations_file='data/LUNA16/annotations.csv',
    subset='0'  # Train on subset 0
)

print(f"Dataset size: {len(dataset)} series")

# Get single item
image, boxes, labels = dataset[0]
print(f"Image shape: {image.shape}")  # [1, 512, 512]
print(f"Boxes shape: {boxes.shape}")  # [num_nodules, 4]
print(f"Labels shape: {labels.shape}") # [num_nodules]

# Create dataloader
train_loader = get_luna_dataloader(
    data_dir='data/LUNA16',
    annotations_file='data/LUNA16/annotations.csv',
    subset='0',
    batch_size=4,
    num_workers=0
)

# Iterate over batches
for images, boxes_list in train_loader:
    print(f"Batch images shape: {images.shape}")  # [batch, 1, 512, 512]
    # boxes_list is list of tensors (variable num boxes per image)
    break
```

### Real Bounding Box Extraction

The dataset accurately extracts bounding boxes from annotations:

```
Annotation: center=(x_mm, y_mm, z_mm), diameter=d_mm

1. Get slice at z_mm
2. Convert from mm to pixels using spacing: pixel_coord = mm_coord / spacing_mm
3. Calculate box: 
   - radius_px = (diameter_mm / 2) / spacing_mm
   - box = [x - r, y - r, x + r, y + r]
4. Clip to image bounds: [0, 512]
```

Example logging output:
```
[dataset] Series 1.3.6.1.4.1.14519.5.2.1.XXXX:
  - Spacing: [0.7mm, 0.7mm, 0.5mm]
  - Slice 185: 2 nodules
    - Nodule 1: center=(256, 300)px, radius=25px
    - Nodule 2: center=(180, 140)px, radius=18px
```

## Training Script (train.py)

### RetinaNetTrainer Class

Complete training loop with validation and checkpointing.

**Features**:
- Per-epoch training with gradient clipping
- Validation phase with mAP calculation
- Best checkpoint saving
- Learning rate scheduling (StepLR)
- Comprehensive logging

**Usage**:

```bash
# Basic training
python train.py --data-dir data/LUNA16 --epochs 20

# With custom output directory
python train.py \
    --data-dir data/LUNA16 \
    --output-dir models/v2 \
    --epochs 30

# Batch size and learning rate tuning
python train.py \
    --data-dir data/LUNA16 \
    --batch-size 4 \
    --learning-rate 2e-4 \
    --epochs 20
```

### Training Loop

```
Epoch 1/20
├─ Training:
│  ├─ Batch 1: Loss=5.234
│  ├─ Batch 2: Loss=3.892
│  └─ Epoch Loss: 4.563
├─ Validation:
│  ├─ mAP@0.5: 0.234
│  └─ mAP@0.75: 0.102
└─ Saved checkpoint: models/retinanet_lung_epoch_1.pth (new best!)
```

### Output Files

After training, check `models/`:

```
models/
├── retinanet_lung_best.pth      # Best checkpoint (lowest val loss)
├── retinanet_lung_epoch_1.pth   # Checkpoints for each epoch
├── retinanet_lung_epoch_2.pth
└── training_log.csv             # Metrics per epoch
```

## Configuration

### Default Hyperparameters

```python
{
    'epochs': 20,
    'batch_size': 2,        # Adjust for GPU memory (4-8 with VRAM)
    'learning_rate': 1e-4,  # 1e-4 for new train, 1e-5 for finetune
    'weight_decay': 1e-4,
    'num_workers': 0,       # Increase for faster data loading
    'device': 'cuda' if torch.cuda.is_available() else 'cpu'
}
```

### Recommended Settings by Use Case

**Quick Iteration** (test code, ~5min):
```bash
python train.py --data-dir data/LUNA16 --epochs 1 --batch-size 2
```

**Weekend Training** (~24 hours):
```bash
python train.py --data-dir data/LUNA16 --epochs 20 --batch-size 4
```

**Production** (multi-GPU):
```bash
# Modify train.py to use DataParallel
python train.py --data-dir data/LUNA16 --epochs 30 --batch-size 8
```

## Utility Functions (utils.py)

### NMS (Non-Maximum Suppression)

Remove overlapping boxes:

```python
from utils import nms

keep_indices = nms(
    boxes=[[0,0,100,100], [10,10,90,90]],  # IoU=0.81
    scores=[0.9, 0.8],
    iou_threshold=0.5
)
# Returns [0] - removes box 1 due to high IoU with box 0
```

### IoU Calculation

```python
from utils import calculate_iou

iou = calculate_iou(
    box1=[0, 0, 100, 100],
    box2=[50, 50, 150, 150]
)
# Returns 0.14
```

### Metrics Tracking

```python
from utils import AverageMeter

loss_meter = AverageMeter('Loss')
loss_meter.update(5.2)
loss_meter.update(4.8)
print(loss_meter)  # Loss: 5.0000
```

## Validation Strategy

The training script uses a recommended split:

- **Training**: Subsets 0-8 (888 × 0.9 ≈ 799 scans)
- **Validation**: Subset 9 (888 × 0.1 ≈ 89 scans)

This provides ~1,000 training nodules and ~100 validation nodules.

For production, consider:
1. **K-fold validation**: Train 10 models with different test folds
2. **External validation**: Test on independent dataset
3. **Cross-dataset evaluation**: LIDC-IDRI, NDSB

## Performance Benchmarks

Expected performance on LUNA16 validation set:

| Metric | Value | Notes |
|--------|-------|-------|
| mAP@0.5 | ~0.50 | Depending on diameter cutoff |
| mAP@0.75 | ~0.25 | Stricter IoU threshold |
| Sensitivity @ 4 FP/scan | ~0.80 | Official LUNA16 metric |
| Training Time | 4-6 hrs | Single GPU (1 epoch ≈ 12min) |

## Troubleshooting

### Out of Memory
```bash
# Reduce batch size
python train.py --data-dir data/LUNA16 --batch-size 1
```

### Slow Data Loading
```python
# In train.py, increase num_workers
train_loader = get_luna_dataloader(
    ...,
    num_workers=4  # Use multiple processes
)
```

### Missing Annotations
```bash
# Verify dataset installation
python -c "from utils import check_luna16_installation; check_luna16_installation('data/LUNA16')"
```

### NaN Loss
```bash
# Increase learning rate warmup or reduce LR
python train.py --data-dir data/LUNA16 --learning-rate 5e-5
```

## Integration with Production System

After training, copy the best model to production:

```bash
# Copy best checkpoint to models/ for detection
cp models/retinanet_lung_best.pth ../models/retinanet_lung_finetuned.pth

# Update config to use new model
# In backend/app/core/config.py:
# RETINANET_CHECKPOINT = "models/retinanet_lung_finetuned.pth"

# Restart backend
python ../backend/run_server.py
```

## Citation

**LUNA16 Dataset**:
```
Setio AAA, Traverso A, de Bel T, et al. Validation, comparison, and 
combination of algorithms for automatic detection of pulmonary nodules 
in computed tomography images: the LUNA16 challenge. Medical Image 
Analysis. 2017;42:1-13.
```

**RetinaNet**:
```
Lin TY, Goyal P, Girshick R, He K, Dollár P. Focal Loss for Dense Object 
Detection. In: IEEE International Conference on Computer Vision (ICCV); 
2017.
```

## Next Steps

1. ✓ Created training infrastructure
2. → Download LUNA16 dataset (https://luna16.grand-challenge.org/)
3. → Run training: `python train.py --data-dir data/LUNA16 --epochs 20`
4. → Evaluate on validation set
5. → Deploy best model to backend

Questions? Check logs in `models/training_log.csv` for detailed metrics per epoch.
