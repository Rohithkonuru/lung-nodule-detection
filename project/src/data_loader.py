import SimpleITK as sitk
import numpy as np

def load_ct_scan(path):
    """
    Reads .mhd CT scan and returns numpy array
    """
    scan = sitk.ReadImage(path)
    scan_array = sitk.GetArrayFromImage(scan)
    return scan_array
