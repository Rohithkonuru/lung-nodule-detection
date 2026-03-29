import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
import hashlib

import numpy as np

from app.core.config import settings


_LAST_PROCESSED_IMAGE_HASH: str | None = None


def _project_root() -> Path:
    # backend/app/services/pipeline_service.py -> project root at parent index 3
    return Path(__file__).resolve().parents[3]


def _import_run_detection():
    try:
        from src.ml import run_detection
        return run_detection
    except Exception:
        project_root = str(_project_root())
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from src.ml import run_detection
        return run_detection


def _resolve_model_path(model_path: str) -> str:
    raw = Path(model_path)
    if raw.exists():
        return str(raw)

    candidate = _project_root() / model_path
    if candidate.exists():
        return str(candidate)

    return model_path


def _heuristic_2d_nodule_candidates(slice_image: np.ndarray, z_index: int = 0, max_candidates: int = 15) -> list[dict]:
    """Detect micronodules and small nodules using multi-scale, cascade thresholding approach.
    
    Enhanced for dense micronodule detection with:
    - Multi-scale morphological processing
    - Cascade thresholding at multiple percentiles
    - Better handling of small structures (2-5 pixels)
    - Adaptive intensity-based confidence scoring
    - Improved lung/mediastinum separation
    """
    import SimpleITK as sitk

    arr = slice_image.astype(np.float32)
    arr_min = float(np.min(arr))
    arr_max = float(np.max(arr))
    if arr_max - arr_min < 1e-6:
        return []

    norm = (arr - arr_min) / (arr_max - arr_min + 1e-6)

    # Improved lung region detection: separate lungs from mediastinum using multi-level approach
    lung_threshold = float(np.percentile(norm, 40))  # More generous lung inclusion
    lung_seed = (norm <= lung_threshold).astype(np.uint8)
    lung_img = sitk.GetImageFromArray(lung_seed)
    lung_cc = sitk.ConnectedComponent(lung_img)
    stats = sitk.LabelShapeStatisticsImageFilter()
    stats.Execute(lung_cc)

    # Get largest lung regions (usually 2 lungs)
    labels = sorted(
        [(label, stats.GetPhysicalSize(label)) for label in stats.GetLabels()],
        key=lambda x: x[1],
        reverse=True,
    )
    keep = {label for label, _ in labels[:3]}  # Keep top 3 regions for bilateral lungs + edge
    lung_arr = np.isin(sitk.GetArrayFromImage(lung_cc), list(keep)).astype(np.uint8)
    
    # Multi-scale morphological processing for better structure preservation
    lung_arr = sitk.GetArrayFromImage(
        sitk.BinaryDilate(
            sitk.BinaryFillhole(sitk.GetImageFromArray(lung_arr)),
            [4, 4],  # Larger dilation for better lung coverage
        )
    ).astype(bool)
    
    if not np.any(lung_arr):
        lung_arr = np.ones_like(norm, dtype=bool)

    lung_values = norm[lung_arr]
    if lung_values.size == 0:
        return []

    # CASCADE THRESHOLDING: Try multiple percentiles for maximum detection
    dets: list[dict] = []
    percentiles_to_try = [99.9, 99.8, 99.7, 99.5, 99.2, 99.0, 98.5, 98.0, 97.5, 97.0]
    
    # Adaptive baseline: use low percentile of lung for more sensitive detection
    lung_p20 = float(np.percentile(lung_values, 20))
    lung_p50 = float(np.percentile(lung_values, 50))
    min_intensity_baseline = lung_p50 + (lung_p50 - lung_p20) * 0.8  # Key for micronodule = significantly brighter than lung center
    min_intensity_baseline = max(0.50, min(min_intensity_baseline, 0.85))  # Clamp to reasonable range
    
    for p_idx, p in enumerate(percentiles_to_try):
        # Progressive threshold lowering - more aggressive for higher percentiles
        threshold_reduction = (p_idx * 0.06) if p_idx < 5 else (0.3 + (p_idx - 5) * 0.05)
        thr = max(min_intensity_baseline - threshold_reduction, 0.45)
        mask = (norm >= thr) & lung_arr
        candidate_count = int(np.sum(mask))
        
        if candidate_count < 1:  # Accept even single bright pixels
            continue

        # Multi-scale morphological closing to enhance nodule structure
        candidate_mask_img = sitk.GetImageFromArray(mask.astype(np.uint8))
        candidate_mask_img = sitk.BinaryMorphologicalClosing(candidate_mask_img, [1, 1])
        candidate_mask = sitk.GetArrayFromImage(candidate_mask_img).astype(bool)
        
        cand_img = sitk.GetImageFromArray(candidate_mask.astype(np.uint8))
        cand_cc = sitk.ConnectedComponent(cand_img)
        cand_stats = sitk.LabelShapeStatisticsImageFilter()
        cand_stats.Execute(cand_cc)
        cand_arr = sitk.GetArrayFromImage(cand_cc)

        for label in cand_stats.GetLabels():
            area = int(cand_stats.GetNumberOfPixels(label))
            # Accept much smaller structures for micronodule detection
            if area < 2 or area > 500:
                continue

            x, y, w, h = cand_stats.GetBoundingBox(label)
            if w <= 0 or h <= 0:
                continue

            aspect = float(max(w, h)) / float(max(1, min(w, h)))
            fill_ratio = float(area) / float(max(1, w * h))
            
            # More permissive for small structures
            if aspect > 2.5 or fill_ratio < 0.20:
                continue

            vals = norm[cand_arr == label]
            if vals.size == 0:
                continue

            # Check if already detected (avoid duplicates)
            cx = int(round(x + w / 2.0))
            cy = int(round(y + h / 2.0))
            is_duplicate = False
            for existing in dets:
                ex_center = existing.get("center", (0, 0, 0))
                dist_sq = (cx - ex_center[2]) ** 2 + (cy - ex_center[1]) ** 2
                if dist_sq < 4:  # Within 2 pixels
                    is_duplicate = True
                    break
            
            if is_duplicate:
                continue

            # Enhanced confidence scoring: intensity + compactness + size + location
            intensity_score = min(1.0, max(0.0, (float(np.mean(vals)) - min_intensity_baseline) / (1.0 - min_intensity_baseline + 1e-6)))
            compactness_score = fill_ratio
            size_bonus = min(1.0, float(area) / 100.0) * 0.25  # Bonus for nodule-sized structures
            percentile_bonus = (len(percentiles_to_try) - p_idx) / len(percentiles_to_try) * 0.15  # Earlier percentiles = higher confidence
            
            conf = float(np.clip(
                0.40 + intensity_score * 0.30 + compactness_score * 0.25 + size_bonus + percentile_bonus,
                0.40,
                0.98
            ))
            
            dets.append(
                {
                    "center": (int(z_index), int(cy), int(cx)),
                    "confidence": conf,
                    "size_mm": float(max(w, h)),
                    "num_slices": 1,
                    "bbox_zyx": (int(z_index), int(y), int(x), int(z_index), int(y + h), int(x + w)),
                }
            )

    # Remove near-duplicates before final sort
    final_dets = []
    sorted_dets = sorted(dets, key=lambda d: float(d.get("confidence", 0.0)), reverse=True)
    
    for det in sorted_dets:
        is_dup = False
        for final_det in final_dets:
            d_center = det.get("center", (0, 0, 0))
            f_center = final_det.get("center", (0, 0, 0))
            dist_sq = (d_center[2] - f_center[2]) ** 2 + (d_center[1] - f_center[1]) ** 2
            if dist_sq < 9:  # Within 3 pixels
                is_dup = True
                break
        
        if not is_dup:
            final_dets.append(det)
            if len(final_dets) >= max_candidates:
                break

    return final_dets


