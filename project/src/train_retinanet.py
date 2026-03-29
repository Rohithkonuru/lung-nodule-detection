import os
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from src.models.retinanet import SimpleRetinaNet
from src.models.focal_loss import FocalLoss
from src.data_loader import load_ct_scan
from src.preprocessing import preprocess_scan



import random
from torchvision import transforms
from sklearn.model_selection import train_test_split

class LunaDataset(Dataset):
    def __init__(self, csv_path, annotations_path, size=256, augment=True):
        self.data = pd.read_csv(csv_path, header=None)
        self.annotations = pd.read_csv(annotations_path)
        self.size = size
        self.augment = augment
        self.scan_map = {}
        for idx, row in self.annotations.iterrows():
            uid = row['seriesuid']
            if uid not in self.scan_map:
                self.scan_map[uid] = []
            self.scan_map[uid].append((row['coordX'], row['coordY'], row['coordZ'], row['diameter_mm']))

        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(15),
        ]) if augment else transforms.ToTensor()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        scan_path = self.data.iloc[idx, 0]
        uid = os.path.basename(scan_path).replace('.mhd', '')
        scan = load_ct_scan(scan_path)
        processed = preprocess_scan(scan, size=self.size)
        # Use all slices for training
        slice_idx = random.randint(0, processed.shape[0] - 1)
        img = processed[slice_idx]
        img = np.expand_dims(img, axis=0)  # (1, H, W)
        img = torch.tensor(img, dtype=torch.float32)
        if self.augment:
            img = self.transform(img)
        # Find nodule boxes for this slice
        boxes = []
        if uid in self.scan_map:
            for x, y, z, d in self.scan_map[uid]:
                # Map nodule Z to slice index
                slice_z = int(z)
                if abs(slice_z - slice_idx) < 2:  # Allow +/- 2 slices
                    cx, cy = self.size // 2, self.size // 2
                    w = h = int(d)
                    x1 = cx - w // 2
                    y1 = cy - h // 2
                    x2 = cx + w // 2
                    y2 = cy + h // 2
                    boxes.append([x1, y1, x2, y2, 1.0])
        return img, torch.tensor(boxes, dtype=torch.float32)

def collate_fn(batch):
    imgs, targets = zip(*batch)
    imgs = torch.stack(imgs)
    return imgs, targets


    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    # Split train/val
    df = pd.read_csv('train_luna.csv', header=None)
    train_idx, val_idx = train_test_split(df.index, test_size=0.2, random_state=42)
    train_csv = df.iloc[train_idx]
    val_csv = df.iloc[val_idx]
    train_csv.to_csv('train_split.csv', index=False, header=False)
    val_csv.to_csv('val_split.csv', index=False, header=False)

    train_dataset = LunaDataset(
        csv_path='train_split.csv',
        annotations_path='luna dataset/annotations.csv',
        size=256,
        augment=True
    )
    val_dataset = LunaDataset(
        csv_path='val_split.csv',
        annotations_path='luna dataset/annotations.csv',
        size=256,
        augment=False
    )
    train_loader = DataLoader(train_dataset, batch_size=4, shuffle=True, collate_fn=collate_fn)
    val_loader = DataLoader(val_dataset, batch_size=4, shuffle=False, collate_fn=collate_fn)

    model = SimpleRetinaNet(num_classes=1, num_anchors=5, in_channels=1).to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3, verbose=True)
    criterion = FocalLoss()
    num_epochs = 30
    best_val_loss = float('inf')
    patience = 7
    patience_counter = 0

    def iou(boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
        return iou

    for epoch in range(num_epochs):
        model.train()
        epoch_loss = 0.0
        for imgs, targets in train_loader:
            imgs = imgs.to(device)
            cls_outs, box_outs = model(imgs)
            loss = 0.0
            for cls in cls_outs:
                loss += criterion(cls, torch.zeros_like(cls))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        avg_loss = epoch_loss / len(train_loader)

        # Validation
        model.eval()
        val_loss = 0.0
        all_pred_boxes = []
        all_gt_boxes = []
        with torch.no_grad():
            for imgs, targets in val_loader:
                imgs = imgs.to(device)
                cls_outs, box_outs = model(imgs)
                loss = 0.0
                for cls in cls_outs:
                    loss += criterion(cls, torch.zeros_like(cls))
                val_loss += loss.item()
                # For metrics: collect predicted and gt boxes
                for t in targets:
                    all_gt_boxes.extend(t.cpu().numpy())
                # For demo: use random boxes as predictions
                for cls in cls_outs:
                    pred_boxes = (cls > 0.5).nonzero(as_tuple=True)
                    for idx in range(len(pred_boxes[0])):
                        all_pred_boxes.append([0,0,10,10,1.0])  # Placeholder
        avg_val_loss = val_loss / len(val_loader)
        scheduler.step(avg_val_loss)

        # Compute metrics
        TP = 0
        FP = 0
        FN = 0
        for gt in all_gt_boxes:
            matched = False
            for pred in all_pred_boxes:
                if iou(gt[:4], pred[:4]) > 0.5:
                    matched = True
                    break
            if matched:
                TP += 1
            else:
                FN += 1
        FP = max(0, len(all_pred_boxes) - TP)
        recall = TP / (TP + FN + 1e-6)
        precision = TP / (TP + FP + 1e-6)
        print(f'Epoch {epoch+1}/{num_epochs}, Train Loss: {avg_loss:.4f}, Val Loss: {avg_val_loss:.4f}, Recall: {recall:.3f}, Precision: {precision:.3f}')

        # Early stopping
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            torch.save({'model_state_dict': model.state_dict()}, f'retinanet_best.pth')
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print('Early stopping triggered.')
                break
    print('Training complete. Best model saved as retinanet_best.pth')

if __name__ == '__main__':
    train_retinanet()
