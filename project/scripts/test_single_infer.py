import os, sys
sys.path.insert(0, os.path.abspath('.'))
from PIL import Image
from src.data_loader import load_ct_scan
from src.preprocessing import preprocess_scan
from src import infer
from src.ensemble import get_model_paths

# pick sample
sample = 'data/samples/sample_scan.mhd'
if not os.path.exists(sample):
    print('Sample not found:', sample)
    sys.exit(1)

scan = load_ct_scan(sample)
vol = preprocess_scan(scan, size=256)
arr = (vol[len(vol)//2] * 255).astype('uint8')
img = Image.fromarray(arr)

models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')
paths = get_model_paths(models_dir)
print('Model paths:', paths)

# select retina candidate
candidate = None
for p in reversed(paths):
    try:
        if os.path.getsize(p) == 0:
            continue
    except Exception:
        continue
    if 'retina' in os.path.basename(p).lower() or 'retinanet' in os.path.basename(p).lower():
        candidate = p
        break
if candidate is None:
    for p in reversed(paths):
        try:
            if os.path.getsize(p) > 0:
                candidate = p
                break
        except Exception:
            continue

print('Using candidate for detection:', candidate)
primary_model = None
if candidate and infer.is_torch_available():
    try:
        primary_model = infer.load_model(candidate, device='cpu')
        print('Loaded primary model OK')
    except Exception as e:
        print('Failed to load primary model:', e)

score = 0.0
try:
    from src.ensemble import predict_ensemble
    score = predict_ensemble(models_dir, img)
    print('Ensemble score:', score)
except Exception as e:
    print('Ensemble error:', e)

boxes = infer.detect_boxes_with_options(primary_model, img, conf_thresh=0.1, apply_nms=True)
print('Boxes found:', boxes)

# draw and save
boxed = infer.draw_boxes(img, boxes)
out = os.path.join('outputs', 'predictions', 'debug_boxed.png')
os.makedirs(os.path.dirname(out), exist_ok=True)
boxed.save(out)
print('Saved boxed image to', out)