@dataclass
class AnalysisResult:
    num_detections: int
    confidence_score: float
    avg_size_mm: float
    detections: list[dict]
    runtime: float


def analyze_scan(file_path: str) -> AnalysisResult:
    if not os.path.exists(file_path):
        raise FileNotFoundError("Scan file not found")

    try:
        # Lazy import prevents FastAPI startup failures when optional ML deps are not installed yet.
        run_detection = _import_run_detection()
    except Exception as exc:
        raise RuntimeError(
            "ML dependencies are not available. Install backend/requirements-ml.txt to enable analysis."
        ) from exc

    # Use hybrid detector (2D RetinaNet) if configured
    if settings.DETECTOR_TYPE == "hybrid":
        result = _analyze_scan_hybrid(file_path)
    else:
        # Default: 3D detector pipeline
        model_path = _resolve_model_path(settings.MODEL_WEIGHTS_PATH)
        result = run_detection(
            file_path,
            confidence_threshold=settings.CONFIDENCE_THRESHOLD,
            min_size_mm=settings.MIN_NODULE_SIZE_MM,
            model_path=model_path,
            stride=settings.DETECTION_STRIDE,
            iou_threshold=settings.NMS_IOU_THRESHOLD,
        )
    
    if not result.get("success"):
        error_msg = result.get("error", "Detection failed")
        if bool(result.get("invalid_input", False)):
            raise ValueError(error_msg)
        raise RuntimeError(error_msg)

    detections = result.get("detections", [])
    avg_conf = float(np.mean([d["confidence"] for d in detections])) if detections else 0.0
    avg_size = float(np.mean([d["size_mm"] for d in detections])) if detections else 0.0

    return AnalysisResult(
        num_detections=len(detections),
        confidence_score=avg_conf,
        avg_size_mm=avg_size,
        detections=detections,
        runtime=float(result.get("runtime", 0.0)),
    )


