"""LUNA16 dataset loader with real bounding box extraction.

This module loads CT scans from LUNA16 and extracts 2D slice boxes from
3D nodule annotations in ``annotations.csv``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import SimpleITK as sitk
import torch
from torch.utils.data import DataLoader, Dataset

logger = logging.getLogger(__name__)


def _subset_name(subset: Union[int, str]) -> str:
	"""Normalize subset identifiers to the expected folder name."""
	subset_str = str(subset)
	if subset_str.lower().startswith("subset"):
		return subset_str
	return f"subset{subset_str}"


class LUNADataset(Dataset):
	"""LUNA16 dataset that returns one representative slice per series.

	Args:
		data_dir: Root directory containing ``subset*`` folders.
		annotations_file: Path to LUNA16 ``annotations.csv``.
		subset: Optional subset id/name (example: ``0`` or ``subset0``).
		subset_folders: Optional explicit list of subset folder names.
		cache: If True, keep loaded volumes in memory for faster iteration.
		slice_tolerance: Max distance in z-slices to include a nodule on slice.
	"""

	def __init__(
		self,
		data_dir: Union[str, Path],
		annotations_file: Union[str, Path],
		subset: Optional[Union[int, str]] = None,
		subset_folders: Optional[Sequence[str]] = None,
		cache: bool = True,
		slice_tolerance: int = 2,
		hard_negative_ratio: float = 0.0,
	) -> None:
		self.data_dir = Path(data_dir)
		self.annotations_file = Path(annotations_file)
		self.subset = subset
		self.cache = cache
		self.slice_tolerance = int(slice_tolerance)
		self.hard_negative_ratio = max(0.0, float(hard_negative_ratio))

		if not self.data_dir.exists():
			raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
		if not self.annotations_file.exists():
			raise FileNotFoundError(f"Annotations file not found: {self.annotations_file}")

		self.annotations = pd.read_csv(self.annotations_file)
		required_columns = {"seriesuid", "coordX", "coordY", "coordZ", "diameter_mm"}
		missing = required_columns.difference(self.annotations.columns)
		if missing:
			missing_list = ", ".join(sorted(missing))
			raise ValueError(f"annotations.csv missing required columns: {missing_list}")

		self._subset_dirs = self._resolve_subset_dirs(subset, subset_folders)
		self._mhd_cache: Dict[str, Optional[Path]] = {}
		self._volume_cache: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

		all_series_ids = sorted(self.annotations["seriesuid"].astype(str).unique().tolist())
		self._series_paths: Dict[str, Path] = {}
		for series_id in all_series_ids:
			mhd_path = self._find_mhd_path(series_id)
			if mhd_path is not None:
				self._series_paths[series_id] = mhd_path

		self.series_with_nodules = sorted(self._series_paths.keys())
		self._base_len = len(self.series_with_nodules)
		self._hard_negative_count = int(round(self._base_len * self.hard_negative_ratio)) if self._base_len > 0 else 0
		skipped = len(all_series_ids) - len(self.series_with_nodules)
		if skipped > 0:
			logger.warning("Skipped %d series without matching .mhd files", skipped)

		logger.info(
			"Loaded LUNA16 dataset: %d series (+%d hard negatives) across %d subset folders",
			len(self.series_with_nodules),
			self._hard_negative_count,
			len(self._subset_dirs),
		)

	def _resolve_subset_dirs(
		self,
		subset: Optional[Union[int, str]],
		subset_folders: Optional[Sequence[str]],
	) -> List[Path]:
		if subset_folders:
			candidate_names = [_subset_name(name) for name in subset_folders]
			subset_dirs = [self.data_dir / name for name in candidate_names]
		elif subset is not None:
			subset_dirs = [self.data_dir / _subset_name(subset)]
		else:
			subset_dirs = sorted(
				[p for p in self.data_dir.iterdir() if p.is_dir() and p.name.lower().startswith("subset")],
				key=lambda p: p.name,
			)

		# Allow direct mhd placement under data_dir as a fallback.
		if not subset_dirs and any(self.data_dir.glob("*.mhd")):
			return [self.data_dir]

		existing_subset_dirs = [p for p in subset_dirs if p.exists() and p.is_dir()]
		if not existing_subset_dirs:
			raise FileNotFoundError(
				f"No valid subset folders found under {self.data_dir}. "
				f"Checked: {[str(p) for p in subset_dirs]}"
			)
		return existing_subset_dirs

	def _find_mhd_path(self, series_id: str) -> Optional[Path]:
		if series_id in self._mhd_cache:
			return self._mhd_cache[series_id]

		for subset_dir in self._subset_dirs:
			direct = sorted(subset_dir.glob(f"{series_id}*.mhd"))
			if direct:
				self._mhd_cache[series_id] = direct[0]
				return direct[0]

			recursive = sorted(subset_dir.rglob(f"{series_id}*.mhd"))
			if recursive:
				self._mhd_cache[series_id] = recursive[0]
				return recursive[0]

		self._mhd_cache[series_id] = None
		return None

	def __len__(self) -> int:
		return self._base_len + self._hard_negative_count

	def __getitem__(self, idx: int) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
		if self._base_len == 0:
			raise IndexError("Dataset is empty")

		is_hard_negative = idx >= self._base_len
		if is_hard_negative:
			rel_idx = idx - self._base_len
			series_id = self.series_with_nodules[rel_idx % self._base_len]
		else:
			series_id = self.series_with_nodules[idx]

		volume, spacing_xyz, origin_xyz = self._load_volume(series_id)

		if is_hard_negative:
			slice_idx = self._choose_hard_negative_slice_index(
				series_id,
				volume.shape[0],
				spacing_xyz,
				origin_xyz,
				sample_seed=idx,
			)
			boxes = np.zeros((0, 4), dtype=np.float32)
			labels = np.zeros((0,), dtype=np.int64)
		else:
			slice_idx = self._choose_slice_index(series_id, volume.shape[0], spacing_xyz, origin_xyz)
			boxes, labels = self._get_bounding_boxes(
				series_id=series_id,
				slice_idx=slice_idx,
				spacing_xyz=spacing_xyz,
				origin_xyz=origin_xyz,
				image_shape=volume[slice_idx].shape,
			)

		slice_image = volume[slice_idx]
		image_tensor = self._normalize_slice(slice_image)

		target: Dict[str, torch.Tensor] = {
			"boxes": torch.as_tensor(boxes, dtype=torch.float32),
			"labels": torch.as_tensor(labels, dtype=torch.int64),
			"series_id": series_id,
			"slice_index": torch.as_tensor(slice_idx, dtype=torch.int64),
			"is_hard_negative": torch.as_tensor(1 if is_hard_negative else 0, dtype=torch.int64),
		}
		return image_tensor, target

	def _choose_hard_negative_slice_index(
		self,
		series_id: str,
		depth: int,
		spacing_xyz: np.ndarray,
		origin_xyz: np.ndarray,
		sample_seed: int,
	) -> int:
		"""Choose a slice far from annotated nodules for hard-negative training."""
		if depth <= 1:
			return 0

		series_annot = self.annotations[self.annotations["seriesuid"].astype(str) == series_id]
		if len(series_annot) == 0:
			return int(sample_seed % depth)

		z_mm = series_annot["coordZ"].astype(float).to_numpy()
		z_vox = (z_mm - origin_xyz[2]) / spacing_xyz[2]
		z_vox = np.clip(np.round(z_vox), 0, max(depth - 1, 0)).astype(np.int32)
		exclusion = max(3, self.slice_tolerance * 2)

		candidates = [
			z for z in range(depth)
			if np.all(np.abs(z_vox - z) > exclusion)
		]

		if not candidates:
			return int((sample_seed * 7) % depth)

		return int(candidates[sample_seed % len(candidates)])

	def _load_volume(self, series_id: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
		if self.cache and series_id in self._volume_cache:
			return self._volume_cache[series_id]

		mhd_path = self._series_paths[series_id]
		image = sitk.ReadImage(str(mhd_path))

		# sitk.GetArrayFromImage returns volume as [z, y, x]
		volume = sitk.GetArrayFromImage(image).astype(np.float32)
		spacing_xyz = np.array(image.GetSpacing(), dtype=np.float32)
		origin_xyz = np.array(image.GetOrigin(), dtype=np.float32)

		if self.cache:
			self._volume_cache[series_id] = (volume, spacing_xyz, origin_xyz)
		return volume, spacing_xyz, origin_xyz

	def _choose_slice_index(
		self,
		series_id: str,
		depth: int,
		spacing_xyz: np.ndarray,
		origin_xyz: np.ndarray,
	) -> int:
		series_annot = self.annotations[self.annotations["seriesuid"].astype(str) == series_id]
		if len(series_annot) == 0:
			return depth // 2

		z_mm = series_annot["coordZ"].astype(float).to_numpy()
		z_vox = (z_mm - origin_xyz[2]) / spacing_xyz[2]
		z_vox = np.clip(np.round(z_vox), 0, max(depth - 1, 0)).astype(np.int32)
		if len(z_vox) == 0:
			return depth // 2
		return int(np.median(z_vox))

	def _normalize_slice(self, slice_image: np.ndarray) -> torch.Tensor:
		# Typical CT clipping range for lung windows.
		slice_image = np.clip(slice_image, -1000.0, 400.0)
		slice_image = (slice_image + 1000.0) / 1400.0
		slice_image = slice_image.astype(np.float32)
		return torch.from_numpy(slice_image).unsqueeze(0)

	def _get_bounding_boxes(
		self,
		series_id: str,
		slice_idx: int,
		spacing_xyz: np.ndarray,
		origin_xyz: np.ndarray,
		image_shape: Tuple[int, int],
	) -> Tuple[np.ndarray, np.ndarray]:
		boxes: List[List[float]] = []
		labels: List[int] = []

		height, width = image_shape
		series_annot = self.annotations[self.annotations["seriesuid"].astype(str) == series_id]

		for _, row in series_annot.iterrows():
			x_mm = float(row["coordX"])
			y_mm = float(row["coordY"])
			z_mm = float(row["coordZ"])
			diameter_mm = float(row["diameter_mm"])

			x_px = (x_mm - origin_xyz[0]) / spacing_xyz[0]
			y_px = (y_mm - origin_xyz[1]) / spacing_xyz[1]
			z_px = (z_mm - origin_xyz[2]) / spacing_xyz[2]

			if abs(z_px - float(slice_idx)) > float(self.slice_tolerance):
				continue

			radius_x = (diameter_mm / 2.0) / spacing_xyz[0]
			radius_y = (diameter_mm / 2.0) / spacing_xyz[1]

			x1 = max(0.0, x_px - radius_x)
			y1 = max(0.0, y_px - radius_y)
			x2 = min(float(width - 1), x_px + radius_x)
			y2 = min(float(height - 1), y_px + radius_y)

			if x2 > x1 and y2 > y1:
				boxes.append([x1, y1, x2, y2])
				labels.append(1)

		if not boxes:
			return np.zeros((0, 4), dtype=np.float32), np.zeros((0,), dtype=np.int64)

		return np.asarray(boxes, dtype=np.float32), np.asarray(labels, dtype=np.int64)


def get_luna_dataloader(
	data_dir: Union[str, Path],
	annotations_file: Union[str, Path],
	batch_size: int = 2,
	shuffle: bool = True,
	num_workers: int = 0,
	subset: Optional[Union[int, str]] = None,
	subset_folders: Optional[Sequence[str]] = None,
	cache: bool = True,
	hard_negative_ratio: float = 0.0,
) -> DataLoader:
	"""Create a DataLoader for the LUNA16 detection dataset."""
	dataset = LUNADataset(
		data_dir=data_dir,
		annotations_file=annotations_file,
		subset=subset,
		subset_folders=subset_folders,
		cache=cache,
		hard_negative_ratio=hard_negative_ratio,
	)

	def collate_fn(batch: List[Tuple[torch.Tensor, Dict[str, torch.Tensor]]]):
		images = [img for img, _ in batch]
		targets = [target for _, target in batch]
		return images, targets

	return DataLoader(
		dataset,
		batch_size=batch_size,
		shuffle=shuffle,
		num_workers=num_workers,
		collate_fn=collate_fn,
	)


__all__ = ["LUNADataset", "get_luna_dataloader"]
