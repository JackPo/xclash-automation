"""
Label training data using image analysis agent.
Processes batches of 20 images at a time.
"""

import os
import shutil
from pathlib import Path

def create_label_batches(raw_dir, batch_size=20):
    """Create batches of images for labeling."""
    images = sorted(list(Path(raw_dir).glob('*.png')))
    batches = []
    for i in range(0, len(images), batch_size):
        batch = images[i:i+batch_size]
        batches.append(batch)
    return batches

def main():
    print("Training Data Labeling Script")
    print("=" * 50)

    # Count samples
    levels_raw_dir = Path('training_data/levels_raw')
    names_raw_dir = Path('training_data/names_raw')

    level_images = list(levels_raw_dir.glob('*.png'))
    name_images = list(names_raw_dir.glob('*.png'))

    print(f"\nFound:")
    print(f"  Level ROIs: {len(level_images)}")
    print(f"  Name ROIs: {len(name_images)}")

    # Create batches
    level_batches = create_label_batches(levels_raw_dir, batch_size=20)
    name_batches = create_label_batches(names_raw_dir, batch_size=20)

    print(f"\nLevel batches: {len(level_batches)}")
    print(f"Name batches: {len(name_batches)}")

    print("\n" + "=" * 50)
    print("Next steps:")
    print("1. Use Task tool with general-purpose agent to label each batch")
    print("2. Agent should read the number/name from each image")
    print("3. Return list of: (filename, label) pairs")
    print("4. Script will rename files to: level_{label}_{uuid}.png")
    print("\nRun this script interactively to process batches.")

if __name__ == "__main__":
    main()
