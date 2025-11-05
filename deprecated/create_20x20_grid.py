
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Get image dimensions
    h, w, _ = image.shape

    # Define grid size
    grid_size = 20
    grid_h = h // grid_size
    grid_w = w // grid_size

    # Create a copy of the image to draw on
    grid_image = image.copy()

    # Draw grid lines
    for i in range(1, grid_size):
        # Horizontal lines
        cv2.line(grid_image, (0, i * grid_h), (w, i * grid_h), (0, 255, 0), 1)
        # Vertical lines
        cv2.line(grid_image, (i * grid_w, 0), (i * grid_w, h), (0, 255, 0), 1)

    # Add labels to grid cells
    for i in range(grid_size):
        for j in range(grid_size):
            cell_label = f'{i},{j}'
            cv2.putText(grid_image, cell_label, (j * grid_w + 5, i * grid_h + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    # Save the gridded image
    output_path = 'templates/gridded_screenshot_20x20.png'
    cv2.imwrite(output_path, grid_image)
    print(f"Saved gridded screenshot to {output_path}")
