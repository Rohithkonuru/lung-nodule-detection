import random
from typing import Tuple, Optional

import numpy as np
from PIL import Image, ImageEnhance


def _to_pil(arr: np.ndarray) -> Image.Image:
    arr = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((arr * 255).astype(np.uint8))


def _to_np(im: Image.Image) -> np.ndarray:
    return np.array(im).astype(np.float32) / 255.0


def random_flip(slice_img: np.ndarray, p: float = 0.5) -> np.ndarray:
    if random.random() < p:
        return np.fliplr(slice_img).copy()
    return slice_img


def random_rotate(slice_img: np.ndarray, max_angle: float = 15.0, p: float = 0.5) -> np.ndarray:
    if random.random() >= p:
        return slice_img
    angle = random.uniform(-max_angle, max_angle)
    im = _to_pil(slice_img)
    im = im.rotate(angle, resample=Image.BILINEAR)
    return _to_np(im)


def random_brightness_contrast(slice_img: np.ndarray, brightness: float = 0.15, contrast: float = 0.15, p: float = 0.5) -> np.ndarray:
    if random.random() >= p:
        return slice_img
    im = _to_pil(slice_img)
    if brightness > 0:
        factor = 1.0 + random.uniform(-brightness, brightness)
        im = ImageEnhance.Brightness(im).enhance(factor)
    if contrast > 0:
        factor = 1.0 + random.uniform(-contrast, contrast)
        im = ImageEnhance.Contrast(im).enhance(factor)
    return _to_np(im)


def random_noise(slice_img: np.ndarray, sigma: float = 0.02, p: float = 0.5) -> np.ndarray:
    if random.random() >= p:
        return slice_img
    noise = np.random.normal(0.0, sigma, slice_img.shape).astype(np.float32)
    out = slice_img + noise
    return np.clip(out, 0.0, 1.0)


def random_zoom(slice_img: np.ndarray, min_zoom: float = 0.9, max_zoom: float = 1.1, p: float = 0.5) -> np.ndarray:
    if random.random() >= p:
        return slice_img
    z = random.uniform(min_zoom, max_zoom)
    h, w = slice_img.shape
    im = _to_pil(slice_img)
    new_w = max(1, int(w * z))
    new_h = max(1, int(h * z))
    im = im.resize((new_w, new_h), resample=Image.BILINEAR)
    # center crop or pad back to original
    im_np = np.array(im).astype(np.float32) / 255.0
    out = np.zeros((h, w), dtype=np.float32)
    if new_h >= h and new_w >= w:
        # center crop
        start_y = (new_h - h) // 2
        start_x = (new_w - w) // 2
        out = im_np[start_y:start_y + h, start_x:start_x + w]
    else:
        # place centered
        start_y = (h - new_h) // 2
        start_x = (w - new_w) // 2
        out[start_y:start_y + new_h, start_x:start_x + new_w] = im_np
    return np.clip(out, 0.0, 1.0)


def compose_augmentations(slice_img: np.ndarray, probs: Optional[dict] = None) -> np.ndarray:
    """Apply a sequence of augmentations to a single 2D slice.

    Args:
        slice_img: float32 array in range [0,1]
        probs: optional dict with probabilities for each augmentation
    """
    if probs is None:
        probs = dict(flip=0.5, rotate=0.5, bc=0.5, noise=0.3, zoom=0.3)

    out = slice_img
    out = random_flip(out, p=probs.get('flip', 0.5))
    out = random_rotate(out, p=probs.get('rotate', 0.5))
    out = random_brightness_contrast(out, p=probs.get('bc', 0.5))
    out = random_noise(out, p=probs.get('noise', 0.3))
    out = random_zoom(out, p=probs.get('zoom', 0.3))
    return out


def augment_volume(scan: np.ndarray, per_slice: bool = True, probs: Optional[dict] = None, n_augment: int = 1) -> np.ndarray:
    """Return augmented volume(s).

    If `n_augment` > 1, returns an array with shape (n_augment, slices, H, W).
    """
    if n_augment <= 1:
        n_augment = 1

    slices = scan.shape[0]
    h = scan.shape[1]
    w = scan.shape[2]

    results = []
    for _ in range(n_augment):
        if per_slice:
            out = np.zeros_like(scan, dtype=np.float32)
            for i in range(slices):
                out[i] = compose_augmentations(scan[i], probs=probs)
        else:
            # simple volume-level augmentation: apply same random transform to all slices (rotate/flip/zoom)
            seed = random.randint(0, 2 ** 31 - 1)
            out = np.zeros_like(scan, dtype=np.float32)
            for i in range(slices):
                random.seed(seed)
                out[i] = compose_augmentations(scan[i], probs=probs)
        results.append(out)

    if len(results) == 1:
        return results[0]
    return np.stack(results, axis=0)
