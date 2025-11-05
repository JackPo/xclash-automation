from pathlib import Path
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def read_text(path):
    img = Image.open(path)
    return pytesseract.image_to_string(img)

print('world template text:', repr(read_text(Path('templates/buttons/world_button_template.png'))))
print('town template text:', repr(read_text(Path('templates/buttons/town_button_template.png'))))
print('debug button text:', repr(read_text(Path('templates/debug/testing/roi/debug_btn_1_20251103_162924_roi.png'))))
print('button_test_1 text:', repr(read_text(Path('templates/debug/testing/roi/button_test_1_20251103_123807_roi.png'))))
