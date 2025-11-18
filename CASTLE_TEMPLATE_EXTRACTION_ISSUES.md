# Castle Template Extraction - Issues and Blockers

## Goal
Extract 3 good complex castle templates from a Clash of Clans world map screenshot to use for zoom level detection.

## Requirements for Each Template
1. **ONE complete player castle** - full structure with all buildings/towers visible
2. **Player name** - text above the castle must be visible
3. **Level number** - number below the castle must be visible
4. **Centered** - castle should be centered in the bounding box with equal padding
5. **Not overlapping** - should not include parts of multiple castles

## The Plan
1. Use a screenshot of the game at a zoomed-out view: `templates/debug/after_8_zooms.png` (2560x1440)
2. Since the full-res image is too large for the agent to process (>2000px limit), downsample it by 50% to 1280x720
3. Have an agent identify 3 castles in the downsampled image and provide bounding box coordinates
4. Multiply the coordinates by 2 to get full-resolution coordinates
5. Extract the crops from the full-resolution image
6. Verify each extraction is correct

## What's Happening (The Problem)

### Attempts Made (ALL FAILED):
1. **Direct coordinate guessing** - I manually guessed coordinates, extracted garbage
2. **Grid overlay** - Added 100px grid to image, had agent read coordinates from grid, extracted garbage
3. **Iterative visualization** - Drew bounding boxes on image, had agent verify, adjusted, still extracted wrong things
4. **Downsampled approach** - Downsampled image to 1280x720, had agent give coordinates, multiplied by 2, STILL extracted garbage
5. **Multiple agent attempts** - Used Sonnet, Haiku, different prompts, different approaches - all produce bad coordinates

### What I'm Extracting (Instead of Castles):
- UI elements (resource counters, buttons)
- Half of one castle + half of another castle
- Single defensive towers (not full player bases)
- Empty grass with just a level number
- Blurry/cut-off partial structures

### Verification Problem:
When I have the agent verify the extracted templates:
- **Agent says**: "This is GOOD - has castle + name + level"
- **User says**: "This is garbage - it's half of two castles"
- **I can't see the images myself** so I rely on agent verification
- **Agents are consistently wrong** about what's in the extracted images

## Why This Is Failing

### Core Issue: Coordinate Translation
The agents give me coordinates like:
```
Castle 1: x_min=450, y_min=75, x_max=570, y_max=185
```

When I multiply by 2 for full-res:
```python
x1_min, y1_min, x1_max, y1_max = 450*2, 75*2, 570*2, 185*2
crop = img[y1_min:y1_max, x1_min:x1_max]
```

This produces: `crop = img[150:370, 900:1140]`

**Something is wrong** - either:
1. The agent is identifying the wrong things as "castles"
2. The coordinate system is off (maybe agents see images differently than cv2 indexes them?)
3. The downsampling/upsampling math is wrong
4. The agents can't accurately locate objects in images
5. I'm making some stupid mistake in the extraction code

### Verification Issue:
Even when I ask agents to verify the extracted images, they say things are "GOOD" when the user clearly sees they're garbage. This means:
1. Agents can't reliably identify what's in an image crop
2. Agents may be biased to say things are good
3. I have no reliable way to verify results without user feedback

## What I've Tried to Debug

### Visualization Approach:
1. Drew bounding boxes ON the image with cv2.rectangle()
2. Saved visualization with boxes drawn
3. Had agent verify boxes look correct
4. Agent says "boxes look good"
5. Extract using those exact coordinates
6. Result is garbage

**This means**: Even when agent confirms boxes are drawn correctly on the visualization, the extraction still fails.

### The "Half Two Castles" Problem:
User repeatedly says extractions show "half of one castle and half of another". This suggests:
1. Bounding boxes are positioned between two castles
2. Not enough padding to isolate one castle
3. Agent is identifying cluster of castles as "one castle"
4. Coordinate offset error causing systematic misalignment

## Current State

### Files:
- `templates/debug/after_8_zooms.png` - Original full-res screenshot (2560x1440)
- `templates/debug/after_8_zooms_small.png` - Downsampled 50% (1280x720)
- `templates/complex_castle_1.png` - BAD (garbage)
- `templates/complex_castle_2.png` - BAD (half of two castles)
- `templates/complex_castle_3.png` - BAD (garbage)

### What Works:
- Screenshot capture works
- Downsampling works
- cv2 image loading works
- File saving works

### What Doesn't Work:
- Getting correct bounding box coordinates
- Verifying extracted templates are correct
- Agent spatial reasoning about object locations
- My ability to debug without being able to see the images

## Possible Solutions

### Option 1: Manual Coordinates
User provides exact coordinates for ONE castle from the downsampled image:
```
x_min=?, y_min=?, x_max=?, y_max=?
```
I extract it, user verifies, if good we repeat for 2 more.

### Option 2: Different Approach
Instead of trying to extract "complex" castles from a zoomed view:
- Use a different screenshot where castles are larger/more isolated
- Or abandon the "complex vs simple" template approach entirely
- Or use a completely different method for zoom detection

### Option 3: Interactive Refinement
For each castle:
1. I make a guess
2. User says "too far left/right/up/down"
3. I adjust by N pixels
4. Repeat until correct
5. Very slow but might actually work

## Why This Matters
The complex castle templates are needed for the zoom level detector to work:
- Complex template = matches when TOO ZOOMED IN → need to zoom out
- Simple template = matches when in correct zone → check scale

Without good complex templates, the zoom calibration system won't work correctly.

## Time Spent
~2+ hours trying to extract 3 simple image crops with no success.

## Request for Help
Need either:
1. Manual coordinates from user
2. Different approach entirely
3. Permission to move on and revisit later
