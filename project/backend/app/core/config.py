from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Lung Nodule Detection API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    MODEL_PATH: str | None = None

    SECRET_KEY: str = Field("dev-only-change-me-please-123456", min_length=24)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "sqlite:////tmp/backend_dev.db"

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
    UPLOAD_DIR: str = "uploads/scans"
    MODEL_WEIGHTS_PATH: str = "models/finetuned/retinanet_lung_best.pth"
    DETECTOR_TYPE: str = "hybrid"  # Using hybrid 2D RetinaNet with proper deduplication
    RETINANET_MODEL_PATH: str = "models/finetuned/retinanet_lung_best.pth"
    CONFIDENCE_THRESHOLD: float = 0.03  # Slightly more sensitive default to reduce missed nodules
    # NOTE: Model needs LUNA16 fine-tuning for proper accuracy. See training/README.md
    DISABLE_FILTERS_FOR_TESTING: bool = False  # If True, bypass all filters regardless of individual toggles
    USE_LUNG_MASK: bool = True
    USE_SIZE_FILTER: bool = True  # Keep only small nodule-like boxes
    USE_ROI_FILTER: bool = False  # Less strict spatial filtering improves recall on varied scans
    ROI_MIN_RATIO: float = 0.1  # Center-region filter (10%-90%)
    ROI_MAX_RATIO: float = 0.9
    MIN_BOX_SIZE_PX: int = 5  # Strict size bounds for nodules
    MAX_BOX_SIZE_PX: int = 40
    NMS_IOU_THRESHOLD_2D: float = 0.3
    POST_FILTER_SCORE_THRESHOLD: float = 0.04
    TOP_K_2D_DETECTIONS: int = 8
    DETECTION_SAMPLE_EVERY_N_SLICES: int = 1
    ENABLE_DOMAIN_GUARD: bool = False
    DOMAIN_GUARD_MIN_MEAN: float = 0.1
    DOMAIN_GUARD_MAX_MEAN: float = 0.8
    DOMAIN_GUARD_REJECT_MULTICHANNEL_2D: bool = True
    DOMAIN_GUARD_MAX_CHANNEL_DELTA: float = 8.0
    DEBUG_PRINT_RAW_OUTPUTS: bool = True  # Step 2: print outputs[0]['scores'] and boxes heads
    DEBUG_MID_CONF_ONLY: bool = False  # If True, only keep detections with 0.1 < score < 0.4 (debug)
    PRINT_DEBUG_COUNTS: bool = True  # Print raw/filtered/final detection counts
    FALLBACK_TO_RAW_IF_EMPTY: bool = True  # If filters suppress everything, return strongest raw candidates
    MAX_RAW_FALLBACK_DETECTIONS: int = 10
    MIN_NODULE_SIZE_MM: float = 3.0
    NMS_IOU_THRESHOLD: float = 0.3
    DETECTION_STRIDE: int = 32
    MAX_UPLOAD_SIZE_MB: int = 500
    ALLOWED_UPLOAD_EXTENSIONS: str = ".nii,.nii.gz,.mhd,.jpg,.jpeg,.png,.dcm"
    APP_ENV: str = "development"


settings = Settings()
