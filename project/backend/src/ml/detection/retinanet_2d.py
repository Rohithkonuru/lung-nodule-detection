"""
2D RetinaNet detector for lung nodule detection on CT slices.
Uses ImageNet pretrained ResNet50 FPN, fine-tuned on LUNA16 data.
"""

import torch
import torchvision
from torchvision.models.detection import retinanet_resnet50_fpn
from torchvision.ops import nms
import torchvision.transforms as T
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
import hashlib

logger = logging.getLogger(__name__)


class RetinaNet2DDetector:
    """
    2D RetinaNet detector for CT slices.
    
    Architecture:
    - ResNet50 backbone with FPN
    - ImageNet pretrained, fine-tuned on LUNA16
    - Detects lung nodules in 2D CT slice images
    """
    
    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize RetinaNet detector.
        
        Args:
            model_path: Path to fine-tuned checkpoint (.pth)
            device: 'cuda' or 'cpu'. Auto-detects if None.
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Load model - start with ImageNet pretrained
        self.model = retinanet_resnet50_fpn(pretrained=True)
        
        # Load fine-tuned weights if provided
        if model_path:
            self._load_weights(model_path)
        else:
            self.logger.info("No model path provided, using ImageNet pretrained RetinaNet")

        # Expose raw candidates for debugging (stage 2 request).
        # Final filtering still happens via confidence_threshold in detect().
        if hasattr(self.model, "score_thresh"):
            self.model.score_thresh = 0.0
        if hasattr(self.model, "detections_per_img"):
            self.model.detections_per_img = 300
        
        self.model.to(self.device)
        self.model.eval()

        # RetinaNet expects ImageNet-style normalized tensors.
        self.normalize = T.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )

        # Debug snapshots from the latest detect() call.
        self.last_raw_detections: List[Dict] = []
        self.last_filtered_detections: List[Dict] = []
        self._detect_call_counter = 0
        
        self.logger.info(f"RetinaNet2D initialized on {self.device}")

    @staticmethod
    def _mask_threshold_for_scale(slice_image: np.ndarray) -> float:
        """Choose a lung-mask threshold matching the image intensity scale."""
        min_v = float(np.min(slice_image))
        max_v = float(np.max(slice_image))

        # HU-like scale.
        if min_v < -300.0 and max_v > 50.0:
            return -600.0

        # [0, 1] normalized CT after windowing [-1024, 400].
        if min_v >= 0.0 and max_v <= 1.5:
            return (-600.0 - (-1024.0)) / (400.0 - (-1024.0))

        # [0, 255] image-like scale.
        if min_v >= 0.0 and max_v <= 255.0:
            norm_thr = (-600.0 - (-1024.0)) / (400.0 - (-1024.0))
            return norm_thr * 255.0

        # Conservative fallback.
        return -600.0

    def _apply_lung_mask(self, slice_image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply a simple threshold-based lung mask before RetinaNet inference."""
        threshold = self._mask_threshold_for_scale(slice_image)
        mask = (slice_image > threshold).astype(np.float32)
        masked = slice_image * mask

        keep_ratio = float(mask.mean())
        self.logger.debug(
            "Lung mask threshold=%0.4f keep_ratio=%0.3f",
            threshold,
            keep_ratio,
        )
        return masked, mask

    
    def _load_weights(self, model_path: str):
        """Load fine-tuned checkpoint."""
        try:
            weights_path = Path(model_path)
            if not weights_path.exists():
                self.logger.warning(f"Checkpoint not found: {model_path}, using ImageNet pretrained")
                return
            
            # Try loading with weights_only=False to allow safe globals
            try:
                checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
            except TypeError:
                # Fallback for older PyTorch versions
                checkpoint = torch.load(model_path, map_location=self.device)
            
            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            else:
                state_dict = checkpoint
            
            result = self.model.load_state_dict(state_dict, strict=False)
            if result.missing_keys or result.unexpected_keys:
                self.logger.debug(f"Loaded checkpoint with some mismatches")
            
            self.logger.info(f"Fine-tuned weights loaded: {model_path}")
        except Exception as e:
            self.logger.warning(f"Failed to load custom weights: {e}, using ImageNet pretrained")
    
    def _lung_region_filter(
        self,
        detections: List[Dict],
        h: int,
        w: int,
        roi_min_ratio: float = 0.05,
        roi_max_ratio: float = 0.95,
    ) -> List[Dict]:
        """
        Filter detections to keep only those inside lung region.
        Rejects detections near borders (ribs area) and edges.
        
        Args:
            detections: List of detections with 'bbox' field
            h: Image height
            w: Image width
        
        Returns:
            Filtered detections
        """
        filtered = []
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']

            # Keep detections inside configured central ROI.
            is_valid = (
                x1 > w * roi_min_ratio and x2 < w * roi_max_ratio and
                y1 > h * roi_min_ratio and y2 < h * roi_max_ratio
            )
            if not is_valid:
                self.logger.debug("Rejected detection: outside central lung ROI")
                continue

            filtered.append(det)

        return filtered
    
    def _size_filter(
        self,
        detections: List[Dict],
        min_size: int = 3,
        max_size: int = 80,
    ) -> List[Dict]:
        """
        Filter detections by size.
        Real lung nodules have specific size ranges.
        Rejects extremely small (noise) or extremely large (not nodules) detections.
        
        Args:
            detections: List of detections with 'bbox' field
        
        Returns:
            Filtered detections
        """
        filtered = []
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            width = x2 - x1
            height = y2 - y1
            size = max(width, height)
            
            # Requested looser size rule for staged filtering.
            if not (min_size < size < max_size):
                self.logger.debug(f"Rejected detection: invalid size ({width}x{height}px, max_side={size}px)")
                continue

            filtered.append(det)

        return filtered
    
    def _center_bias_filter(self, detections: List[Dict], h: int, w: int) -> List[Dict]:
        """
        Reject detections far from image center.
        Real lung nodules are rarely at extreme edges.
        
        Args:
            detections: List of detections with 'bbox' field
            h: Image height
            w: Image width
        
        Returns:
            Filtered detections
        """
        filtered = []
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            
            # Reject if center is at image extremes (outer 20% regions)
            if cx < w * 0.1 or cx > w * 0.9:
                self.logger.debug(f"Rejected detection: center outside horizontal bounds")
                continue
            if cy < h * 0.1 or cy > h * 0.9:
                self.logger.debug(f"Rejected detection: center outside vertical bounds")
                continue
            
            filtered.append(det)
        
        return filtered

    def detect(
        self,
        slice_image: np.ndarray,
        confidence_threshold: float = 0.04,
        slice_index: Optional[int] = None,
        disable_filters: bool = False,
        debug_mid_conf_only: bool = False,
        use_lung_mask: bool = False,
        use_size_filter: bool = False,
        use_roi_filter: bool = False,
        min_size_px: int = 5,
        max_size_px: int = 40,
        roi_min_ratio: float = 0.1,
        roi_max_ratio: float = 0.9,
        nms_iou_threshold: float = 0.3,
        post_filter_score_threshold: float = 0.06,
        top_k_detections: int = 3,
        debug_print_raw_outputs: bool = True,
    ) -> List[Dict]:
        """
        Detect nodules in a single CT slice.
        Applies multi-stage filtering to reduce false positives:
        1. Lung region filter (reject border/rib detections)
        2. Size filter (reject too small/large boxes)
        3. Center bias filter (reject extreme edge detections)
        
        Args:
            slice_image: 2D CT slice (HxW), float32, normalized to [-1000, 500] or similar
            confidence_threshold: Minimum confidence for positive detection
            slice_index: Z-index of this slice in 3D volume (optional, for tracking)
            disable_filters: If True, skip spatial filters (for diagnostics/testing)
        
        Returns:
            List of detections: [{'bbox': [x1,y1,x2,y2], 'confidence': float, 'slice': int}]
        """
        try:
            self.last_raw_detections = []
            self.last_filtered_detections = []
            self._detect_call_counter += 1
            detect_call_id = self._detect_call_counter

            if debug_print_raw_outputs:
                print(f"Running fresh detection call #{detect_call_id} (slice={slice_index})")

            # Ensure numpy array
            if isinstance(slice_image, torch.Tensor):
                slice_image = slice_image.cpu().numpy()
            
            # Force 2D → HxW
            if slice_image.ndim > 2:
                slice_image = slice_image.squeeze()
            
            if slice_image.ndim != 2:
                self.logger.warning(f"Unexpected slice shape: {slice_image.shape}, skipping")
                return []
            
            h, w = slice_image.shape

            if debug_print_raw_outputs:
                slice_bytes = np.ascontiguousarray(slice_image).tobytes()
                print("Image shape:", slice_image.shape)
                print("Image sum:", float(slice_image.sum()))
                print("IMAGE HASH:", hash(slice_bytes))
                print("IMAGE SHA1:", hashlib.sha1(slice_bytes).hexdigest()[:16])
            
            working_slice = slice_image.astype(np.float32)
            if use_lung_mask:
                working_slice, _mask = self._apply_lung_mask(working_slice)

            # Keep training/inference normalization aligned:
            # image = image.astype("float32") / 255.0
            # We first map diverse input scales to uint8, then divide by 255.
            min_v = float(np.min(working_slice))
            max_v = float(np.max(working_slice))

            if debug_print_raw_outputs:
                print(f"Input min/max before norm: {min_v:.6f}/{max_v:.6f}")

            if min_v < 0.0 or max_v > 1.0:
                if min_v < -50.0 or max_v > 10.0:
                    windowed = np.clip(working_slice, -1024.0, 400.0)
                    normalized = (windowed + 1024.0) / 1424.0
                else:
                    denom = max(max_v - min_v, 1e-6)
                    normalized = (working_slice - min_v) / denom
            else:
                normalized = working_slice

            normalized = np.clip(normalized, 0.0, 1.0).astype(np.float32)
            img_uint8 = (normalized * 255.0).astype(np.uint8)
            img_float = img_uint8.astype(np.float32) / 255.0

            # Convert to 3-channel tensor (C,H,W) and apply ImageNet normalization.
            img_chw = np.stack([img_float, img_float, img_float], axis=0)
            img_tensor = torch.from_numpy(img_chw)
            img_tensor = self.normalize(img_tensor).unsqueeze(0).to(self.device)

            if self.model.training:
                # Safety net: inference must always be in eval mode.
                self.model.eval()
                self.logger.warning("Model was in training mode during detect(); forced eval()")
                if debug_print_raw_outputs:
                    print("Forced model.eval() before inference")

            if debug_print_raw_outputs:
                print("Model input shape (C,H,W):", tuple(img_tensor.squeeze(0).shape))
                print("Model eval mode:", not self.model.training)
            
            if img_tensor.shape != torch.Size([1, 3, h, w]):
                self.logger.debug(f"Tensor shape after transform: {img_tensor.shape}, expected [1, 3, {h}, {w}]")
            
            # Inference
            with torch.no_grad():
                outputs = self.model([img_tensor.squeeze(0)])
            
            detections_raw = []
            
            if outputs and len(outputs) > 0:
                raw_boxes = outputs[0]['boxes'] if 'boxes' in outputs[0] else torch.empty((0, 4), device=self.device)
                raw_scores = outputs[0]['scores'] if 'scores' in outputs[0] else torch.empty((0,), device=self.device)

                pre_nms_count = int(raw_scores.shape[0])
                if pre_nms_count > 0:
                    keep = nms(raw_boxes, raw_scores, float(nms_iou_threshold))
                    boxes = raw_boxes[keep].detach().cpu().numpy()
                    scores = raw_scores[keep].detach().cpu().numpy()
                else:
                    boxes = np.array([])
                    scores = np.array([])

                if debug_print_raw_outputs:
                    print(f"Raw predictions before NMS: {pre_nms_count}")
                    print(f"Predictions after NMS: {len(scores)}")
                    print("Scores:", scores[:10].tolist() if scores.size else [])
                    print("Boxes:", boxes[:5].tolist() if boxes.size else [])

                # Quick debug requested: inspect top model scores.
                self.logger.info(f"[Slice {slice_index}] scores[:10]={scores[:10].tolist() if scores.size else []}")

                # Log a small sample of raw model output for diagnostics
                sample_boxes = boxes[:5].tolist() if boxes.size else []
                sample_scores = scores[:5].tolist() if scores.size else []
                self.logger.info(f"[Slice {slice_index}] Raw detections: {len(boxes)} | boxes(head): {sample_boxes} | scores(head): {sample_scores}")
                
                for box, score in zip(boxes, scores):
                    if debug_mid_conf_only and not (0.1 < float(score) < 0.4):
                        continue

                    if score >= confidence_threshold:
                        x1, y1, x2, y2 = box.astype(int)
                        
                        # Clip to image bounds
                        x1 = max(0, min(x1, w - 1))
                        y1 = max(0, min(y1, h - 1))
                        x2 = max(x1 + 1, min(x2, w))
                        y2 = max(y1 + 1, min(y2, h))
                        
                        det = {
                            'bbox': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': float(score),
                            'center_xy': [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                        }
                        
                        if slice_index is not None:
                            det['slice'] = slice_index
                        
                        detections_raw.append(det)

            self.last_raw_detections = list(detections_raw)
            
            # Apply multi-stage filtering to reduce false positives
            # (skip if testing/diagnostics mode)
            if disable_filters:
                detections = detections_raw
                self.logger.info(f"[Slice {slice_index}] TESTING MODE: Filters disabled - {len(detections)} detections")
            else:
                detections = detections_raw

                if use_roi_filter:
                    detections = self._lung_region_filter(
                        detections,
                        h,
                        w,
                        roi_min_ratio=roi_min_ratio,
                        roi_max_ratio=roi_max_ratio,
                    )
                    detections = self._center_bias_filter(detections, h, w)

                if use_size_filter:
                    detections = self._size_filter(
                        detections,
                        min_size=min_size_px,
                        max_size=max_size_px,
                    )

                if float(post_filter_score_threshold) > 0.0:
                    detections = [
                        d for d in detections
                        if float(d.get('confidence', 0.0)) >= float(post_filter_score_threshold)
                    ]

                if int(top_k_detections) > 0 and len(detections) > int(top_k_detections):
                    detections = sorted(
                        detections,
                        key=lambda d: float(d.get('confidence', 0.0)),
                        reverse=True,
                    )[: int(top_k_detections)]

                self.logger.info(f"[Slice {slice_index}] {len(detections_raw)} raw → {len(detections)} after filters")

            self.last_filtered_detections = list(detections)
            
            return detections
        
        except Exception as e:
            self.logger.error(f"Detection failed on slice {slice_index}: {e}")
            return []
    
    def detect_batch(
        self,
        slice_images: List[np.ndarray],
        confidence_threshold: float = 0.04,
    ) -> List[List[Dict]]:
        """
        Batch detection on multiple slices.
        
        Args:
            slice_images: List of 2D slices
            confidence_threshold: Min confidence
        
        Returns:
            List of detection lists (one per slice)
        """
        batch_results = []
        
        for i, slice_img in enumerate(slice_images):
            dets = self.detect(slice_img, confidence_threshold, slice_index=i)
            batch_results.append(dets)
        
        return batch_results


__all__ = ['RetinaNet2DDetector']
