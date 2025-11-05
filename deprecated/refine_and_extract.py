
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

    # User-provided grid coordinates
    grid_coords = [(2, 1), (1, 2), (2, 7)]

    # Process each grid coordinate
    for i, (row, col) in enumerate(grid_coords):
        # Calculate bounding box of the grid cell
        x1 = col * grid_w
        y1 = row * grid_h
        x2 = x1 + grid_w
        y2 = y1 + grid_h

        # Extract the ROI
        roi = image[y1:y2, x1:x2]

        # Convert ROI to grayscale and apply threshold
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray_roi, 127, 255, cv2.THRESH_BINARY)

        # Find contours in the ROI
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Find the largest contour
            largest_contour = max(contours, key=cv2.contourArea)

            # Get the bounding box of the largest contour
            x, y, w_contour, h_contour = cv2.boundingRect(largest_contour)

            # Adjust the bounding box to be relative to the original image
            x_abs = x1 + x
            y_abs = y1 + y

            # Add padding
            padding = 20
            x1_padded = max(0, x_abs - padding)
            y1_padded = max(0, y_abs - padding)
            x2_padded = min(w, x_abs + w_contour + padding)
            y2_padded = min(h, y_abs + h_contour + padding)

            # Extract the template with padding
            template = image[y1_padded:y2_padded, x1_padded:x2_padded]

            # Save the template
            template_path = f'templates/complex_castle_{i+1}.png'
            cv2.imwrite(template_path, template)
            print(f"Saved template to {template_path}")
        else:
            print(f"No contours found in grid cell ({row}, {col})")
