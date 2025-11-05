import cv2
from castle_matcher import CastleMatcher

matcher = CastleMatcher()
frame = cv2.imread('templates/debug/testing/latest_attempt.png')
result = matcher.estimate_scale(frame)
print(result)
if result:
    print('approx dims', matcher.approximate_castle_dimensions(result.scale))