def _analyze_scan_hybrid(file_path: str) -> dict:
    """
    Analyze using hybrid 3D+2D RetinaNet detector.
    
    Pipeline:
    1. Load and preprocess 3D CT
    2. Extract 2D slices
    3. Run 2D RetinaNet on each slice
    4. Aggregate detections to 3D
    """
    import time
    import SimpleITK as sitk
    from src.ml.preprocessing import get_preprocessor
    from src.ml.detection.hybrid_detector import Hybrid3D2DDetector
    
    start_time = time.time()
    
    try:
        if bool(getattr(settings, "DEBUG_PRINT_RAW_OUTPUTS", False)) or bool(getattr(settings, "PRINT_DEBUG_COUNTS", False)):
            print(f"Running fresh detection for file: {file_path}")
            if os.path.exists(file_path):
                print(f"Input file size bytes: {os.path.getsize(file_path)}")

        # Load image
        image = sitk.ReadImage(file_path)

        if bool(getattr(settings, "ENABLE_DOMAIN_GUARD", False)) and bool(
            getattr(settings, "DOMAIN_GUARD_REJECT_MULTICHANNEL_2D", True)
        ):
            if image.GetDimension() == 2 and image.GetNumberOfComponentsPerPixel() > 1:
                raw_arr = sitk.GetArrayFromImage(image)
                max_delta = 0.0
                if raw_arr.ndim == 3 and raw_arr.shape[-1] >= 3:
                    arr = raw_arr.astype(np.float32)
                    rg = float(np.mean(np.abs(arr[..., 0] - arr[..., 1])))
                    gb = float(np.mean(np.abs(arr[..., 1] - arr[..., 2])))
                    rb = float(np.mean(np.abs(arr[..., 0] - arr[..., 2])))
                    max_delta = max(rg, gb, rb)

                max_allowed_delta = float(getattr(settings, "DOMAIN_GUARD_MAX_CHANNEL_DELTA", 8.0))
                if max_delta > max_allowed_delta:
                    runtime = time.time() - start_time
                    return {
                        'success': False,
                        'error': (
                            "Invalid CT scan: colorful multi-channel 2D image detected "
                            f"(channel delta {max_delta:.2f} > {max_allowed_delta:.2f}). "
                            "Please upload grayscale CT scan slices or volumetric CT files."
                        ),
                        'invalid_input': True,
                        'runtime': runtime,
                        'detector_type': 'hybrid_2d_retinanet',
                    }

        original_spacing_xyz = image.GetSpacing()
        original_spacing_zyx = (
            float(original_spacing_xyz[2]) if len(original_spacing_xyz) > 2 else 1.0,
            float(original_spacing_xyz[1]) if len(original_spacing_xyz) > 1 else 1.0,
            float(original_spacing_xyz[0]) if len(original_spacing_xyz) > 0 else 1.0,
        )
        
        # Preprocess
        preprocessor = get_preprocessor()
        processed = preprocessor.preprocess(image, apply_segmentation=True)
        processed_array = sitk.GetArrayFromImage(processed)

        if bool(getattr(settings, "ENABLE_DOMAIN_GUARD", False)):
            mean_intensity = float(np.mean(processed_array))
            min_mean = float(getattr(settings, "DOMAIN_GUARD_MIN_MEAN", 0.1))
            max_mean = float(getattr(settings, "DOMAIN_GUARD_MAX_MEAN", 0.9))

            # 2D grayscale CT slices can be valid across a wider post-normalization mean range
            # depending on windowing and scanner/export settings. Keep strict upper/lower mean
            # guard only for volumetric scans, and keep a lower-bound sanity check for 2D.
            is_2d_grayscale = image.GetDimension() == 2 and image.GetNumberOfComponentsPerPixel() == 1
            if is_2d_grayscale:
                if mean_intensity < min_mean:
                    runtime = time.time() - start_time
                    return {
                        'success': False,
                        'error': (
                            "Invalid CT scan: grayscale image appears too dark after preprocessing "
                            f"(mean {mean_intensity:.3f} < {min_mean:.2f}). "
                            "Try a lung-windowed grayscale CT slice or upload a .mhd/.nii volume."
                        ),
                        'invalid_input': True,
                        'runtime': runtime,
                        'detector_type': 'hybrid_2d_retinanet',
                    }
            else:
                if mean_intensity < min_mean or mean_intensity > max_mean:
                    runtime = time.time() - start_time
                    return {
                        'success': False,
                        'error': (
                            "Invalid CT scan: intensity distribution is outside accepted range "
                            f"(mean={mean_intensity:.3f}, expected {min_mean:.2f}-{max_mean:.2f}). "
                            "Use a grayscale CT slice or upload a .mhd/.nii CT volume."
                        ),
                        'invalid_input': True,
                        'runtime': runtime,
                        'detector_type': 'hybrid_2d_retinanet',
                    }

        if bool(getattr(settings, "DEBUG_PRINT_RAW_OUTPUTS", False)) or bool(getattr(settings, "PRINT_DEBUG_COUNTS", False)):
            global _LAST_PROCESSED_IMAGE_HASH
            processed_bytes = np.ascontiguousarray(processed_array).tobytes()
            processed_hash = hashlib.sha1(processed_bytes).hexdigest()[:16]
            print("Processed image shape:", tuple(processed_array.shape))
            print("Processed image sum:", float(np.sum(processed_array)))
            print("Processed IMAGE HASH:", hash(processed_bytes))
            print("Processed IMAGE SHA1:", processed_hash)
            print("Processed image hash same as previous:", processed_hash == _LAST_PROCESSED_IMAGE_HASH)
            _LAST_PROCESSED_IMAGE_HASH = processed_hash
        
        if processed_array.ndim == 2:
            processed_array = np.expand_dims(processed_array, axis=0)
        
        # Detect using hybrid 2D RetinaNet
        retinanet_path = _resolve_model_path(settings.RETINANET_MODEL_PATH)
        detector = Hybrid3D2DDetector(retinanet_model_path=retinanet_path)
        
        detections = detector.detect(
            processed_array,
            voxel_spacing_zyx=(1.0, 1.0, 1.0),
            confidence_threshold=max(0.0, float(settings.CONFIDENCE_THRESHOLD)),
            sample_every_n_slices=int(getattr(settings, "PROCESS_EVERY_NTH_SLICE", 1)),  # Process every slice
            disable_filters=bool(settings.DISABLE_FILTERS_FOR_TESTING),
            debug_mid_conf_only=bool(getattr(settings, "DEBUG_MID_CONF_ONLY", False)),
            use_lung_mask=bool(getattr(settings, "USE_LUNG_MASK", False)),
            use_size_filter=bool(getattr(settings, "USE_SIZE_FILTER", False)),
            use_roi_filter=bool(getattr(settings, "USE_ROI_FILTER", False)),
            min_size_px=int(getattr(settings, "MIN_BOX_SIZE_PX", 5)),
            max_size_px=int(getattr(settings, "MAX_BOX_SIZE_PX", 40)),
            roi_min_ratio=float(getattr(settings, "ROI_MIN_RATIO", 0.1)),
            roi_max_ratio=float(getattr(settings, "ROI_MAX_RATIO", 0.9)),
            nms_iou_threshold=float(getattr(settings, "NMS_IOU_THRESHOLD_2D", 0.3)),
            post_filter_score_threshold=float(getattr(settings, "POST_FILTER_SCORE_THRESHOLD", 0.06)),
            top_k_detections_per_slice=max(0, int(getattr(settings, "TOP_K_2D_DETECTIONS", 3))),
            debug_print_raw_outputs=bool(getattr(settings, "DEBUG_PRINT_RAW_OUTPUTS", True)),
            print_debug_counts=bool(getattr(settings, "PRINT_DEBUG_COUNTS", True)),
            fallback_to_raw_if_empty=bool(getattr(settings, "FALLBACK_TO_RAW_IF_EMPTY", False)),
            max_raw_fallback_detections=int(getattr(settings, "MAX_RAW_FALLBACK_DETECTIONS", 10)),
        )

        # For thin volumes (2D slices or few 3D slices), enhance with cascade heuristic
        if processed_array.ndim == 3 and processed_array.shape[0] <= 3:
            # Try heuristic cascade approach for better micronodule coverage
            heuristic_dets = []
            for slice_idx in range(processed_array.shape[0]):
                h_dets = _heuristic_2d_nodule_candidates(
                    processed_array[slice_idx],
                    z_index=slice_idx,
                    max_candidates=int(getattr(settings, "TOP_K_2D_DETECTIONS", 15)),
                )
                heuristic_dets.extend(h_dets)
            
            # If heuristic found many detections, use it; otherwise enhance model detections
            if len(heuristic_dets) >= 3:
                # Strong heuristic performance: use it as primary
                detections = sorted(heuristic_dets, key=lambda d: float(d.get("confidence", 0.0)), reverse=True)[:int(getattr(settings, "TOP_K_2D_DETECTIONS", 15))]
            elif len(heuristic_dets) > 0 and len(detections) == 0:
                # Model found nothing, heuristic found some: use heuristic
                detections = heuristic_dets
            elif len(heuristic_dets) > len(detections):
                # Heuristic outperformed model: prefer heuristic with some model results
                all_dets = sorted(detections + heuristic_dets, key=lambda d: float(d.get("confidence", 0.0)), reverse=True)
                detections = all_dets[:int(getattr(settings, "TOP_K_2D_DETECTIONS", 15))]
        
        runtime = time.time() - start_time
        
        return {
            'success': True,
            'detections': detections,
            'num_detections': len(detections),
            'runtime': runtime,
            'detector_type': 'hybrid_2d_retinanet',
        }
    
    except Exception as e:
        runtime = time.time() - start_time
        return {
            'success': False,
            'error': str(e),
            'runtime': runtime,
            'detector_type': 'hybrid_2d_retinanet',
        }


