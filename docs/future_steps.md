# Future Automation Opportunities

This document outlines potential enhancements and missing automation features for the xclash project.

Last updated: 2025-12-02

---

## Current Coverage Status

### ✅ Fully Automated (3/5 Arms Race Events)

**Resource Collection (Passive Income):**
- ✅ Corn, Gold, Iron, Gems, Cabbage, Equipment harvest
- ✅ AFK rewards collection (1hr cooldown)
- ✅ Union gifts collection

**Combat/Events:**
- ✅ Elite Zombie rallies (stamina-based)
- ✅ Treasure map digging
- ✅ Handshake/alliance interactions
- ✅ Harvest surprise boxes

**Arms Race Events:**
- ✅ **Beast Training** (Mystic Beast): Elite zombie rallies in last 60 minutes
- ✅ **Hero Upgrades** (Enhance Hero): Auto-upgrade heroes in last 20 minutes, 2 AM trigger
- ✅ **Soldier Training**: Auto-collect READY soldiers, auto-train PENDING barracks

**Stamina Management:**
- ✅ Free stamina claim (every 4 hours, red dot detection)
- ✅ Stamina recovery items (when low, max 4 uses per block)

**Infrastructure:**
- ✅ Robust view detection (TOWN/WORLD/CHAT/UNKNOWN)
- ✅ Crash recovery with automatic restart
- ✅ Idle detection (prevents interfering with active gameplay)
- ✅ Dog house alignment check (prevents coordinate drift)
- ✅ Hybrid detection methods (template + pixel counting)

---

## 🎯 Missing Features / Opportunities

### HIGH IMPACT (Recommended First)

#### 1. City Construction Event Automation ⭐
**Status**: ❌ Not automated (2/5 Arms Race events automated)

**Description**: Arms Race City Construction event (4 hours) has no automation

**Opportunity**:
- Detect building upgrade completion notifications (yellow hard hat icons)
- Auto-start building upgrades during event window
- Prioritize fastest completions to maximize points
- Would complete Arms Race coverage to 4/5 events

**Complexity**: Medium
- Need building upgrade notification template
- Need to handle builder queue (2 slots)
- May need resource availability checks

**Impact**: HIGH - Arms Race points during 4-hour window

---

#### 2. Daily Quest Reward Collection ⭐
**Status**: ❌ Not automated

**Description**: Daily quests completion rewards not collected automatically

**Opportunity**:
- Detect quest completion notifications/indicators
- Auto-click quest reward collection buttons
- Significant daily resource income

**Complexity**: Low
- Predictable UI patterns
- Template matching for quest icons
- Simple click flows

**Impact**: HIGH - Daily consistent resource gain

---

#### 3. VIP Chest / Daily Login Rewards ⭐
**Status**: ❌ Not automated

**Description**: VIP chests and daily login popups not handled

**Opportunity**:
- Auto-collect VIP chest rewards
- Click through daily login bonuses
- Calendar event rewards
- Common popups that interrupt gameplay

**Complexity**: Low
- Simple template matching
- Single-click flows
- Similar to existing popup handlers

**Impact**: HIGH - Daily rewards, removes interruptions

---

### MEDIUM IMPACT

#### 4. Alliance Help Automation
**Status**: ⚠️ Partial (only handshake automated)

**Description**: Limited alliance interaction automation

