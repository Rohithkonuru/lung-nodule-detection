"""
Robust inference helpers for the project.

- Safe model loading (no silent failures)
- Predict never crashes even if model is missing
- Clean demo fallback
- Supports scoring, embeddings, box detection, and NMS
"""

from typing import List
import os
import numpy as np
from PIL import Image
from src.models.unet import UNet


# Lazy torch import
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False

import logging
logger = logging.getLogger("lung_nodule_infer")


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def is_torch_available() -> bool:
    return TORCH_AVAILABLE


# ---------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------

def load_model(path: str, device: str = "cpu"):
    """
    Load a PyTorch model from disk.
    Raises clear errors if anything is wrong.
    """
    try:
        abs_path = os.path.abspath(path)
        logger.info(f"Loading model weights from {abs_path} on device {device}...")
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch is not available")

        if not path or not isinstance(path, str):
            raise ValueError(f"Model path is invalid: {path} (abs: {abs_path})")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path} (abs: {abs_path})")

        from src.models.retinanet import SimpleRetinaNet
        model = SimpleRetinaNet()
        state = torch.load(path, map_location=device)
        logger.debug(f"Loaded state dict keys: {list(state.keys()) if isinstance(state, dict) else type(state)}")
        if isinstance(state, dict) and "model_state_dict" in state:
            state_dict = state["model_state_dict"]
        else:
            state_dict = state
        result = model.load_state_dict(state_dict, strict=False)
        logger.info(f"State dict load result: missing_keys={result.missing_keys}, unexpected_keys={result.unexpected_keys}")
        if len(result.missing_keys) > 0 or len(result.unexpected_keys) > 0:
            logger.warning(f"Model state_dict mismatch. Missing keys: {result.missing_keys}, Unexpected keys: {result.unexpected_keys}")
        else:
            logger.info("Model weights loaded successfully.")
        model.to(device)
        model.eval()
        logger.info(f"Model moved to device {device} and set to eval mode.")
        return model
    except Exception as e:
        logger.error(f"[load_model ERROR] path={path} abs_path={os.path.abspath(path)} device={device} error={e}")
        # For Flask: propagate error up so it can be shown as a flash message, but do not crash app
        raise


# ---------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------

def _preprocess_pil_image(im: Image.Image, size: int = 256) -> np.ndarray:
    """
    Convert PIL image to normalized float32 array (1, H, W).
    """
    im = im.convert("L")
    im = im.resize((size, size), Image.BILINEAR)
    arr = np.asarray(im, dtype=np.float32) / 255.0
    return arr


# ---------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------

def predict(model, pil_image: Image.Image, device: str = "cpu") -> float:
    """
    Run inference and return confidence score (0..1).
    Falls back to demo prediction if model is None.
    """

    # 🔒 HARD GUARD — prevents NoneType crash
    if model is None or not TORCH_AVAILABLE:
        arr = _preprocess_pil_image(pil_image)
        return float(arr.mean())

    arr = _preprocess_pil_image(pil_image)
    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0).to(device)

    with torch.no_grad():
        out = model(tensor)

        if out.numel() == 1:
            score = torch.sigmoid(out.view(-1)).item()
        else:
            score = float(F.softmax(out.view(-1), dim=0).max().item())

    return score


# ---------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------

def compute_embedding(model, pil_image: Image.Image, device: str = "cpu") -> np.ndarray:
    """
    Return an embedding vector for the image.
    """

    arr = _preprocess_pil_image(pil_image)

    if model is None or not TORCH_AVAILABLE:
        # Demo embedding
        return np.mean(arr.reshape(-1, 16), axis=1).astype(np.float32)

    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0).to(device)

    with torch.no_grad():
        try:
            feats = model.features(tensor)
        except Exception:
            feats = model(tensor)

        emb = feats.view(feats.size(0), feats.size(1), -1).mean(dim=2)
        emb = emb.cpu().numpy().ravel().astype(np.float32)

    return emb


# ---------------------------------------------------------------------
# Detection (Demo + Model-based)
# ---------------------------------------------------------------------

def detect_boxes(model, pil_image: Image.Image, device: str = "cpu") -> list:
    """
    Detect bounding boxes of abnormal regions.
    Returns list of (x1, y1, x2, y2, score).
    """

    if TORCH_AVAILABLE and model is not None and hasattr(model, "predict_boxes"):
        try:
            logger.info("Using model's predict_boxes for detection.")
            boxes = model.predict_boxes(pil_image, conf_thresh=0.3, iou_thresh=0.3)
            logger.debug(f"Model output: {boxes}")
            if not boxes:
                logger.info("No boxes detected by model.")
            else:
                for idx, box in enumerate(boxes):
                    logger.info(f"Box {idx}: {box}")
            return boxes
        except Exception as e:
            logger.warning(f"Model predict_boxes failed: {e}")
            if not os.environ.get('DEBUG', False):
                raise
            return []
    logger.error("No valid model loaded for detection. Returning empty list.")
    return []


# ---------------------------------------------------------------------
# NMS
# ---------------------------------------------------------------------

def nms(boxes: list, iou_threshold: float = 0.3) -> list:
    if not boxes:
        return []

    boxes = np.array(boxes, dtype=float)
    x1, y1, x2, y2, scores = boxes.T

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h

        iou = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return [tuple(boxes[i]) for i in keep]


