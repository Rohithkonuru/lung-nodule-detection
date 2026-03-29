#!/usr/bin/env python3
import torch
import os

models = ['models/retinanet_best.pth', 'models/transfer_demo.pth']

for path in models:
    print(f'\n=== {os.path.basename(path)} ===')
    try:
        ckpt = torch.load(path, map_location='cpu')
        if isinstance(ckpt, dict) and 'model_state_dict' in ckpt:
            state = ckpt['model_state_dict']
        else:
            state = ckpt
        
        print(f'Keys: {len(state)} total')
        
        # Categorize
        has_legacy = any(k.startswith('features.') for k in state.keys())
        has_modern = any(k.startswith(('conv1', 'layer', 'bn1')) for k in state.keys())
        
        if has_legacy:
            print('Type: LEGACY 2D (features/classifier)')
        elif has_modern:
            print('Type: MODERN 3D (ResNet)')
        else:
            print('Type: UNKNOWN')
        
        # First 5 keys
        for k in list(state.keys())[:5]:
            v = state[k]
            shp = v.shape if hasattr(v, 'shape') else 'scalar'
            print(f'  {k}: {shp}')
    except Exception as e:
        print(f'Error: {e}')