def detections_to_boxes_text(detections: list[dict]) -> str:
    return json.dumps(detections)


def generate_report_text(detections: list[dict]) -> tuple[str, dict]:
    try:
        from src.rag.production_report_generator import generate_clinical_report
        from src.rag.retriever import retrieve_nodule_guidelines
    except Exception:
        count = len(detections)
        max_size = max((float(d.get("size_mm", 0.0)) for d in detections), default=0.0)
        avg_conf = float(np.mean([float(d.get("confidence", 0.0)) for d in detections])) if detections else 0.0

        if count == 0:
            title = "No suspicious nodules detected"
            summary = "No high-confidence pulmonary nodules were identified in this scan."
            recommendations = [
                "Continue routine clinical follow-up as advised by your physician.",
                "Correlate with prior imaging if clinically indicated.",
            ]
        else:
            title = "Pulmonary nodule candidates detected"
            summary = (
                f"Detected {count} nodule candidate(s). "
                f"Maximum estimated size: {max_size:.1f} mm. "
                f"Average model confidence: {avg_conf * 100:.1f}%."
            )
            recommendations = [
                "Recommend radiologist review of highlighted regions.",
                "Correlate with prior CT and clinical risk factors.",
                "Consider follow-up low-dose CT based on guideline-based risk stratification.",
            ]

        lines = [
            "CLINICAL REPORT",
            "=" * 60,
            "",
            f"SUMMARY: {title}",
            summary,
            "",
            "RECOMMENDATIONS:",
            "-" * 60,
        ]
        lines.extend([f"- {r}" for r in recommendations])
        structured = {
            "summary": {"title": title, "text": summary},
            "recommendations": recommendations,
            "knowledge_context": "RAG unavailable; generated from detection statistics.",
        }
        return "\n".join(lines), structured

    max_size = max((float(d.get("size_mm", 0.0)) for d in detections), default=0.0)
    knowledge_context = retrieve_nodule_guidelines(size_mm=max_size, nodule_count=len(detections))
    structured = generate_clinical_report(
        detections,
        patient_info={
            "knowledge_context": knowledge_context,
        },
    )
    structured["knowledge_context"] = knowledge_context

    summary_title = structured.get("summary", {}).get("title", "Clinical Report")
    summary_text = structured.get("summary", {}).get("text", "")
    recommendations = structured.get("recommendations", [])

    lines = [
        "CLINICAL REPORT",
        "=" * 60,
        "",
        f"SUMMARY: {summary_title}",
        summary_text,
        "",
        "RECOMMENDATIONS:",
        "-" * 60,
    ]
    lines.extend([f"- {r}" for r in recommendations])
    report_text = "\n".join(lines)

    return report_text, structured
