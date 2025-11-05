import cv2
import numpy as np

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)
if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Canny edge detection
    edges = cv2.Canny(blurred, 50, 150)

    # Find contours
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours
    castle_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if 500 < area < 5000:  # Adjust area thresholds as needed
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h
            if 0.8 < aspect_ratio < 1.5:  # Adjust aspect ratio as needed
                castle_contours.append(contour)

    # Sort by contour area and take the top 3
    castle_contours = sorted(castle_contours, key=cv2.contourArea, reverse=True)[:3]

    # Create a copy of the original image to draw on
    output_image = image.copy()

    # Extract and save templates
    for i, contour in enumerate(castle_contours):
        x, y, w, h = cv2.boundingRect(contour)
        # Add some padding
        padding = 20
        x1, y1 = max(0, x - padding), max(0, y - padding)
        x2, y2 = min(image.shape[1], x + w + padding), min(image.shape[0], y + h + padding)
        
        # Draw rectangle on the output image
        cv2.rectangle(output_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Crop and save the template
        template = image[y1:y2, x1:x2]
        template_path = f'templates/complex_castle_{i+1}.png'
        cv2.imwrite(template_path, template)
        print(f"Saved template to {template_path}")

    # Save the debug image
    output_image_path = 'castle_locations_marked.png'
    cv2.imwrite(output_image_path, output_image)
    print(f"Saved debug image to {output_image_path}")