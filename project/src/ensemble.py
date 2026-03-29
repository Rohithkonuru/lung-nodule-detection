"""Ensemble helpers: load multiple PyTorch models and compute averaged predictions."""
from typing import List
import os
from functools import lru_cache

from PIL import Image

from src import infer


@lru_cache(maxsize=1)
def _load_models_from_paths(paths: tuple):
    models = []
    for p in paths:
        try:
            m = infer.load_model(p, device='cpu') if infer.is_torch_available() else None
            models.append(m)
        except Exception:
            models.append(None)
    return models


def get_model_paths(models_dir: str) -> List[str]:
    if not os.path.isdir(models_dir):
        return []
    files = [os.path.join(models_dir, f) for f in os.listdir(models_dir) if f.endswith('.pth')]
    # filter out empty/corrupt files
    good = []
    for p in files:
        try:
            if os.path.getsize(p) > 0:
                good.append(p)
        except Exception:
            continue
    files = good
    files.sort()
    return files


def predict_ensemble(models_dir: str, pil_image: Image.Image) -> float:
    """Load all .pth models in `models_dir`, run `infer.predict` on each and return average score.

    If no models found or PyTorch unavailable, falls back to single `infer.predict(None, img)` behavior.
    """
    paths = tuple(get_model_paths(models_dir))
    if not paths:
        return infer.predict(None, pil_image, device='cpu')

    models = _load_models_from_paths(paths)
    scores = []
    for m in models:
        try:
            s = infer.predict(m, pil_image, device='cpu')
            scores.append(float(s))
        except Exception:
            continue

    if not scores:
        return infer.predict(None, pil_image, device='cpu')

    return float(sum(scores) / len(scores))
