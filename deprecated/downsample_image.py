
import cv2

# Load the image
image_path = 'templates/debug/after_8_zooms.png'
image = cv2.imread(image_path)

if image is None:
    print(f"Error: Could not load image at {image_path}")
else:
    # Downsample the image by a factor of 2
    downsampled_image = cv2.resize(image, (0, 0), fx=0.5, fy=0.5)

    # Save the downsampled image
    downsampled_image_path = 'templates/debug/after_8_zooms_downsampled.png'
    cv2.imwrite(downsampled_image_path, downsampled_image)
    print(f"Saved downsampled image to {downsampled_image_path}")
