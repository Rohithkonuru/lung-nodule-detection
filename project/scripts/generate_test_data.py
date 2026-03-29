"""
Generate synthetic CT scan data for testing the Lung Nodule Detection system
"""
import numpy as np
import json
from pathlib import Path


def generate_synthetic_ct_scan(output_path: str, width=256, height=256, depth=64, num_nodules=3):
    """
    Generate a synthetic CT scan with simulated lung nodules
    
    Args:
        output_path: Path to save the output file (.npy format)
        width: Image width in pixels
        height: Image height in pixels
        depth: Number of slices (depth)
        num_nodules: Number of synthetic nodules to add
    """
    # Create base lung tissue (normalized to Hounsfield Units)
    # Air: -1000, Lung tissue: -700 to -500, Tissue/Water: 0
    scan = np.full((depth, height, width), -700, dtype=np.int16)  # Lung tissue
    
    # Add some anatomical variation
    scan += np.random.randint(-50, 50, scan.shape)
    
    # Generate synthetic nodules
    nodule_positions = []
    for i in range(num_nodules):
        # Random position
        z = np.random.randint(10, depth - 10)
        y = np.random.randint(30, height - 30)
        x = np.random.randint(30, width - 30)
        
        # Random size (radius in pixels)
        radius = np.random.randint(5, 15)
        
        # Create nodule using simple sphere logic
        z_min, z_max = max(0, z - radius), min(depth, z + radius + 1)
        y_min, y_max = max(0, y - radius), min(height, y + radius + 1)
        x_min, x_max = max(0, x - radius), min(width, x + radius + 1)
        
        for zz in range(z_min, z_max):
            for yy in range(y_min, y_max):
                for xx in range(x_min, x_max):
                    dist = np.sqrt((zz - z)**2 + (yy - y)**2 + (xx - x)**2)
                    if dist <= radius:
                        scan[zz, yy, xx] = np.random.randint(30, 100)
        
        nodule_positions.append({
            "center": [int(z), int(y), int(x)],
            "radius_pixels": int(radius),
            "estimated_size_mm": float(radius * 2 * 0.5),  # Assuming 0.5mm per pixel
            "intensity": int(np.random.randint(30, 100))
        })
    
    # Save as numpy file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    np.save(output_path, scan)
    
    # Save metadata
    metadata_path = output_path.replace('.npy', '_metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump({
            "shape": list(scan.shape),
            "spacing_mm": [2.0, 0.5, 0.5],  # z, y, x spacing in mm
            "nodules": nodule_positions,
            "scan_type": "synthetic_lung_ct"
        }, f, indent=2)
    
    print(f"✓ Generated synthetic CT scan: {output_path}")
    print(f"  Size: {width}x{height}x{depth} pixels")
    print(f"  Nodules: {num_nodules}")
    print(f"  Metadata: {metadata_path}")
    
    return output_path


def generate_test_image_files():
    """Generate simple 2D test images for quick testing"""
    from PIL import Image, ImageDraw
    
    output_dir = Path('d:/project/project/data/samples')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a simple lung-like image with dark regions (lungs) and bright spots (nodules)
    for i in range(3):
        img = Image.new('L', (512, 512), color=100)  # Gray background
        draw = ImageDraw.Draw(img)
        
        # Draw lung regions (dark ellipses)
        draw.ellipse([50, 100, 200, 400], fill=30)
        draw.ellipse([300, 100, 450, 400], fill=30)
        
        # Draw nodules (bright spots)
        for j in range(2):
            x = np.random.randint(80, 180) if j == 0 else np.random.randint(330, 430)
            y = np.random.randint(150, 350)
            radius = np.random.randint(8, 15)
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=180)
        
        filename = f'test_lung_{i+1}.png'
        filepath = output_dir / filename
        img.save(filepath)
        print(f"✓ Created test image: {filepath}")


if __name__ == '__main__':
    # Generate synthetic CT scans
    print("\n=== Generating Test Data ===\n")
    
    # Small scan for quick testing
    generate_synthetic_ct_scan(
        'd:/project/project/data/samples/synthetic_small.npy',
        width=128, height=128, depth=32, num_nodules=2
    )
    
    # Medium scan
    generate_synthetic_ct_scan(
        'd:/project/project/data/samples/synthetic_medium.npy',
        width=256, height=256, depth=64, num_nodules=4
    )
    
    # Generate simple 2D test images
    print("\n=== Generating Test Images ===\n")
    try:
        generate_test_image_files()
    except ImportError:
        print("PIL not installed - skipping image generation")
    
    print("\n✓ All test data generated successfully!")
    print("\nYou can now upload these files to the application:")
    print("  - d:/project/project/data/samples/sample_scan.mhd (existing MHD file)")
    print("  - d:/project/project/data/samples/synthetic_small.npy")
    print("  - d:/project/project/data/samples/synthetic_medium.npy")
    print("  - d:/project/project/data/samples/test_lung_*.png")
