import os
import sys
import csv
from PIL import Image

sys.path.insert(0, os.path.abspath('.'))

from src.ensemble import predict_ensemble, get_model_paths
from src.data_loader import load_ct_scan
from src.preprocessing import preprocess_scan

CSV = 'val_small.csv'
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'models')

items = []
with open(CSV, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        p, lbl = line.split(',')
        items.append((p.strip(), int(lbl.strip())))

if not items:
    print('No items in', CSV)
    sys.exit(1)

model_paths = get_model_paths(MODELS_DIR)
print('Model paths (sorted):')
for p in model_paths:
    try:
        print(' -', os.path.basename(p), 'size=', os.path.getsize(p))
    except Exception:
        print(' -', os.path.basename(p))

correct = 0
scores = []
count = 0
MAX = 50
for path, label in items[:MAX]:
    try:
        scan = load_ct_scan(path)
        vol = preprocess_scan(scan, size=256)
        arr = (vol[len(vol)//2] * 255).astype('uint8')
        img = Image.fromarray(arr)
        score = predict_ensemble(MODELS_DIR, img)
        pred = 1 if score >= 0.5 else 0
        correct += int(pred == label)
        scores.append(score)
        count += 1
    except Exception as e:
        print('ERROR processing', path, e)

if count:
    acc = correct / count
    avg = sum(scores)/len(scores) if scores else 0.0
    print(f'Processed {count} items. Accuracy={acc*100:.2f}% avg_score={avg:.3f}')
else:
    print('No items processed')
