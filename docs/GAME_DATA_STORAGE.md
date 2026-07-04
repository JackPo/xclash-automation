# X-Clash Game Data Storage Analysis

## Overview

Complete analysis of local data storage for X-Clash (com.xman.na.gp) on Android/BlueStacks.

**Key Finding**: Only DM (private) messages are cached locally. Union/World chat is NOT stored - it's streamed via WebSocket.

---

## Storage Locations

### Primary: `/data/data/com.xman.na.gp/shared_prefs/`

| File | Size | Purpose |
|------|------|---------|
| `com.xman.na.gp.v2.playerprefs.xml` | ~1.2MB | **Main game state** - DM chats, player profiles, formations |
| `q1sdk.cache.xml` | ~31KB | SDK auth tokens, account bindings |
| `aihelp_share_data.xml` | ~6KB | Customer support data |
| `spUtils.xml` | ~7KB | SDK event whitelist, upload timestamps |

### Secondary: `/data/data/com.xman.na.gp/`

| Path | Purpose |
|------|---------|
| `files/mmkv/mmkv.default` | Tencent MMKV key-value store (SDK config, purchase cache) |
| `files/mmkv/google_purchase` | Google Play purchase tracking |
| `databases/q1sdk_android.db` | SDK events database (analytics upload queue) |
| `databases/thinkingdata` | ThinkingData analytics (1.1MB, ~2M events) |

### External: `/sdcard/Android/data/com.xman.na.gp/files/`

| Path | Purpose |
|------|---------|
| `AssetBundles/Android/Log/*.log` | Game debug logs (rotated, ~5MB each) |
| `AvatarCaching/*.jpg` | Cached player avatars |
| `Documents/q1_apm_log/` | Performance monitoring logs |
| `NewCaching/` | Asset bundles, localization files |

---

## PlayerPrefs Structure

### How to Extract

```bash
# Copy to sdcard (requires root)
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c 'cp /data/data/com.xman.na.gp/shared_prefs/com.xman.na.gp.v2.playerprefs.xml /sdcard/playerprefs.xml'"

# Pull to PC
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "cat /sdcard/playerprefs.xml" > playerprefs.xml
```

### Format
- Standard Android SharedPreferences XML
- Values are **URL-encoded JSON strings**
- Keys follow pattern: `{roleId}{category}_{suffix}`

### Key Categories (275 total keys)

| Category | Count | Pattern | Description |
|----------|-------|---------|-------------|
| DM Sessions | 86 | `session_{myId}_{otherId}_` | Private message history |
| Role Info | 96 | `roleInfo_{roleId}_{worldId}` | Cached player profiles |
| Formations | 24 | `{roleId}*Formations*` | Battle/Alliance team setups |
| Cache Data | 4 | `cacheData_auto*` | Activity timestamps, UI state |
| Legend Teams | 20 | `{roleId}legendTeam*` | Legend mode formations |
| Session Props | 2 | `sessionProp_{roleId}`, `sIdList_{roleId}` | DM metadata |
| Other | 43 | Various | Server data, login info, settings |

---

## DM Chat Sessions

### Key Format: `session_{myRoleId}_{otherRoleId}_`

**Statistics (as of 2026-02-06)**:
- **86 conversations** with unique players
- **1,992 total messages** cached
- Most recent: 2026-02-06 05:47 (Role 5117391)
- Oldest: 2025-10-27 (Role 5144046)

### Message Structure

```json
{
  "roleid": 5179912,           // Sender role ID
  "context": "Message text",   // The actual message (text for sType 0)
  "toRoleId": 23494094,        // Recipient role ID
  "chatTime": 1761936510,      // Unix timestamp
  "szChatID": "5179912-68169-1761936510",
  "chatBubbleID": 0,
  "nationalFlagID": 6,         // Sender's flag
  "toWorldid": 10049,
  "worldid": 10049,
  "sType": 0,                  // Message type (see below)
  "extendinfo": "",
  "toNationalFlagID": 0,
  "sandboxmarkData": {},       // For coordinate shares (sType 43)
  "shareInfo": {},             // For item shares (sType 69)
  "langText": [],              // Translation data
  "hero": [],                  // Hero data for shares
  "exchangeInfo": []           // Exchange data
}
```

### Message Types (sType)

