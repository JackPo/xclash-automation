
import cv2
import numpy as np

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Get image dimensions
    h, w, _ = image.shape

    # Define grid size
    grid_size = 10
    grid_h = h // grid_size
    grid_w = w // grid_size

    # Draw grid lines
    for i in range(1, grid_size):
        # Horizontal lines
        cv2.line(image, (0, i * grid_h), (w, i * grid_h), (0, 255, 0), 2)
        # Vertical lines
        cv2.line(image, (i * grid_w, 0), (i * grid_w, h), (0, 255, 0), 2)

    # Add labels to grid cells
    for i in range(grid_size):
        for j in range(grid_size):
            cell_label = f'{i},{j}'
            cv2.putText(image, cell_label, (j * grid_w + 10, i * grid_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Save the gridded image
    output_path = 'templates/gridded_screenshot.png'
    cv2.imwrite(output_path, image)
    print(f"Saved gridded screenshot to {output_path}")
