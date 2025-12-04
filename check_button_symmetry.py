"""Check which side to trim to make it 130x130."""
import cv2

# Load the 130x131 template
template = cv2.imread('templates/ground_truth/testing/rally_plus_button_130x131.png')

h, w = template.shape[:2]
print(f"Current size: {w}x{h}")

# The green plus should be centered
# Let's extract different versions and see which one is more centered

# Option 1: Remove 1px from LEFT (start at x=1)
option1 = template[:, 1:131]

# Option 2: Remove 1px from RIGHT (end at x=129)
option2 = template[:, 0:130]

# Save both
cv2.imwrite('templates/ground_truth/testing/rally_plus_130x130_trim_left.png', option1)
cv2.imwrite('templates/ground_truth/testing/rally_plus_130x130_trim_right.png', option2)

print("\nCreated two options:")
print("  1. Trim LEFT: templates/ground_truth/testing/rally_plus_130x130_trim_left.png")
print("  2. Trim RIGHT: templates/ground_truth/testing/rally_plus_130x130_trim_right.png")
