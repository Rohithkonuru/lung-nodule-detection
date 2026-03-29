"""
Production lung nodule detection using MONAI.

Supports:
- 3D CNN detection (ResNet-based)
- GPU acceleration (CUDA)
- CPU fallback
- Model caching
- Batch inference
"""

import torch
import torch.nn as nn
from typing import List, Tuple, Optional, Dict
import logging
import numpy as np
import math

logger = logging.getLogger(__name__)


class NodulesDetectionModel(nn.Module):
    """
    Production 3D lung nodule detection model (ResNet-based CNN).
    
    Architecture:
    - Input: 64x64x64 patches extracted from preprocessed CT
    - 3 residual blocks with dilations
    - Output: Binary nodule/non-nodule classification + confidence
    """
    
    def __init__(self):
        super().__init__()
        
        # Input: 64x64x64 single channel (CT)
        self.conv1 = nn.Conv3d(1, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm3d(32)
        
        # Residual blocks
        self.block1 = self._make_block(32, 64, dilation=1)
        self.block2 = self._make_block(64, 128, dilation=2)
        self.block3 = self._make_block(128, 256, dilation=2)
        
        # Global pooling + classification
        self.pool = nn.AdaptiveAvgPool3d(1)
        self.fc1 = nn.Linear(256, 128)
        self.fc2 = nn.Linear(128, 1)  # Binary: nodule/non-nodule
        
        self.relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(0.5)
        self.sigmoid = nn.Sigmoid()
    
    def _make_block(self, in_channels: int, out_channels: int, dilation: int = 1) -> nn.Sequential:
        """Create residual block with dilated convolutions."""
        return nn.Sequential(
            nn.Conv3d(in_channels, out_channels, kernel_size=3, padding=dilation, dilation=dilation),
            nn.BatchNorm3d(out_channels),
            nn.ReLU(inplace=True),
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input tensor (B, 1, 64, 64, 64)
        
        Returns:
            Confidence scores (B, 1) in [0, 1]
        """
        # Initial conv
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        
        # Residual blocks
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        
        # Classification head
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        confidence = self.sigmoid(x)
        
        return confidence


class LegacySliceClassifier(nn.Module):
    """Compatibility model for legacy 2D checkpoints with features/classifier keys."""

    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Identity(),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
        )
        self.classifier = nn.Linear(32 * 64 * 64, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return self.sigmoid(x)


class NoduleDetector:
    """Production nodule detection inference engine."""
    
    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """
        Initialize detector.
        
        Args:
            model_path: Path to trained model weights (.pth)
            device: 'cuda' or 'cpu'. Auto-detects if None.
        """
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self.model_kind = "3d"
        self.model = None
        
        # Real model weights are mandatory for production inference.
        if not model_path:
            raise ValueError("Model weights path is required. Set MODEL_WEIGHTS_PATH to a valid .pth file.")
        self._load_weights(model_path)
        
        self.model.eval()
        self.logger.info(f"Detector initialized on {self.device}")
    
    def _load_weights(self, model_path: str):
        """Load trained model weights."""
        try:
            from pathlib import Path

            weights_path = Path(model_path)
            if not weights_path.exists() or not weights_path.is_file():
                raise FileNotFoundError(f"Model weights not found: {model_path}")

            checkpoint = torch.load(model_path, map_location=self.device)

            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            else:
                state_dict = checkpoint

            if not isinstance(state_dict, dict):
                raise RuntimeError("Invalid checkpoint format: expected a state_dict dictionary")

            has_legacy_keys = any(k.startswith('features.') or k.startswith('classifier.') for k in state_dict.keys())

            if has_legacy_keys:
                self.model_kind = "2d"
                self.model = LegacySliceClassifier().to(self.device)
            else:
                self.model_kind = "3d"
                self.model = NodulesDetectionModel().to(self.device)

            result = self.model.load_state_dict(state_dict, strict=False)
            if result.missing_keys or result.unexpected_keys:
                self.logger.warning(
                    "State dict loaded with mismatches. Missing=%s Unexpected=%s",
                    result.missing_keys,
                    result.unexpected_keys,
                )

            if self.model_kind == "2d":
                self.logger.warning(
                    "Loaded legacy 2D checkpoint. Detection will run on central 2D slices of 3D patches."
                )
            
            self.logger.info(f"Loaded model weights from {model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load weights: {str(e)}")
            raise

    @staticmethod
    def _seed_in_mask(mask: np.ndarray, center_local: Tuple[int, int, int]) -> Optional[Tuple[int, int, int]]:
        """Pick a valid seed in a local binary mask near the center."""
        cz, cy, cx = center_local
        if 0 <= cz < mask.shape[0] and 0 <= cy < mask.shape[1] and 0 <= cx < mask.shape[2] and mask[cz, cy, cx]:
            return cz, cy, cx

        max_radius = 3
        for r in range(1, max_radius + 1):
            z0, z1 = max(0, cz - r), min(mask.shape[0], cz + r + 1)
            y0, y1 = max(0, cy - r), min(mask.shape[1], cy + r + 1)
            x0, x1 = max(0, cx - r), min(mask.shape[2], cx + r + 1)
            candidates = np.argwhere(mask[z0:z1, y0:y1, x0:x1])
            if len(candidates) > 0:
                offset = candidates[0]
                return int(z0 + offset[0]), int(y0 + offset[1]), int(x0 + offset[2])
        return None

    @staticmethod
    def _flood_fill_component(mask: np.ndarray, seed: Tuple[int, int, int]) -> np.ndarray:
        """Return boolean mask for the connected component containing seed."""
        visited = np.zeros(mask.shape, dtype=bool)
        component = np.zeros(mask.shape, dtype=bool)
        stack = [seed]

        while stack:
            z, y, x = stack.pop()
            if visited[z, y, x]:
                continue
            visited[z, y, x] = True
            if not mask[z, y, x]:
                continue

            component[z, y, x] = True
            for dz, dy, dx in (
                (-1, 0, 0), (1, 0, 0),
                (0, -1, 0), (0, 1, 0),
                (0, 0, -1), (0, 0, 1),
            ):
                nz, ny, nx = z + dz, y + dy, x + dx
                if 0 <= nz < mask.shape[0] and 0 <= ny < mask.shape[1] and 0 <= nx < mask.shape[2]:
                    if not visited[nz, ny, nx]:
                        stack.append((nz, ny, nx))

        return component

    def _estimate_nodule_size_mm(
        self,
        volume: np.ndarray,
        center: Tuple[int, int, int],
        voxel_spacing_zyx: Tuple[float, float, float],
        local_window: int = 40,
    ) -> float:
        """Estimate equivalent spherical diameter from local connected component volume."""
        z, y, x = center
        half = local_window // 2

        z0, z1 = max(0, z - half), min(volume.shape[0], z + half + 1)
        y0, y1 = max(0, y - half), min(volume.shape[1], y + half + 1)
        x0, x1 = max(0, x - half), min(volume.shape[2], x + half + 1)

        local = volume[z0:z1, y0:y1, x0:x1].astype(np.float32)
        if local.size == 0:
            return 3.0

        # Adaptive threshold around candidate point to isolate denser local structure.
        threshold = float(np.percentile(local, 85.0))
        binary = local >= threshold

        seed = self._seed_in_mask(binary, (z - z0, y - y0, x - x0))
        if seed is None:
            return 3.0

        component = self._flood_fill_component(binary, seed)
        voxel_count = int(component.sum())
        if voxel_count <= 0:
            return 3.0

        voxel_volume_mm3 = float(voxel_spacing_zyx[0] * voxel_spacing_zyx[1] * voxel_spacing_zyx[2])
        component_volume_mm3 = voxel_count * voxel_volume_mm3

        # Equivalent sphere diameter: d = 2 * (3V / 4pi)^(1/3)
        diameter_mm = 2.0 * ((3.0 * component_volume_mm3) / (4.0 * math.pi)) ** (1.0 / 3.0)
        return float(np.clip(diameter_mm, 1.0, 100.0))

    @staticmethod
    def _compute_bbox(
        center: Tuple[int, int, int],
        diameter_mm: float,
        voxel_spacing_zyx: Tuple[float, float, float],
        volume_shape: Tuple[int, int, int],
    ) -> Tuple[int, int, int, int, int, int]:
        """Build z1,y1,x1,z2,y2,x2 bounding box from center and estimated size."""
        z, y, x = center
        radius_mm = max(diameter_mm / 2.0, 1.0)

        rz = max(1, int(round(radius_mm / max(voxel_spacing_zyx[0], 1e-6))))
        ry = max(1, int(round(radius_mm / max(voxel_spacing_zyx[1], 1e-6))))
        rx = max(1, int(round(radius_mm / max(voxel_spacing_zyx[2], 1e-6))))

        z1 = max(0, z - rz)
        y1 = max(0, y - ry)
        x1 = max(0, x - rx)
        z2 = min(volume_shape[0] - 1, z + rz)
        y2 = min(volume_shape[1] - 1, y + ry)
        x2 = min(volume_shape[2] - 1, x + rx)
        return z1, y1, x1, z2, y2, x2

    @staticmethod
    def _distance(c1: Tuple[int, int, int], c2: Tuple[int, int, int]) -> float:
        a = np.array(c1, dtype=np.float32)
        b = np.array(c2, dtype=np.float32)
        return float(np.linalg.norm(a - b))

    def _legacy_candidate_selection(
        self,
        detections: List[Dict],
        max_count: int = 8,
        min_distance_voxels: float = 48.0,
    ) -> List[Dict]:
        """Reduce noisy detections from legacy 2D checkpoint to sparse top candidates."""
        if not detections:
            return []

        ranked = sorted(detections, key=lambda d: float(d.get('confidence', 0.0)), reverse=True)
        if len(ranked) <= max_count:
            return ranked

        selected: List[Dict] = []
        for det in ranked:
            center = tuple(det.get('center', (0, 0, 0)))
            if any(self._distance(center, tuple(s.get('center', (0, 0, 0)))) < min_distance_voxels for s in selected):
                continue
            selected.append(det)
            if len(selected) >= max_count:
                break

        # Fallback if spacing rule was too strict for the scan geometry.
        if not selected:
            selected = ranked[:max_count]

        return selected
    
    def extract_patch(self, volume: np.ndarray, center: Tuple[int, int, int], 
                     patch_size: int = 64) -> np.ndarray:
        """Extract cubic patch centered at point."""
        z, y, x = center
        half = patch_size // 2
        
        z_start = max(0, z - half)
        z_end = min(volume.shape[0], z + half)
        y_start = max(0, y - half)
        y_end = min(volume.shape[1], y + half)
        x_start = max(0, x - half)
        x_end = min(volume.shape[2], x + half)
        
        patch = volume[z_start:z_end, y_start:y_end, x_start:x_end]
        
        # Pad if necessary
        if patch.shape != (patch_size, patch_size, patch_size):
            padded = np.full((patch_size, patch_size, patch_size), -1.0, dtype=np.float32)
            z_offset = (patch_size - (z_end - z_start)) // 2
            y_offset = (patch_size - (y_end - y_start)) // 2
            x_offset = (patch_size - (x_end - x_start)) // 2
            padded[z_offset:z_offset+(z_end-z_start),
                   y_offset:y_offset+(y_end-y_start),
                   x_offset:x_offset+(x_end-x_start)] = patch
            return padded
        
        return patch.astype(np.float32)
    
    def detect(
        self,
        volume: np.ndarray,
        stride: int = 32,
        confidence_threshold: float = 0.5,
        voxel_spacing_zyx: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    ) -> List[Dict]:
        """
        Detect nodules in volume using sliding window.
        
        Args:
            volume: Preprocessed 3D CT volume
            stride: Step size for sliding window (mm, at 1mm isotropic)
            confidence_threshold: Minimum confidence for positive detection
        
        Returns:
            List of detections: [{'center': (z,y,x), 'confidence': float, 'size_mm': float}]
        """
        try:
            detections = []
            z_dim, y_dim, x_dim = volume.shape
            patch_size = 64

            def axis_positions(dim: int) -> List[int]:
                # Ensure we always evaluate at least one center per axis, even for thin 2D-like inputs.
                if dim <= patch_size:
                    return [max(0, dim // 2)]

                start = patch_size // 2
                end = dim - patch_size // 2
                pos = list(range(start, end, max(1, stride)))
                if not pos:
                    pos = [dim // 2]
                elif pos[-1] != (end - 1):
                    pos.append(end - 1)
                return pos
            
            self.logger.info(f"Starting detection: volume shape {volume.shape}, stride {stride}")
            
            candidate_centers = []
            z_positions = axis_positions(z_dim)
            y_positions = axis_positions(y_dim)
            x_positions = axis_positions(x_dim)

            for z in z_positions:
                for y in y_positions:
                    for x in x_positions:
                        candidate_centers.append((z, y, x))
            
            self.logger.debug(f"Evaluating {len(candidate_centers)} candidate locations")
            
            # Legacy 2D checkpoints tend to over-fire on every patch, so require stronger confidence.
            effective_threshold = confidence_threshold
            if self.model_kind == "2d":
                effective_threshold = max(confidence_threshold, 0.70)

            # Batch inference for speed
            batch_size = 8
            with torch.no_grad():
                for i in range(0, len(candidate_centers), batch_size):
                    batch_centers = candidate_centers[i:i+batch_size]
                    patches = []
                    
                    for center in batch_centers:
                        patch = self.extract_patch(volume, center)
                        patches.append(patch)
                    
                    # Stack and convert to tensor
                    if self.model_kind == "2d":
                        # Legacy checkpoints are 2D classifiers, so use center slice from each 3D patch.
                        center_idx = patch_size // 2
                        slice_batch = np.stack([p[center_idx] for p in patches])
                        patches_tensor = torch.from_numpy(slice_batch).unsqueeze(1)
                    else:
                        patches_tensor = torch.from_numpy(np.stack(patches)).unsqueeze(1)
                    patches_tensor = patches_tensor.to(self.device)
                    
                    # Inference
                    confidences = self.model(patches_tensor)
                    
                    # Process results
                    for center, confidence in zip(batch_centers, confidences.cpu().numpy()):
                        conf_value = float(confidence[0])
                        if conf_value >= effective_threshold:
                            size_mm = self._estimate_nodule_size_mm(volume, center, voxel_spacing_zyx)
                            bbox = self._compute_bbox(center, size_mm, voxel_spacing_zyx, volume.shape)
                            detections.append({
                                'center': center,
                                'confidence': conf_value,
                                'size_mm': float(size_mm),
                                'bbox_zyx': bbox,
                            })
            
            if self.model_kind == "2d":
                detections = self._legacy_candidate_selection(detections)

            self.logger.info(f"Detection complete: {len(detections)} nodules found")
            return detections
            
        except Exception as e:
            self.logger.error(f"Detection failed: {str(e)}")
            raise


# Global detector instance
_detector = None
_detector_model_path = None


def get_detector(model_path: Optional[str] = None) -> NoduleDetector:
    """Get singleton detector instance (model caching)."""
    global _detector, _detector_model_path
    if not model_path:
        raise ValueError("model_path is required to initialize detector")

    if _detector is None:
        _detector = NoduleDetector(model_path)
        _detector_model_path = model_path
    elif _detector_model_path != model_path:
        logger.warning("Detector already initialized with a different model path; reusing existing instance")
    return _detector


__all__ = ['NodulesDetectionModel', 'NoduleDetector', 'get_detector']
