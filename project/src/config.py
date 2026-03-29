import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DATA_RAW = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")

IMAGE_SIZE = 256
BATCH_SIZE = 2
EPOCHS = 5
LEARNING_RATE = 1e-4

DEVICE = "cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu"
