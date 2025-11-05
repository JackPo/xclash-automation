import cv2
roi = cv2.imread('templates/debug/testing/post_click_roi.png')
print('roi shape', roi.shape if roi is not None else None)
if roi is not None:
    cv2.imwrite('templates/debug/testing/post_click_roi_down.png', cv2.resize(roi, (400,400)))
