import torch
from torch.utils.data import Dataset

class LungDataset(Dataset):
    def __init__(self, images, labels=None):
        self.images = images
        self.labels = labels

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img = self.images[idx]
        img = torch.tensor(img).float().unsqueeze(0)
        if self.labels is not None:
            label = torch.tensor([self.labels[idx]]).float()
        else:
            label = torch.tensor([1.0])  # fallback
        return img, label
