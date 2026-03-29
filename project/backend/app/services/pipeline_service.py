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
            max_mean = float(getattr(settings, "DOMAIN_GUARD_MAX_MEAN", 0.8))
            if mean_intensity < min_mean or mean_intensity > max_mean:
                runtime = time.time() - start_time
                return {
                    'success': False,
                    'error': (
                        f"Invalid CT scan: mean intensity {mean_intensity:.3f} "
                        f"outside [{min_mean:.2f}, {max_mean:.2f}]"
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
            sample_every_n_slices=2,  # Process every 2nd slice for speed
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
            fallback_to_raw_if_empty=bool(getattr(settings, "FALLBACK_TO_RAW_IF_EMPTY", True)),
            max_raw_fallback_detections=int(getattr(settings, "MAX_RAW_FALLBACK_DETECTIONS", 10)),
        )
        
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
    except Exception as exc:
        raise RuntimeError("RAG report generator dependencies are not available.") from exc

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
