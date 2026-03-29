"""
Helper script to prepare and validate LUNA16 annotations.csv
Creates annotations.csv if it doesn't exist or validates existing file.
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path
import SimpleITK as sitk

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_mhd_files(data_dir):
    """Find all .mhd files in dataset directory."""
    data_path = Path(data_dir)
    mhd_files = list(data_path.glob("**/subset*/*.mhd"))
    
    logger.info(f"Found {len(mhd_files)} MHD files in {data_dir}")
    return sorted(mhd_files)


def extract_series_uid_from_filename(mhd_path):
    """
    Extract series UID from MHD filename.
    LUNA16 files are typically named: <seriesuid>.mhd
    """
    filename = Path(mhd_path).stem  # Remove .mhd extension
    return filename


def create_dummy_annotations(data_dir, output_file='data/annotations.csv'):
    """
    Create a sample annotations.csv file with dummy nodule data.
    This is for testing purposes when actual annotations are not available.
    
    Args:
        data_dir: Path to dataset directory
        output_file: Output CSV file path
    """
    logger.warning("Creating DUMMY annotations file for testing purposes")
    logger.warning("This uses synthetic nodule positions - for real training, use actual LUNA16 annotations")
    
    mhd_files = find_mhd_files(data_dir)
    
    if not mhd_files:
        logger.error(f"No MHD files found in {data_dir}")
        return False
    
    # Create dummy annotations
    records = []
    
    for mhd_file in mhd_files[:10]:  # Limit to first 10 for demo
        series_uid = extract_series_uid_from_filename(mhd_file)
        
        try:
            # Load image to get dimensions
            image = sitk.ReadImage(str(mhd_file))
            size = image.GetSize()  # (x, y, z)
            spacing = image.GetSpacing()  # (x, y, z)
            
            # Create 2-3 dummy nodules per scan
            for i in range(2):
                # Random nodule position (in mm, world coordinates)
                x_mm = (size[0] * spacing[0]) * (0.3 + i * 0.2)
                y_mm = (size[1] * spacing[1]) * 0.5
                z_mm = (size[2] * spacing[2]) * 0.5
                diameter_mm = 8.0  # 8mm nodule diameter
                
                records.append({
                    'seriesuid': series_uid,
                    'coordX': x_mm,
                    'coordY': y_mm,
                    'coordZ': z_mm,
                    'diameter_mm': diameter_mm
                })
        
        except Exception as e:
            logger.warning(f"Failed to process {mhd_file}: {e}")
    
    # Save to CSV
    df = pd.DataFrame(records)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    logger.info(f"Created dummy annotations file: {output_file}")
    logger.info(f"  Series: {df['seriesuid'].nunique()}")
    logger.info(f"  Total nodules: {len(df)}")
    logger.info(f"  Columns: {list(df.columns)}")
    
    return True


def validate_annotations(annotations_file, data_dir):
    """
    Validate annotations.csv file format and consistency.
    
    Args:
        annotations_file: Path to annotations.csv
        data_dir: Path to dataset directory
    
    Returns:
        bool: True if valid, False otherwise
    """
    annotations_path = Path(annotations_file)
    
    if not annotations_path.exists():
        logger.error(f"Annotations file not found: {annotations_file}")
        return False
    
    try:
        df = pd.read_csv(annotations_file)
    except Exception as e:
        logger.error(f"Failed to read annotations file: {e}")
        return False
    
    # Check required columns
    required_cols = ['seriesuid', 'coordX', 'coordY', 'coordZ', 'diameter_mm']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        logger.error(f"Found columns: {list(df.columns)}")
        return False
    
    # Check for missing values
    if df.isnull().any().any():
        logger.warning(f"Found missing values in annotations")
        logger.warning(f"\n{df.isnull().sum()}")
    
    # Get list of MHD files
    mhd_files = find_mhd_files(data_dir)
    available_series = {extract_series_uid_from_filename(f) for f in mhd_files}
    
    # Check if all series in annotations exist
    annotation_series = set(df['seriesuid'].unique())
    missing_series = annotation_series - available_series
    
    if missing_series:
        logger.warning(f"Series in annotations but not in data directory: {len(missing_series)}")
        for s in list(missing_series)[:5]:
            logger.warning(f"  - {s}")
    
    extra_series = available_series - annotation_series
    if extra_series:
        logger.warning(f"Series in data directory but not in annotations: {len(extra_series)}")
        logger.warning(f"  (These scans have no nodules)")
    
    # Validation summary
    logger.info("\n" + "=" * 60)
    logger.info("ANNOTATIONS VALIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✓ File format: Valid CSV")
    logger.info(f"✓ Required columns: Present")
    logger.info(f"✓ Series with annotations: {len(annotation_series)}")
    logger.info(f"✓ Total annotated nodules: {len(df)}")
    logger.info(f"✓ Coordinate ranges:")
    logger.info(f"    X: [{df['coordX'].min():.1f}, {df['coordX'].max():.1f}]")
    logger.info(f"    Y: [{df['coordY'].min():.1f}, {df['coordY'].max():.1f}]")
    logger.info(f"    Z: [{df['coordZ'].min():.1f}, {df['coordZ'].max():.1f}]")
    logger.info(f"✓ Diameter range: [{df['diameter_mm'].min():.1f}, {df['diameter_mm'].max():.1f}] mm")
    logger.info("=" * 60 + "\n")
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Prepare and validate LUNA16 annotations.csv'
    )
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Path to LUNA16 dataset directory')
    parser.add_argument('--annotations', type=str, default='data/annotations.csv',
                        help='Path to annotations.csv')
    parser.add_argument('--create-dummy', action='store_true',
                        help='Create dummy annotations for testing (use real annotations for actual training)')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only validate existing annotations, do not create new')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("LUNA16 Annotations Preparation Tool")
    logger.info("=" * 60 + "\n")
    
    # Check if annotations exist
    annotations_path = Path(args.annotations)
    
    if annotations_path.exists():
        logger.info(f"Found existing annotations: {args.annotations}")
        validate_annotations(args.annotations, args.data_dir)
    else:
        logger.info(f"No annotations found at: {args.annotations}")
        
        if args.validate_only:
            logger.error("Cannot validate - file does not exist")
            sys.exit(1)
        
        if args.create_dummy:
            create_dummy_annotations(args.data_dir, args.annotations)
        else:
            logger.error("\nNo annotations.csv found!")
            logger.error(f"Expected at: {args.annotations}")
            logger.error("\nTo create dummy annotations for testing, run:")
            logger.error(f"  python prepare_luna_annotations.py --create-dummy")
            logger.error("\nFor real training, ensure annotations.csv contains:")
            logger.error("  - seriesuid: Unique CT scan identifier")
            logger.error("  - coordX, coordY, coordZ: Nodule center in mm (world coordinates)")
            logger.error("  - diameter_mm: Nodule diameter in millimeters")
            sys.exit(1)


if __name__ == "__main__":
    main()
