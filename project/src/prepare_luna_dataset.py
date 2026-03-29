import os
import csv
import random

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LUNA_DIR = os.path.join(BASE, 'luna datasets')


def load_annotations(path):
    series_with_nodule = set()
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            series_with_nodule.add(r['seriesuid'].strip())
    return series_with_nodule


def find_mhd_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith('.mhd'):
                files.append(os.path.join(dirpath, fn))
    return files


def prepare_csv(out_train='train_luna.csv', out_val='val_luna.csv', val_frac=0.2, seed=42):
    ann_path = os.path.join(LUNA_DIR, 'annotations.csv')
    if not os.path.exists(ann_path):
        raise FileNotFoundError('annotations.csv not found in luna datasets')

    pos_series = load_annotations(ann_path)
    mhd_files = find_mhd_files(LUNA_DIR)
    items = []
    for p in mhd_files:
        fn = os.path.basename(p)
        seriesuid = os.path.splitext(fn)[0]
        label = 1 if seriesuid in pos_series else 0
        items.append((p.replace('\\', '/'), label))

    random.seed(seed)
    random.shuffle(items)
    nval = int(len(items) * val_frac)
    val = items[:nval]
    train = items[nval:]

    def write(path, rows):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            for p, lbl in rows:
                w.writerow([p, lbl])

    write(os.path.join(BASE, out_train), train)
    write(os.path.join(BASE, out_val), val)
    return os.path.join(BASE, out_train), os.path.join(BASE, out_val)


if __name__ == '__main__':
    t, v = prepare_csv()
    print('Wrote:', t, v)
