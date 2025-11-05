
import cv2

# Load the original image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Scaled-up bounding box
    # Format: (x_min, y_min, x_max, y_max)
    bounding_box = (230, 180, 430, 380)

    # Crop the image
    template = image[bounding_box[1]:bounding_box[3], bounding_box[0]:bounding_box[2]]

    # Save the template
    template_path = f'templates/complex_castle_1.png'
    cv2.imwrite(template_path, template)
    print(f"Saved template to {template_path}")
