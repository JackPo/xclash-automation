import cv2
for name in ["corner_town.png", "corner_check.png", "corner_debug.png"]:
    img = cv2.imread(name)
    if img is None:
        print(name, "missing")
    else:
        print(name, img.shape)
