
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Bounding box for the red button
    # Format: (x_min, y_min, x_max, y_max)
    bounding_box = (2450, 100, 2550, 200)

    # Draw a rectangle on the image
    cv2.rectangle(image, (bounding_box[0], bounding_box[1]), (bounding_box[2], bounding_box[3]), (0, 255, 0), 2)

    # Save the annotated image
    annotated_image_path = f'templates/red_button_annotated.png'
    cv2.imwrite(annotated_image_path, image)
    print(f"Saved annotated image to {annotated_image_path}")
