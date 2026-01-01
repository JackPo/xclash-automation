# Kingdom Titles Reference

Royal City kingdom titles provide buffs when applied. Access via marked Royal City location.

## Standard Titles

### Row 1

| Title | Click (4K) | Buffs |
|-------|------------|-------|
| **Prime Minister** | (1537, 950) | Building +20%, Tech Research +20%, Soldier Training +10% |
| **Marshall** | (1916, 938) | Barrack Capacity +20%, Soldier Training +20% |
| **Minister of Health** | (2294, 945) | Hospital Capacity +20%, Healing Speed +20% |

### Row 2

| Title | Click (4K) | Buffs |
|-------|------------|-------|
| **Minister of Construction** | (1537, 1515) | Building +50%, Tech Research +25% |
| **Minister of Science** | (1917, 1515) | Tech Research +50%, Building +25% |
| **Minister of Domestic Affairs** | (2292, 1508) | Food/Iron/Gold Output +100% each |

## Best Title for Each Activity

| Activity | Best Title | Buff |
|----------|------------|------|
| Building | Minister of Construction | +50% |
| Research | Minister of Science | +50% |
| Soldier Training | Marshall | +20% speed, +20% capacity |
| Healing | Minister of Health | +20% speed, +20% capacity |
| Resource Gathering | Minister of Domestic Affairs | +100% all resources |

## Event Titles

Additional titles may appear during special events. Add to `data/kingdom_titles.json` as discovered.

## Navigation Flow

```
Pre-condition: At marked Royal City (star icon with ! visible)

1. Click star icon (1919, 1285) → Poll for Royal City header
2. Click Manage (2230, 881) → Poll for Royal City Management header
3. Click Title Assignment (1650, 976) → Poll for Kingdom Title header
4. Click desired title row → Poll for title detail header
5. Click Apply (1914, 1844)
6. Return to base view
```

## Templates

| Template | Purpose |
|----------|---------|
| `mark_star_icon_4k.png` | Entry point detection |
| `mark_royal_city_header_4k.png` | Validate Royal City popup |
| `mark_manage_button_4k.png` | Manage button |
| `mark_royal_city_mgmt_header_4k.png` | Validate management screen |
| `mark_title_assignment_button_4k.png` | Title Assignment button |
| `mark_kingdom_title_header_4k.png` | Validate title list screen |
| `mark_apply_button_4k.png` | Apply button |
| `mark_title_domestic_affairs_4k.png` | Example title detail header |

## WebSocket API Commands

The daemon exposes title management via WebSocket API (default port 9876):

### `list_titles`
Lists all available kingdom titles.

```json
{"command": "list_titles"}
```

Response includes title keys like `minister_of_science`, `minister_of_construction`, etc.

### `apply_title`
Applies a specific title. Requires being at marked Royal City with star icon visible.

```json
{"command": "apply_title", "args": {"title": "minister_of_science"}}
```

**Title keys:**
- `prime_minister` - Building +20%, Tech Research +20%, Soldier Training +10%
- `marshall` - Barrack Capacity +20%, Soldier Training +20%
- `minister_of_health` - Hospital Capacity +20%, Healing Speed +20%
- `minister_of_construction` - Building +50%, Tech Research +25%
- `minister_of_science` - Tech Research +50%, Building +25%
- `minister_of_domestic_affairs` - Food/Iron/Gold Output +100% each

## JSON Data

Full structured data: `data/kingdom_titles.json`
