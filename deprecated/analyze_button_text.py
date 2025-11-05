from pathlib import Path
from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

for name in [
    "templates/debug/testing/roi/button_test_1_20251103_123807_roi.png",
    "templates/debug/testing/roi/latest_attempt_roi.png",
    "templates/buttons/world_button_template.png",
    "templates/buttons/town_button_template.png",
]:
    path = Path(name)
    if not path.exists():
        print(name, "missing")
        continue
    print("\n", name)
    img = Image.open(path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf_raw = data["conf"][i]
        try:
            conf = int(float(conf_raw))
        except Exception:
            conf = -1
        if text and conf > 30:
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            print(f"  {text} conf={conf} bbox=({x},{y},{w},{h})")
