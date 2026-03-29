import numpy as np
from PIL import Image
from src import infer


def test_detect_boxes_and_nms():
    # Create two overlapping blobs
    arr = np.zeros((256,256), dtype=np.uint8)
    arr[50:120, 50:120] = 255
    arr[70:140, 70:140] = 255
    img = Image.fromarray(arr)

    boxes = infer.detect_boxes(None, img)
    assert len(boxes) >= 1

    # Apply NMS with high IoU threshold -> should reduce overlapping boxes
    boxes_nms = infer.nms(boxes, iou_threshold=0.1)
    assert len(boxes_nms) <= len(boxes)


def test_draw_boxes_creates_image(tmp_path):
    arr = np.zeros((128,128), dtype=np.uint8)
    arr[30:60, 40:80] = 255
    img = Image.fromarray(arr)
    boxes = infer.detect_boxes(None, img)
    boxed = infer.draw_boxes(img, boxes)
    out = tmp_path / "boxed.png"
    boxed.save(out)
    assert out.exists()
