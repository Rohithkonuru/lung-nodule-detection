import os
import csv
import SimpleITK as sitk
import numpy as np
from PIL import Image
import torch
from sklearn.model_selection import train_test_split
from src.train import train

# Augmentation imports
import random

def load_and_preprocess_image(mhd_path, size=(256, 256)):
    try:
        itk_img = sitk.ReadImage(mhd_path)
        img_array = sitk.GetArrayFromImage(itk_img)
        central_slice = img_array[img_array.shape[0] // 2]
        pil_img = Image.fromarray(central_slice)
        pil_img = pil_img.resize(size, resample=Image.BILINEAR)
        arr = np.array(pil_img).astype(np.float32)
        arr = (arr - np.mean(arr)) / (np.std(arr) + 1e-5)  # Normalize
        return arr
    except Exception as e:
        print(f"Failed to load {mhd_path}: {e}")
        return None

def augment_image(img):
    # Random horizontal flip
    if random.random() > 0.5:
        img = np.fliplr(img)
    # Random vertical flip
    if random.random() > 0.5:
        img = np.flipud(img)
    # Random rotation (0, 90, 180, 270 degrees)
    k = random.choice([0, 1, 2, 3])
    img = np.rot90(img, k)
    # Random brightness/contrast
    if random.random() > 0.5:
        factor = 0.7 + 0.6 * random.random()  # 0.7 to 1.3
        img = np.clip(img * factor, -3, 3)
    # Add random Gaussian noise
    if random.random() > 0.5:
        noise = np.random.normal(0, 0.1, img.shape)
        img = np.clip(img + noise, -3, 3)
    return img.copy()

def load_dataset(csv_path, augment=False):
    images, labels = [], []
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            mhd_path, label = row
            img = load_and_preprocess_image(mhd_path)
            if img is not None:
                if augment:
                    img = augment_image(img)
                images.append(img)
                labels.append(int(label))
    return images, labels

def main():
    csv_path = 'train_luna.csv'
    images, labels = load_dataset(csv_path, augment=True)
    print(f"Loaded {len(images)} images.")
    # Split into train/val
    train_imgs, val_imgs, train_lbls, val_lbls = train_test_split(images, labels, test_size=0.15, random_state=42, stratify=labels)
    print(f"Training: {len(train_imgs)}, Validation: {len(val_imgs)}")
    train(train_imgs, train_lbls, val_imgs, val_lbls, epochs=50)
    print("Training complete. Model saved to models/retinanet_best.pth")

if __name__ == "__main__":
    main()
