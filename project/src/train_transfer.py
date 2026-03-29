"""Simple transfer-learning training script for classification on CT slices.

Usage (example):
    from command line or import train():
    python -m src.train_transfer --train-csv path/to/train.csv --val-csv path/to/val.csv --epochs 20

The CSV files are expected to have two columns: `path,label` where `path` points to a .mhd/.mha file and `label` is 0 or 1.
"""
import argparse
import os
from typing import List

try:
    import torch
    from torch import nn
    from torch.utils.data import Dataset, DataLoader
    from torchvision import models
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False

import numpy as np

from src.data_loader import load_ct_scan
from src.preprocessing import preprocess_scan
from src import augmentations


class CTSliceDataset(Dataset):
    def __init__(self, items: List[tuple], size: int = 224, augment: bool = False):
        """items: list of (path, label)"""
        self.items = items
        self.size = size
        self.augment = augment

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        path, label = self.items[idx]
        scan = load_ct_scan(path)
        # preprocess volume -> (slices, H, W)
        vol = preprocess_scan(scan, size=self.size)
        # pick central slice for classification
        slice_img = vol[len(vol) // 2]
        # augment
        if self.augment:
            slice_img = augmentations.compose_augmentations(slice_img)
        # convert to tensor-like numpy (C,H,W) with single channel
        arr = np.expand_dims(slice_img, axis=0).astype(np.float32)
        return torch.from_numpy(arr), torch.tensor(label, dtype=torch.float32)


def build_model(pretrained: bool = True):
    # Use ResNet18 as a lightweight strong baseline
    model = models.resnet18(pretrained=pretrained)
    # Adjust first conv to accept 1 channel
    conv1 = model.conv1
    model.conv1 = nn.Conv2d(1, conv1.out_channels, kernel_size=conv1.kernel_size,
                            stride=conv1.stride, padding=conv1.padding, bias=conv1.bias is not None)
    # Replace final layer for binary classification
    model.fc = nn.Linear(model.fc.in_features, 1)
    return model


def parse_csv(path: str):
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue
            p = parts[0].strip()
            lbl = int(parts[1].strip())
            items.append((p, lbl))
    return items


def train_loop(model, device, train_loader, val_loader=None, epochs=10, lr=1e-4, out_path='models/transfer_best.pth'):
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    best_val_loss = float('inf')
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device).unsqueeze(1)
            preds = model(xb)
            loss = criterion(preds, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            running_loss += loss.item() * xb.size(0)
        train_loss = running_loss / len(train_loader.dataset)

        val_loss = None
        if val_loader is not None:
            model.eval()
            running = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb = xb.to(device)
                    yb = yb.to(device).unsqueeze(1)
                    preds = model(xb)
                    loss = criterion(preds, yb)
                    running += loss.item() * xb.size(0)
            val_loss = running / len(val_loader.dataset)
            scheduler.step(val_loss)
            print(f"Epoch {epoch+1}/{epochs}  Train Loss: {train_loss:.4f}  Val Loss: {val_loss:.4f}")
        else:
            print(f"Epoch {epoch+1}/{epochs}  Train Loss: {train_loss:.4f}")

        # save best
        if val_loss is not None and val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), out_path)
    # final save
    torch.save(model.state_dict(), out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--train-csv', required=True)
    parser.add_argument('--val-csv', required=False)
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--size', type=int, default=224)
    parser.add_argument('--out', type=str, default='models/transfer_best.pth')
    args = parser.parse_args()

    if not TORCH_AVAILABLE:
        print('PyTorch not available in this environment.')
        return

    train_items = parse_csv(args.train_csv)
    val_items = parse_csv(args.val_csv) if args.val_csv else None

    train_ds = CTSliceDataset(train_items, size=args.size, augment=True)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)

    val_loader = None
    if val_items:
        val_ds = CTSliceDataset(val_items, size=args.size, augment=False)
        val_loader = DataLoader(val_ds, batch_size=args.batch_size)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = build_model(pretrained=True).to(device)

    train_loop(model, device, train_loader, val_loader=val_loader, epochs=args.epochs, lr=args.lr, out_path=args.out)


if __name__ == '__main__':
    main()