def detect_boxes_with_options(
    model,
    pil_image: Image.Image,
    conf_thresh: float = 0.3,
    apply_nms: bool = True,
    iou_thresh: float = 0.3,
) -> list:
    """
    Detect bounding boxes with customizable options.
    
    Args:
        model: Loaded detection model
        pil_image: PIL Image to detect in
        conf_thresh: Confidence threshold (0-1)
        apply_nms: Whether to apply Non-Max Suppression
        iou_thresh: IoU threshold for NMS
        
    Returns:
        List of boxes: [(x1, y1, x2, y2, confidence), ...]
    """
    logger.info(f"Detecting boxes with conf_thresh={conf_thresh}, apply_nms={apply_nms}, iou_thresh={iou_thresh}")
    
    boxes = detect_boxes(model, pil_image)
    logger.debug(f"Raw detected boxes: {boxes}")
    
    if not boxes:
        logger.info("No boxes detected")
        return []
    
    before = len(boxes)
    
    # Filter by confidence threshold
    boxes = [b for b in boxes if len(b) >= 5 and b[4] >= conf_thresh]
    logger.info(f"Filtered down to {len(boxes)} boxes above threshold {conf_thresh:.2f}")
    
    # Filter by size - keep only relatively small objects (nodules)
    w, h = pil_image.size
    img_area = w * h
    filtered_boxes = []
    
    for box in boxes:
        x1, y1, x2, y2, score = box[:5]
        
        # Ensure box coordinates are valid
        if x1 >= x2 or y1 >= y2:
            logger.debug(f"Skipping invalid box: {box}")
            continue
        
        box_w = x2 - x1
        box_h = y2 - y1
        box_area = box_w * box_h
        
        # Keep boxes smaller than 30% of image area (nodules are relatively small)
        if box_area < 0.3 * img_area:
            filtered_boxes.append(box)
        else:
            logger.debug(f"Skipped oversized box: area={box_area:.0f} ({box_area/img_area*100:.1f}% of image)")
    
    logger.debug(f"After size filtering: {len(filtered_boxes)} boxes remain")
    
    # Apply NMS to remove overlapping boxes
    if apply_nms and filtered_boxes:
        filtered_boxes = nms(filtered_boxes, iou_threshold=iou_thresh)
        logger.info(f"NMS applied (IOU threshold={iou_thresh}), {len(filtered_boxes)} boxes remain")
    
    for idx, box in enumerate(filtered_boxes):
        logger.info(f"Final Box {idx}: x1={box[0]:.1f}, y1={box[1]:.1f}, x2={box[2]:.1f}, y2={box[3]:.1f}, conf={box[4]:.3f}")
    
    return filtered_boxes


def draw_boxes(
    image: Image.Image,
    boxes: list,
    color: tuple = (255, 0, 0),
    thickness: int = 2,
    show_confidence: bool = True,
) -> Image.Image:
    """
    Draw bounding boxes on an image.
    
    Args:
        image: PIL Image to draw on
        boxes: List of boxes [(x1, y1, x2, y2, confidence), ...]
        color: RGB color for boxes
        thickness: Line thickness in pixels
        show_confidence: Whether to show confidence scores on boxes
        
    Returns:
        PIL Image with drawn boxes
    """
    from PIL import ImageDraw, ImageFont
    
    logger.info(f"Drawing {len(boxes)} boxes on image")
    
    # Convert to RGB if needed
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Make a copy to avoid modifying original
    image_copy = image.copy()
    draw = ImageDraw.Draw(image_copy)
    
    for idx, box in enumerate(boxes):
        if len(box) < 4:
            logger.warning(f"Invalid box format: {box}")
            continue
        
        x1, y1, x2, y2 = box[:4]
        confidence = box[4] if len(box) >= 5 else 1.0
        
        # Ensure coordinates are integers and within image bounds
        img_w, img_h = image.size
        x1 = max(0, min(int(x1), img_w - 1))
        y1 = max(0, min(int(y1), img_h - 1))
        x2 = max(0, min(int(x2), img_w - 1))
        y2 = max(0, min(int(y2), img_h - 1))
        
        # Draw rectangle
        draw.rectangle([x1, y1, x2, y2], outline=color, width=thickness)
        
        # Draw confidence score if requested
        if show_confidence and len(box) >= 5:
            label = f"Conf: {confidence:.2f}"
            try:
                # Try to use a nice font
                font = ImageFont.truetype("arial.ttf", 10)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
            
            # Draw label background
            bbox = draw.textbbox((x1, y1 - 15), label, font=font)
            draw.rectangle(bbox, fill=color)
            draw.text((x1, y1 - 15), label, fill=(255, 255, 255), font=font)
        
        logger.debug(f"Drew box {idx}: ({x1}, {y1}) to ({x2}, {y2}), conf={confidence:.3f}")
    
    logger.info(f"Successfully drew {len(boxes)} boxes")
    return image_copy
    return filtered_boxes


# ---------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------

def draw_boxes(pil_image: Image.Image, boxes: list, width: int = 3) -> Image.Image:
    from PIL import ImageDraw, ImageFont

    im = pil_image.convert("RGB").copy()
    draw = ImageDraw.Draw(im)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = None

    color = (255, 0, 0)
    for x1, y1, x2, y2, _ in boxes:
        draw.rectangle([x1, y1, x2, y2], outline=color, width=width)

    # Add 'Regions Detected' label above the image
    label_text = "Regions Detected"
    if font:
        draw.text((10, 10), label_text, fill=color, font=font)
    else:
        draw.text((10, 10), label_text, fill=color)

    return im