| sType | Count | Description | Context Field |
|-------|-------|-------------|---------------|
| 0 | 1,888 | Text message | Plain text |
| 15 | 2 | Unknown | Empty |
| 43 | 20 | Coordinate share | Empty (data in `sandboxmarkData`) |
| 69 | 82 | Item/Gift share | Item ID number (e.g., "1007723") |

### Coordinate Share Format (sType 43)

```json
{
  "sType": 43,
  "context": "",
  "sandboxmarkData": {
    "x": 500,
    "y": 500,
    "sandboxSid": 10049,
    "playerName": "DVCxPanda",
    "entityName": "Zombie Lair Lv.10",
    "type": 2
  }
}
```

### Item Share Format (sType 69)

```json
{
  "sType": 69,
  "context": "1007723",        // Item ID
  "shareInfo": {
    "nStallId": 0,
    "nHostAreaId": 0,
    "nHostId": 0,
    "nShareType": 0,
    "nDaySellPrice": 0,
    "nShareState": 0
  }
}
```

### Special Text Formats in Messages

| Format | Example | Meaning |
|--------|---------|---------|
| `[3{hex}&...]` | `[3EAB&base64...]` | Emoji/sticker image |
| `[4&ej_X]` | `[4&ej_5]` | Preset sticker |
| `<link>...</link>` | Tested | Does NOT create links (stored as plain text) |

**Note**: Coordinate links and emojis are UI-generated, not typed.

### Session Metadata

#### `sessionProp_{roleId}`

Unread counts and pinned status for each conversation:

```json
{
  "5371932": {"newNum": 0, "isTop": false},
  "5027210": {"newNum": 0, "isTop": false}
}
```

#### `sIdList_{roleId}`

List of all role IDs you've messaged:

```json
{
  "5371932": true,
  "5027210": true,
  "5064738": true
}
```

---

## Player Profiles

### Key Format: `roleInfo_{roleId}_{worldId}`

Cached profiles of players you've interacted with (96 profiles cached).

```json
{
  "roleid": 5371932,
  "name": "saintlouismd",
  "worldid": 10051,
  "roleLv": 26,
  "toRoleLv": 27,
  "nVipLv": 10,
  "ce": 37790563,
  "guildname": "OCEAN",
  "title": "",
  "titleID": 0,
  "avatarFrame": 9102,
  "nameIcon": 0,
  "passStage": 277,
  "topHero": [],
  "faceId": 9210,
  "faceStr": "https://...avatar.jpg",
  "toName": "SexyAIPanda",
  "toFaceId": "9210",
  "toAvatarFrame": 9101,
  "bHideVip": true
}
```

**Fields**:
- `name` - Player's display name
- `roleLv` / `toRoleLv` - Their level / your level when cached
- `nVipLv` - VIP level
- `ce` - Combat effectiveness (power)
- `guildname` - Alliance/union name
- `passStage` - Campaign progress
- `faceStr` - Avatar image URL
- `toName` - Your name (when this profile was cached)

---

## Battle Formations

### Key Patterns

| Pattern | Description |
|---------|-------------|
| `{roleId}BattleTwoFormations*` | Main battle formations |
| `{roleId}AllianceTrain*Formations*` | Alliance training teams |
| `{roleId}CarriageFormations*` | Carriage defense teams |
| `{roleId}legendTeam*` | Legend mode teams |

### Format

```
12,16,25,7,3,0,0#21,20,24,23,22,0,0#10,18,6,19,2,0,0##
```

Format: `row1#row2#row3##` where each row is comma-separated hero IDs (0 = empty slot)

---

## Q1 SDK Cache Structure

### Authentication Tokens (q1sdk.cache.xml)

| Key | Purpose |
|-----|---------|
| `q1_access_token` | JWT access token (30-day expiry) |
| `q1_refresh_token` | JWT refresh token |
| `q1_firebase_token` | Firebase Cloud Messaging token |
| `q1_user_id` | SDK user ID |

### JWT Access Token Claims (decoded)

```json
{
  "UserId": "500285023",
  "UUID": "56e5e2ad-dbd0-314e-82f2-177c1f1b4d2b",
  "GameId": "2162",
  "BindNickName": "Ming Jack Po",
  "BindFace": "https://lh3.googleusercontent.com/...",
  "UserType": "2",
  "UserTypeList": "1,2",
  "BindUserList": "[{\"usertype\":1,\"nickname\":\"Ming Jack Po\"}...]",
  "Pid": "21621003",
  "exp": 1772991212,
  "iss": "overseas.q1.com"
}
```

