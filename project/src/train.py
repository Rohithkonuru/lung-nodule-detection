try:
    import torch
    from torch.utils.data import DataLoader
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False

if TORCH_AVAILABLE:
    from src.models.focal_loss import FocalLoss
    from src.models.unet import UNet
    from src.utils import LungDataset
    from src.config import *

    def train(train_images, train_labels, val_images=None, val_labels=None, epochs=20):
        train_dataset = LungDataset(train_images, train_labels)
        train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

        if val_images is not None and val_labels is not None:
            val_dataset = LungDataset(val_images, val_labels)
            val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)
        else:
            val_loader = None

        model = UNet(in_channels=1, out_channels=1).to(DEVICE)
        criterion = FocalLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE * 0.5)

        best_sensitivity = 0.0
        patience = 7
        patience_counter = 0

        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for imgs, labels in train_loader:
                imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
                outputs = model(imgs)
                loss = criterion(outputs, labels)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                train_loss += loss.item() * imgs.size(0)
            train_loss /= len(train_loader.dataset)

            val_loss = None
            val_sensitivity = None
            if val_loader is not None:
                model.eval()
                val_loss = 0.0
                all_preds = []
                all_labels = []
                with torch.no_grad():
                    for imgs, labels in val_loader:
                        imgs, labels = imgs.to(DEVICE), labels.to(DEVICE)
                        outputs = model(imgs)
                        loss = criterion(outputs, labels)
                        val_loss += loss.item() * imgs.size(0)
                        preds = torch.sigmoid(outputs).cpu().numpy() > 0.5
                        all_preds.extend(preds.astype(int).flatten())
                        all_labels.extend(labels.cpu().numpy().astype(int).flatten())
                val_loss /= len(val_loader.dataset)
                # Sensitivity = TP / (TP + FN)
                tp = sum((p == 1 and l == 1) for p, l in zip(all_preds, all_labels))
                fn = sum((p == 0 and l == 1) for p, l in zip(all_preds, all_labels))
                val_sensitivity = tp / (tp + fn + 1e-8)
                print(f"Epoch {epoch+1}/{epochs}, Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}, Val Sensitivity: {val_sensitivity:.4f}")
                # Early stopping
                if val_sensitivity > best_sensitivity:
                    best_sensitivity = val_sensitivity
                    patience_counter = 0
                    torch.save(model.state_dict(), "models/retinanet_best.pth")
                else:
                    patience_counter += 1
                if patience_counter >= patience:
                    print(f"Early stopping at epoch {epoch+1} (best sensitivity: {best_sensitivity:.4f})")
                    break
            else:
                print(f"Epoch {epoch+1}/{epochs}, Train Loss: {train_loss:.4f}")

        print(f"Best validation sensitivity achieved: {best_sensitivity:.4f}")
        if best_sensitivity >= 0.8:
            print("Target sensitivity > 80% achieved!")
        else:
            print("Target not reached. Consider further tuning or more data.")
else:
    def train(images):
        print("PyTorch is not available, skipping training (demo mode).")
        return
