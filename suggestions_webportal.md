# Suggestions For Web Portal

## What You Can Pull From PlayerPrefs (Reliable)
- Profile: `name`, `roleid`, `roleLv`, `nVipLv`, `guildname`, `worldid`
- Cosmetics: `avatarFrame`, `toAvatarFrame`, `faceId`, `toFaceId`, `faceStr`, `toFaceStr`, `nameIcon`, `title`, `titleID`
- Progress-ish: `passStage`, `topHero`, `ce`
- UI/flags: `CheckCanShowRedDot#*`, `CutsceneShown*`, `timeKeyPopup_*`, `*_SaveTime` and similar keys for “seen” or “cooldown” states

## What Is Not In PlayerPrefs Or Local Cache
- Resources: stamina, gold, food, etc
- Live server/union/world chat history
- Map positions or other player locations

## Replace Screen Grabs With Local Assets
- Use `asset_bundles_extracted` for real in-game art, UI icons, and textures
- Use `art_assets/user_avatars` for avatar images
- The raw bundle files under `art_assets_game` are UnityFS containers and are not viewable directly

## Recommended Frontend Sections
- Account header: name, level, VIP, guild, world
- Identity panel: avatar frame, portrait, name icon, title
- Progress panel: `passStage`, `topHero`, `ce`
- “Status” panel: list of key flags and last seen timestamps from PlayerPrefs

## Suggested Data Mapping
- Keep a simple JSON snapshot of the PlayerPrefs fields above
- Map cosmetic IDs to extracted assets in `asset_bundles_extracted` so the UI renders without OCR

## Known Gaps (Will Still Need Screens Or Server Data)
- Live resources and currency totals
- Live chat content
- Real-time map info
