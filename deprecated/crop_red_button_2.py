
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Bounding box for the red button test, adjusted
    # Format: (x_min, y_min, x_max, y_max)
    bounding_box = (2400, 100, 2500, 200)

    # Crop the image
    template = image[bounding_box[1]:bounding_box[3], bounding_box[0]:bounding_box[2]]

    # Save the template
    template_path = f'templates/red_button_test_2.png'
    cv2.imwrite(template_path, template)
    print(f"Saved red button test to {template_path}")
