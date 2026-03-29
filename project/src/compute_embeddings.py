"""Utility to compute embeddings for the training set and save them to disk.
Usage:
    python -m src.compute_embeddings --images-dir data/processed/images --out data/processed/embeddings.npz --model models/baseline_model.pth
"""
import argparse
from pathlib import Path
from PIL import Image
import numpy as np
from src import infer


def main(images_dir, out_path, model_path):
    images_dir = Path(images_dir)
    paths = sorted([p for p in images_dir.glob('**/*') if p.suffix.lower() in ('.png','.jpg','.jpeg')])
    if not paths:
        print('No images found in', images_dir)
        return
    model = None
    if infer.is_torch_available():
        model = infer.load_model(model_path, device='cpu')
    else:
        print('PyTorch not available, computing mock embeddings')
    embs = []
    for p in paths:
        img = Image.open(p)
        emb = infer.compute_embedding(model, img, device='cpu')
        embs.append(emb)
    embs = np.stack(embs)
    np.savez(out_path, emb=embs, paths=np.array([str(p) for p in paths]))
    print('Saved', out_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--images-dir', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    main(args.images_dir, args.out, args.model)