### Game Identifiers

| Key | Value | Purpose |
|-----|-------|---------|
| `image_game_id` | 2162 | Game ID |
| `image_world_id` | 10049 | Current server/kingdom |
| `image_actor_id` | 5179912 | Your role ID |
| `image_actor_name` | DVCxPanda | Your display name |
| `image_channel_id` | 21621003 | Channel ID |

### Account Bindings

```json
[
  {"usertype": 1, "nickname": "Ming Jack Po", "bindtime": 1759155446},
  {"usertype": 2, "nickname": "Ming Jack Po", "bindtime": 1760460376}
]
```
- usertype 1 = Google
- usertype 2 = Facebook

---

## Database Analysis

### q1sdk_android.db

Schema:
```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL,
  data TEXT NOT NULL,       -- Binary/compressed
  create_at LONG NOT NULL
);
```

Contains SDK analytics upload queue. Data is binary, not chat.

### thinkingdata

Schema:
```sql
CREATE TABLE events (
  _id INTEGER PRIMARY KEY AUTOINCREMENT,
  clickdata TEXT NOT NULL,  -- JSON event data
  creattime INTEGER NOT NULL,
  token TEXT NOT NULL DEFAULT ''
);
CREATE INDEX time_idx ON events (creattime);
```

Contains ~2M analytics events (game telemetry). Example event:
```json
{
  "#type": "track",
  "#event_name": "AllianceDuel_Enter_Ranking",
  "#account_id": "2162_5_5179912",
  "properties": {
    "role_id": 5179912,
    "server_id": 10049,
    "role_level": 28
  }
}
```

**No chat content in databases - only game telemetry.**

---

## MMKV Store Analysis

Location: `/data/data/com.xman.na.gp/files/mmkv/mmkv.default`

Contains:
- `SP_KEY_APP_INSTALL` - Installation timestamp
- `DeveloperConfigRepository_*` - Developer configs (logging, crash reporting)
- `google_cancel_*` - Cancelled purchase tracking
- SDK initialization data

**No chat content in MMKV - only SDK configuration.**

---

## Chat Storage Summary

### What IS Cached Locally

| Type | Storage | Count | Details |
|------|---------|-------|---------|
| **DM/Private messages** | playerprefs `session_*` | 1,992 msgs | Full history, sender info, timestamps |
| **Player profiles** | playerprefs `roleInfo_*` | 96 profiles | Basic info of people you've messaged |
| **DM metadata** | playerprefs `sessionProp_*` | 86 sessions | Unread counts, pinned status |
| **Your own data** | q1sdk.cache | - | Account, tokens, actor info |

### What is NOT Cached Locally

| Type | Reason |
|------|--------|
| **World/Server chat** | Streamed via WebSocket, not persisted |
| **Union chat** | Streamed via WebSocket, not persisted |
| **Union announcements** | Fetched from server on-demand |
| **System messages** | Transient, not stored |

### Exhaustive Verification (2026-02-06)

**Searched locations**:
1. All 275 playerprefs keys - **Only DM sessions found**
2. MMKV binary store (~32KB) - **Only SDK config**
3. q1sdk_android.db - **Only analytics upload queue**
4. thinkingdata db (~1.1MB) - **Only game telemetry**
5. All cache directories - **No chat files**
6. External storage (`/sdcard/...`) - **Only assets and logs**
7. Game log files - **Only Unity/Lua debug logs**

**Search tests**:
- Grepped for Portuguese words from union chat ("aquecer", "calor", "preciso") - **NOT FOUND**
- Only match was in localization asset files (`lang_exec_po.asset`)
- Analyzed all session_ keys - all are 1:1 DM conversations with player role IDs

**Conclusion**: Union/World chat is definitively NOT stored locally. The game uses WebSocket (`wss://wss-2162ea.q1.com`) for real-time group chat streaming.

---

## 2026-02-07 Verification (Local Cache Only)

### What Was Re-Checked

- `/data/data/com.xman.na.gp/**` (full app data directory)
- `/sdcard/Android/data/com.xman.na.gp/**` (external storage)

### Results

