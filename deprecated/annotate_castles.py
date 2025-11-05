
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Downsample the image
    small_image = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)
    cv2.imwrite('templates/debug/after_8_zooms_small.png', small_image)

    # Bounding boxes for the three castles on the downsampled image
    # Format: (x_min, y_min, x_max, y_max)
    bounding_boxes = [
        (50, 100, 150, 200),
        (250, 300, 350, 400),
        (450, 500, 550, 600)
    ]

    # Draw bounding boxes on the downsampled image
    for (x1, y1, x2, y2) in bounding_boxes:
        cv2.rectangle(small_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

    # Save the annotated image
    annotated_image_path = 'templates/annotated_castles.png'
    cv2.imwrite(annotated_image_path, small_image)
    print(f"Saved annotated image to {annotated_image_path}")
