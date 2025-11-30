# Union Donation Flow

## Trigger Conditions
- User idle for 20+ minutes
- No other flows currently running (lowest priority)
- At most once per hour (cooldown: 60 minutes)
- Must be in TOWN view with dog house aligned

## Flow Steps

### Step 1: Click Union Button
- **Template**: `templates/ground_truth/union_button_4k.png`
- **Position**: (3087, 1939)
- **Size**: 157x188
- **Click**: (3165, 2033)
- **Wait**: 1.5s for union screen to load

### Step 2: Click Technology Tab
- TODO: Capture template and coordinates
- Wait for technology screen

### Step 3: Find Donation Button
- TODO: Look for "Donate" button on technology items
- May need to scroll to find available donations

### Step 4: Click Donate
- TODO: Capture donate button template
- Click to donate resources

### Step 5: Confirm/Exit
- TODO: Handle confirmation dialog if any
- Click back to exit union screen

## Templates Needed
- [x] `union_button_4k.png` - Union button on bottom bar (3087, 1939) 157x188
- [ ] `technology_tab_4k.png` - Technology tab in union menu
- [ ] `donate_button_4k.png` - Donate button on tech items
- [ ] `union_back_button_4k.png` - Back button to exit union

## Notes
- This is the LOWEST priority flow
- Only runs when completely idle
- 1 hour cooldown between runs
- Should check that union screen actually opened before proceeding