- **No union/world/server chat cached locally.**
- Only **DM sessions** are present in `com.xman.na.gp.v2.playerprefs.xml` (`session_*` keys).
- External storage matches are **asset manifests, logs, and UI bundles**, not chat content.
- The only "chat" text match outside playerprefs was **AIHelp support config** (`aihelp_share_data.xml`).

### PlayerPrefs File Activity

`/data/data/com.xman.na.gp/shared_prefs/com.xman.na.gp.v2.playerprefs.xml`

- Size observed: **~1.2 MB**
- Modify time observed: **2026-02-06 20:43:40** (device time)
- Indicates the file **does update during gameplay**, but it is **not a full game state dump**.

---

## What PlayerPrefs Actually Contains (And What It Doesn't)

### Confirmed Useful Data (Good for a Dashboard)

- **DM chat history** (`session_*`)
- **DM metadata** (`sessionProp_*`, `sIdList_*`)
- **Player profiles** (`roleInfo_*`) with:
  - name, level, VIP, power (ce), guild/union name, avatar, etc.
- **Formations / team setups** (battle, alliance training, legend, carriage)
- **Some progression flags** (story/level defeated keys, cutscene flags)
- **VIP level cache** (`*_VIPLevel*`)
- **Misc UI state / timestamps** (various `cacheData_*`, `*_SaveTime`, etc.)

### NOT Found in PlayerPrefs

- **Current stamina/energy**
- **Current gold/food/iron/wood/oil**
- **Full inventory**
- **Union/world/server chat**
- **Realtime combat or march state**

These appear to be **server-side only** or stored in a different runtime cache not persisted to SharedPreferences.

---

## Capturing Non-Local Chat

To capture union/world chat, you must intercept network traffic:

1. **MITM proxy** - Intercept `translate.q1.com` (translated messages only)
2. **WebSocket hook** - Intercept `wss://wss-2162ea.q1.com` directly with Frida
3. **Protobuf parsing** - Decode the game's real-time protocol

See `docs/CHAT_INTERCEPT.md` for MITM setup.

---

## Useful Scripts

### List All DM Conversations

```python
import re, json
from urllib.parse import unquote
from datetime import datetime

with open('playerprefs.xml', 'r', encoding='utf-8') as f:
    content = f.read()

sessions = re.findall(r'<string name="session_(\d+)_(\d+)_">([^<]*)</string>', content)
for my_id, other_id, value in sorted(sessions, key=lambda x: x[1]):
    data = json.loads(unquote(value))
    if data:
        last_ts = data[-1].get('chatTime', 0)
        last_date = datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d')
        print(f"Role {other_id}: {len(data)} msgs, last: {last_date}")
```

### Get Recent Messages

```python
import re, json
from urllib.parse import unquote
from datetime import datetime

with open('playerprefs.xml', 'r', encoding='utf-8') as f:
    content = f.read()

sessions = re.findall(r'<string name="session_(\d+)_(\d+)_">([^<]*)</string>', content)
all_msgs = []

for my_id, other_id, value in sessions:
    data = json.loads(unquote(value))
    for msg in data:
        ts = msg.get('chatTime', 0)
        ctx = msg.get('context', '')
        sender = msg.get('roleid', 0)
        all_msgs.append((ts, other_id, sender, ctx))

# Sort by timestamp (most recent first)
all_msgs.sort(key=lambda x: -x[0])

print("15 Most Recent Messages:")
for ts, other_id, sender, ctx in all_msgs[:15]:
    dt = datetime.fromtimestamp(ts)
    who = 'ME' if str(sender) == '5179912' else 'THEM'
    print(f'{dt} - {who} (with {other_id}): {ctx[:60]}')
```

### Search Messages for Text

```python
import re, json
from urllib.parse import unquote

with open('playerprefs.xml', 'r', encoding='utf-8') as f:
    content = f.read()

search_term = "desperate"  # Change this
sessions = re.findall(r'<string name="session_\d+_(\d+)_">([^<]*)</string>', content)

for other_id, value in sessions:
    decoded = unquote(value)
    if search_term.lower() in decoded.lower():
        data = json.loads(decoded)
        for msg in data:
            if search_term.lower() in msg.get('context', '').lower():
                print(f"Role {other_id}: {msg['context']}")
```

### Get Player Name from Role ID

