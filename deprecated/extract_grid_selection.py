
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

    # User-provided grid coordinates
    row_start, col_start = 4, 14
    row_end, col_end = 6, 16

    # Calculate bounding box in pixels
    x1 = col_start * grid_w
    y1 = row_start * grid_h
    x2 = (col_end + 1) * grid_w
    y2 = (row_end + 1) * grid_h

    # Crop the image
    template = image[y1:y2, x1:x2]

    # Save the template
    template_path = f'templates/complex_castle_1.png'
    cv2.imwrite(template_path, template)
    print(f"Saved template to {template_path}")
