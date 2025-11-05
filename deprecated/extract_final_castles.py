
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Bounding boxes for the three castles
    # Format: (x_min, y_min, x_max, y_max)
    bounding_boxes = [
        (230, 180, 430, 380),  # Upper left castle
        (1800, 800, 2000, 1000), # Lower right castle
        (1000, 500, 1200, 700)  # Central castle
    ]

    # Extract and save templates
    for i, (x1, y1, x2, y2) in enumerate(bounding_boxes):
        # Crop the image
        template = image[y1:y2, x1:x2]

        # Save the template
        template_path = f'templates/complex_castle_{i+1}.png'
        cv2.imwrite(template_path, template)
        print(f"Saved template to {template_path}")