```python
import re, json
from urllib.parse import unquote

with open('playerprefs.xml', 'r', encoding='utf-8') as f:
    content = f.read()

role_id = "5371932"  # Change this
match = re.search(rf'<string name="roleInfo_{role_id}[^"]*">([^<]*)</string>', content)
if match:
    data = json.loads(unquote(match.group(1)))
    print(f"Name: {data.get('name')}")
    print(f"Guild: {data.get('guildname')}")
    print(f"Level: {data.get('roleLv')}")
    print(f"VIP: {data.get('nVipLv')}")
    print(f"Power: {data.get('ce'):,}")
```

### Export All Conversations to JSON

```python
import re, json
from urllib.parse import unquote
from datetime import datetime

with open('playerprefs.xml', 'r', encoding='utf-8') as f:
    content = f.read()

# Get roleInfo for name lookup
role_names = {}
role_infos = re.findall(r'<string name="roleInfo_(\d+)[^"]*">([^<]*)</string>', content)
for role_id, value in role_infos:
    try:
        data = json.loads(unquote(value))
        role_names[role_id] = data.get('name', f'Role_{role_id}')
    except:
        pass

# Export conversations
export = {}
sessions = re.findall(r'<string name="session_(\d+)_(\d+)_">([^<]*)</string>', content)
for my_id, other_id, value in sessions:
    data = json.loads(unquote(value))
    other_name = role_names.get(other_id, f'Role_{other_id}')
    export[other_name] = [{
        'sender': 'me' if str(msg['roleid']) == my_id else other_name,
        'text': msg['context'],
        'sType': msg.get('sType', 0),
        'time': datetime.fromtimestamp(msg['chatTime']).isoformat()
    } for msg in data]

with open('conversations.json', 'w', encoding='utf-8') as f:
    json.dump(export, f, indent=2, ensure_ascii=False)
print(f"Exported {len(export)} conversations")
```

---

## Sample Data

### Current Account (as of 2026-02-06)

| Field | Value |
|-------|-------|
| User ID | 500285023 |
| Actor ID | 5179912 |
| Actor Name | DVCxPanda |
| World ID | 10049 |
| Game ID | 2162 |
| Channel ID | 21621003 |

### DM Statistics

- **Total conversations**: 86
- **Total messages**: 1,992
- **Total cached profiles**: 96
- **Most recent chat**: 2026-02-06 05:47 (Role 5117391)
- **Oldest chat**: 2025-10-27 (Role 5144046)

### Message Type Distribution

| sType | Count | Percentage |
|-------|-------|------------|
| 0 (Text) | 1,888 | 94.8% |
| 69 (Item Share) | 82 | 4.1% |
| 43 (Coordinate) | 20 | 1.0% |
| 15 (Unknown) | 2 | 0.1% |

---

## File Locations Quick Reference

```
/data/data/com.xman.na.gp/
├── shared_prefs/
│   ├── com.xman.na.gp.v2.playerprefs.xml  # Main game data (1.2MB)
│   ├── q1sdk.cache.xml                     # Auth tokens (31KB)
│   ├── spUtils.xml                         # SDK config (7KB)
│   └── aihelp_share_data.xml              # Support data (6KB)
├── files/
│   └── mmkv/
│       ├── mmkv.default                    # SDK config (32KB)
│       └── google_purchase                 # Purchase cache
├── databases/
│   ├── q1sdk_android.db                    # SDK events (77KB)
│   └── thinkingdata                        # Analytics (1.1MB)
└── cache/
    └── WebView/                            # WebView cache

/sdcard/Android/data/com.xman.na.gp/files/
├── AssetBundles/Android/Log/*.log          # Game logs (~5MB each)
├── AvatarCaching/*.jpg                     # Player avatars
├── NewCaching/                             # Asset bundles
│   ├── lang_exec/                          # Localization
│   └── casualchannel/                      # UI assets by language
└── Documents/q1_apm_log/                   # APM logs
```

---

## Related Documentation

- `docs/CHAT_INTERCEPT.md` - MITM proxy setup for network chat capture
- `.claude/skills/mitm-proxy/SKILL.md` - Complete MITM skill reference

---

## Last Updated

2026-02-06 - Exhaustive analysis confirming:
- 86 DM sessions with 1,992 messages stored locally
- 96 player profiles cached
- Union/World chat NOT stored (verified via comprehensive search)
- All storage locations documented with schemas
