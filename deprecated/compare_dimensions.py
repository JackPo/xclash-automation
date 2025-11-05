
import cv2
from PIL import Image

# Image path
image_path = 'templates/debug/after_8_zooms.png'

# Get dimensions with cv2
try:
    cv2_image = cv2.imread(image_path)
    if cv2_image is not None:
        cv2_height, cv2_width, _ = cv2_image.shape
        print(f"cv2 dimensions: {cv2_width}x{cv2_height}")
    else:
        print("cv2 could not read the image")
except Exception as e:
    print(f"Error with cv2: {e}")

# Get dimensions with Pillow
try:
    pil_image = Image.open(image_path)
    pil_width, pil_height = pil_image.size
    print(f"Pillow dimensions: {pil_width}x{pil_height}")
except Exception as e:
    print(f"Error with Pillow: {e}")