**Opportunity**:
- Alliance help requests (clicking help buttons on members' construction/research)
- Alliance territory/war participation detection
- Alliance shop auto-purchases

**Complexity**: Medium
- Need help button detection (may be many on screen)
- Shop requires navigation and purchase logic

**Impact**: MEDIUM - Social contribution, alliance rewards

---

#### 5. Hero Expedition / Adventure
**Status**: ❌ Not automated

**Description**: Hero expeditions provide passive XP but require manual management

**Opportunity**:
- Auto-send heroes on expeditions
- Collect expedition rewards when complete
- Passive hero XP generation

**Complexity**: Medium
- Need expedition UI detection
- Hero selection logic
- Reward collection timing

**Impact**: MEDIUM - Passive hero progression

---

#### 6. Tech Research Event Automation
**Status**: ❌ Not automated (2/5 Arms Race events automated)

**Description**: Arms Race Tech Research event (4 hours) has no automation

**Opportunity**:
- Auto-start tech research during event window
- Similar to building automation
- Would complete Arms Race coverage to 5/5 events

**Complexity**: Medium
- Similar to City Construction automation
- Research queue management
- Resource requirements

**Impact**: MEDIUM - Completes Arms Race coverage

---

### LOW PRIORITY (Complex/Risky)

#### 7. Arena / PvP Automation
**Status**: ❌ Not automated

**Description**: Daily arena attempts for rewards

**Risk**: Complex combat, may need AI or careful scripting

**Opportunity**:
- Auto-complete daily arena attempts
- Team composition selection
- Rewards collection

**Complexity**: HIGH
- Combat AI or simple "press auto-battle"
- Team selection logic
- Risk of poor matchups

**Impact**: LOW-MEDIUM - Daily rewards, but risky

---

#### 8. Construction Queue Management (Proactive)
**Status**: ⚠️ Reactive only (waits for notifications)

**Description**: Only reacts to building completion notifications

**Opportunity**:
- Proactive building queue management
- Keep 2nd builder slot filled at all times
- Optimize upgrade sequences for efficiency
- Resource-aware building selection

**Complexity**: HIGH
- Requires building state tracking
- Resource inventory tracking
- Upgrade tree knowledge
- Optimization logic

**Impact**: LOW - Small efficiency gain over reactive approach

---

#### 9. Resource Trading / Market Automation
**Status**: ❌ Not automated

**Description**: No market/trading automation

**Opportunity**:
- Auto-buy resources at good prices
- Auto-sell excess resources
- Market arbitrage opportunities

**Complexity**: HIGH
- Price tracking and analysis
- Market UI navigation
- Economic decision logic
- Risk of bad trades

**Impact**: LOW-MEDIUM - Economic optimization

---

#### 10. Troop Training Queue (Proactive)
**Status**: ⚠️ Reactive only (waits for READY state)

**Description**: Barracks only train when detected as READY

**Opportunity**:
- Proactive training queue management
- Keep all 4 barracks constantly training
- Optimize soldier level based on resources
- Predict completion times

**Complexity**: MEDIUM-HIGH
- Requires timing prediction
- Resource tracking
- May interfere with user's training preferences

**Impact**: LOW - Barracks rarely sit idle with reactive approach

---

## 📊 Priority Matrix

| Feature | Impact | Complexity | Effort | Priority |
|---------|--------|------------|--------|----------|
| City Construction Event | HIGH | Medium | 2-3 days | ⭐⭐⭐ |
| Daily Quest Rewards | HIGH | Low | 1 day | ⭐⭐⭐ |
| VIP/Daily Login | HIGH | Low | 1 day | ⭐⭐⭐ |
| Alliance Help | MEDIUM | Medium | 2 days | ⭐⭐ |
| Hero Expedition | MEDIUM | Medium | 2 days | ⭐⭐ |
| Tech Research Event | MEDIUM | Medium | 2-3 days | ⭐⭐ |
| Arena/PvP | LOW-MED | HIGH | 3-5 days | ⭐ |
| Proactive Queues | LOW | HIGH | 4-5 days | ⭐ |
| Market Trading | LOW-MED | HIGH | 3-4 days | ⭐ |

---

## 🎨 What Makes This System Special

The current automation is **enterprise-grade** with sophisticated features:

**Detection Innovation:**
- Hybrid detection (template + pixel counting for barracks)
- Red dot detection (prevents false positives on stamina claims)
- Dog house alignment (prevents coordinate drift)

**Scheduling Intelligence:**
- UTC-based Arms Race event tracking
- Scheduled triggers (2 AM hero upgrades with 3h45m idle requirement)
- Cooldown management (stamina use, AFK rewards, union gifts)

**User Experience:**
- Idle detection (5+ min threshold prevents interfering with active gameplay)
- Crash recovery (fully automatic app restart and reinitialization)
- View state machine (robust TOWN/WORLD/CHAT/UNKNOWN navigation)
- Return-to-base recovery (handles stuck states gracefully)

**Code Quality:**
- Comprehensive documentation (README, arms_race.md, future_steps.md)
- Modular flow architecture (easy to add new flows)
- Template-based detection (easy to recalibrate)
- Configurable thresholds and timings

---

## 🔮 Recommended Roadmap

### Phase 1: Complete Arms Race Coverage
**Goal**: Maximize Arms Race points across all 5 events

1. City Construction Event automation
2. Tech Research Event automation

**Impact**: Full 5/5 Arms Race event coverage

---

### Phase 2: Daily Rewards Optimization
**Goal**: Maximize passive daily income

1. Daily quest reward collection
2. VIP chest / daily login automation
3. Alliance help automation

**Impact**: Significant daily resource gains

---

### Phase 3: Passive Progression
**Goal**: Long-term hero and resource growth

1. Hero expedition automation
2. Consider proactive queue management (if worth effort)

**Impact**: Passive hero XP, queue efficiency

---

### Phase 4: Advanced Features (Optional)
**Goal**: Economic and combat optimization

1. Arena/PvP automation (if safe/worthwhile)
2. Market trading (if profitable)

**Impact**: Competitive edge, economic optimization

---

## 📝 Notes

- **Current system is already excellent** - covers core gameplay loop comprehensively
- **Low-hanging fruit**: Daily rewards, VIP chests (easy wins)
- **High-value targets**: City Construction, Tech Research (Arms Race completion)
- **Avoid over-engineering**: Proactive queue management has diminishing returns
- **Risk assessment**: Arena/PvP and Market require careful consideration

---

## 🤝 Contributing

When implementing new features:

1. **Template extraction**: Use Gemini via `calibration/detect_object.py` for accurate coordinates
2. **Matcher creation**: Follow existing patterns (see `utils/*_matcher.py`)
3. **Flow design**: Use existing flows as templates (see `scripts/flows/*.py`)
4. **Documentation**: Update README.md and this file
5. **Testing**: Verify with debug mode and multiple scenarios

---

## 📚 Related Documentation

- [README.md](../README.md) - Main project documentation
- [arms_race.md](arms_race.md) - Arms Race event details
- [CLAUDE.md](../.claude/CLAUDE.md) - Development guidelines and project context
