
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
    grid_size = 10
    grid_h = h // grid_size
    grid_w = w // grid_size

    # User-provided grid coordinates
    grid_coords = [(2, 1), (1, 2), (2, 7)]

    # Extract and save templates
    for i, (row, col) in enumerate(grid_coords):
        # Calculate bounding box
        x1 = col * grid_w
        y1 = row * grid_h
        x2 = x1 + grid_w
        y2 = y1 + grid_h

        # Crop the image
        template = image[y1:y2, x1:x2]

        # Save the template
        template_path = f'templates/complex_castle_{i+1}.png'
        cv2.imwrite(template_path, template)
        print(f"Saved template to {template_path}")
