        function dashboard() {
            return {
                activeTab: 'dashboard',
                status: { paused: false, active_flows: [], critical_flow: null, stamina: null, idle_seconds: 0, view: null },
                armsRace: { current_event: 'Loading...', previous_event: '', next_event: '', day: 1, time_remaining_seconds: 0, next_occurrences: {} },
                flows: [],
                titles: [],
                selectedTitle: '',
                qpMarking: false,
                qpStatusText: '',
                zombieMode: { mode: 'elite', expires: null, hours_remaining: null },
                zombieModes: {},  // Loaded from /api/zombie-modes
                selectedZombieMode: 'elite',
                zombieModeHours: 24,
                // Reinforce loop mode
                reinforceMode: { active: false, interval: 10, expires: null, hours_remaining: null },
                reinforceInterval: 10,  // Seconds between runs
                // Burst mode state (uses selectedZombieMode for flow type)
                burstMode: {
                    running: false,
                    count: 5,
                    delay: 300,  // seconds
                    completed: 0,
                    nextRunIn: 0,
                    intervalId: null,
                    countdownId: null
                },
                toast: { show: false, message: '', type: 'info' },
                dailyCheckin: { checked_in: false, timestamp: null },
                tavernQuests: { assist_allies: { current: null, max: 5 }, plunder_others: { current: null, max: 5 }, timestamp: null },
                tavernStatus: { gold_visible: null, question_visible: null, dispatchable_visible: null, directly_startable_visible: null, refresh_candidates: null, refreshes_today: 0, refreshes_this_attempt: null, checked_at: null, exhausted_today: false, claims_today: 0 },
                researchQueue: { queue1_seconds: null, queue1_name: null, queue2_seconds: null, queue2_name: null, timestamp: null },
                constructionQueue: { queue1_seconds: null, queue1_name: null, queue2_seconds: null, queue2_name: null, timestamp: null },
                pendingQuests: [],
                lastUpdate: '--:--',
                pollInterval: null,
                countdownInterval: null,
                // Config overrides
                configs: {},
                activeOverrides: {},
                rallyMonsters: [],
                overrideDurations: {},
                staminaThreshold: 118,
                targetLevel: 30,
                // Arms Race score check
                armsRaceScore: { current_points: null, chest3_target: null, points_to_chest3: null, speedup_minutes_needed: null, last_checked: null, error: null },
                armsRaceScoreLoading: false,
                // Shield inventory
                shieldInventory: { '8hr': null, '12hr': null, '24hr': null, timestamp: null },
                shieldRefreshing: false,
                // Screenshot
                screenshotLoading: false,
                lastScreenshot: null,
                // Shield scheduling
                showShieldScheduleModal: false,
                scheduleShieldType: '8hr',
                scheduleDelayInput: '',
                scheduledShield: null,  // { shield_type, activate_at, seconds_remaining }
                // Under attack state
                underAttack: false,
                underAttackTime: null,
                // Bloodlust state
                bloodlust: { active: false, started_at: null, expected_end: null, seconds_remaining: null },
                // Shield protection state
                shieldProtectionActive: false,
                // Stamina claim timer (checked once at Beast Training block start)
                staminaClaimTimer: { seconds_remaining: null, claim_available: null, checked_at: null },
                // Block Timeline
                blocks: {
                    blocks: [],
                    current_event: null,
                    time_remaining: null,
                    vs_day: null,
                    vs_info: null,
                    is_special_day: false,
                    server_reset_in: null,
                    day_boundaries: [],
                    lastRefresh: null
                },
                // Events list
                events: { past: [], future: [], lastRefresh: null },
                scoreCheckInterval: null,
                lastScoreCheckEvent: null,
                // DM Sessions state
                dmSessions: [],
                dmLoading: false,
                selectedDmSession: null,
                dmMessages: [],
                dmMessagesLoading: false,
                // Player Profile state
                playerProfile: {
                    name: null,
                    level: 0,
                    vip_level: 0,
                    guild: '',
                    ce: 0,
                    campaign_stage: 0,
                    title: null,
                    avatar_url: null,
                    role_id: null,
                    world_id: null,
                },
                profileLoading: false,
                profileLastUpdated: null,

                async init() {
                    // Load persisted state FIRST (survives page refresh)
                    await this.loadPersistedState();

                    await Promise.all([
                        this.refreshStatus(),
                        this.refreshFlows(),
                        this.refreshArmsRace(),
                        this.refreshPendingQuests(),
                        this.refreshTavernStatus(),
                        this.loadTitles(),
                        this.loadZombieModes(),
                        this.loadZombieMode(),
                        this.loadReinforceMode(),
                        this.loadConfig(),
                        this.refreshBlocks(),
                        this.refreshEvents(),
                        this.refreshScheduledShield()
                    ]);
                    this.pollInterval = setInterval(() => {
                        this.refreshStatus();
                        this.refreshFlows();
                        this.refreshArmsRace();
                        // Refresh under attack state every 10s
                        this.refreshUnderAttack();
                        // Refresh scheduled shield
                        this.refreshScheduledShield();
                        // Refresh pending quests every 30s
                        if (!this._lastPendingQuestsRefresh || Date.now() - this._lastPendingQuestsRefresh > 30000) {
                            this.refreshPendingQuests();
                            this.refreshTavernStatus();
                            this._lastPendingQuestsRefresh = Date.now();
                        }
                        // Refresh blocks every 30s (not every 3s)
                        if (!this.blocks.lastRefresh || Date.now() - this.blocks.lastRefresh > 30000) {
                            this.refreshBlocks();
                        }
                        // Refresh events every 60s
                        if (!this.events.lastRefresh || Date.now() - this.events.lastRefresh > 60000) {
                            this.refreshEvents();
                        }
                    }, 3000);
                    this.countdownInterval = setInterval(() => {
                        if (this.armsRace.time_remaining_seconds > 0) this.armsRace.time_remaining_seconds--;
                        // Decrement scheduled shield countdown
                        if (this.scheduledShield && this.scheduledShield.seconds_remaining > 0) {
                            this.scheduledShield.seconds_remaining--;
                            if (this.scheduledShield.seconds_remaining <= 0) {
                                this.scheduledShield = null; // Clear when activated
                            }
                        }
                        // Decrement bloodlust countdown
                        if (this.bloodlust.active && this.bloodlust.seconds_remaining > 0) {
                            this.bloodlust.seconds_remaining--;
                            if (this.bloodlust.seconds_remaining <= 0) {
                                this.bloodlust.active = false; // Clear when expired
                            }
                        }
                        // Decrement pending quest countdowns
                        this.pendingQuests.forEach(q => q.remaining_seconds--);
                        // Remove completed quests (remaining_seconds <= -60 means 1 minute past completion)
                        this.pendingQuests = this.pendingQuests.filter(q => q.remaining_seconds > -60);
                    }, 1000);
                    // Auto score check every hour (3600000ms)
                    this.scoreCheckInterval = setInterval(() => {
                        this.autoCheckScore();
                    }, 3600000);
                    // Also check if we changed Arms Race event (every 30s)
                    setInterval(() => {
                        this.checkEventChange();
                    }, 30000);
                },

                async refreshStatus() {
                    try {
                        const res = await fetch('/api/status');
                        this.status = await res.json();
                        this.lastUpdate = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                    } catch (e) { console.error('Status fetch failed:', e); }
                },

                async refreshFlows() {
                    try {
                        const res = await fetch('/api/flows');
                        this.flows = await res.json();
                    } catch (e) { console.error('Flows fetch failed:', e); }
                },

                async refreshUnderAttack() {
                    try {
                        const res = await fetch('/api/current-state');
                        const state = await res.json();
                        if (state.under_attack) {
                            this.underAttack = state.under_attack.is_under_attack || false;
                            this.underAttackTime = state.under_attack.last_detected
                                ? new Date(state.under_attack.last_detected).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
                                : null;
                        }
                        // Also refresh bloodlust from same state
                        if (state.bloodlust) {
                            this.bloodlust.active = state.bloodlust.is_active || false;
                            this.bloodlust.started_at = state.bloodlust.started_at;
                            this.bloodlust.expected_end = state.bloodlust.expected_end;
                            if (this.bloodlust.expected_end && this.bloodlust.active) {
                                const endTime = new Date(this.bloodlust.expected_end);
                                const now = new Date();
                                this.bloodlust.seconds_remaining = Math.max(0, Math.floor((endTime - now) / 1000));
                            } else {
                                this.bloodlust.seconds_remaining = null;
                            }
                        }
                        // Refresh shield protection status
                        if (state.shield_active) {
                            this.shieldProtectionActive = state.shield_active.is_active || false;
                        }
                    } catch (e) { /* ignore */ }
                },

                async refreshArmsRace() {
                    try {
                        const res = await fetch('/api/arms-race');
                        this.armsRace = await res.json();
                    } catch (e) { console.error('Arms race fetch failed:', e); }
                },

                async refreshPendingQuests() {
                    try {
                        const res = await fetch('/api/tavern-quests');
                        const data = await res.json();
                        this.pendingQuests = data.quests || [];
                    } catch (e) { console.error('Pending quests fetch failed:', e); }
                },

                async refreshTavernStatus() {
                    try {
                        const res = await fetch('/api/tavern-status');
                        const data = await res.json();
                        this.tavernStatus = {
                            gold_visible: data.gold_visible,
                            question_visible: data.question_visible,
                            dispatchable_visible: data.dispatchable_visible,
                            directly_startable_visible: data.directly_startable_visible,
                            refresh_candidates: data.refresh_candidates,
                            refreshes_today: data.refreshes_today ?? 0,
                            refreshes_this_attempt: data.refreshes_this_attempt,
                            checked_at: data.checked_at,
                            exhausted_today: !!data.exhausted_today,
                            claims_today: data.claims_today ?? 0,
                        };
                    } catch (e) { console.error('Tavern status fetch failed:', e); }
                },

                async clearTavernExhaustion() {
                    try {
                        const res = await fetch('/api/tavern-status/clear-exhaustion', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast('Tavern exhaustion cleared — daemon will re-check on next dispatch', 'success');
                            await this.refreshTavernStatus();
                        } else {
                            this.showToast('Failed to clear exhaustion', 'error');
                        }
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async loadPersistedState() {
                    // Load persisted state from file (survives page refresh)
                    try {
                        const res = await fetch('/api/current-state');
                        const state = await res.json();

                        // Restore Arms Race score if we have one
                        if (state.arms_race_score && state.arms_race_score.current_points !== null) {
                            this.armsRaceScore = {
                                current_points: state.arms_race_score.current_points,
                                chest3_target: state.arms_race_score.chest3_target || 30000,
                                points_to_chest3: state.arms_race_score.points_to_chest3,
                                speedup_minutes_needed: state.arms_race_score.speedup_minutes_needed,
                                last_checked: state.arms_race_score.timestamp,
                                error: null
                            };
                            console.log('Restored Arms Race score from persisted state:', this.armsRaceScore);
                        }

                        // Restore stamina if we have it (and status doesn't have it yet)
                        if (state.stamina && state.stamina.value !== null) {
                            // Will be overwritten by refreshStatus if daemon has newer data
                            console.log('Persisted stamina:', state.stamina.value);
                        }

                        // Restore zombie mode
                        if (state.zombie_mode && state.zombie_mode.mode) {
                            this.zombieMode.mode = state.zombie_mode.mode;
                            this.zombieMode.expires = state.zombie_mode.expires;
                            this.selectedZombieMode = state.zombie_mode.mode;  // Sync dropdown
                        }

                        // Restore stamina claim timer
                        if (state.stamina_claim_timer) {
                            this.staminaClaimTimer = state.stamina_claim_timer;
                        }

                        // Restore daily check-in status
                        if (state.daily_checkin) {
                            this.dailyCheckin = state.daily_checkin;
                        }

                        // Restore tavern quests status
                        if (state.tavern_quests) {
                            this.tavernQuests = state.tavern_quests;
                        }

                        // Restore research queue status
                        if (state.research_queue) {
                            this.researchQueue = state.research_queue;
                        }

                        if (state.construction_queue) {
                            this.constructionQueue = state.construction_queue;
                        }

                        // Restore shield inventory
                        if (state.shield_inventory) {
                            this.shieldInventory = state.shield_inventory;
                        }

                        // Restore under attack state
                        if (state.under_attack) {
                            this.underAttack = state.under_attack.is_under_attack || false;
                            this.underAttackTime = state.under_attack.last_detected
                                ? new Date(state.under_attack.last_detected).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
                                : null;
                        }

                        // Restore bloodlust state
                        if (state.bloodlust) {
                            this.bloodlust.active = state.bloodlust.is_active || false;
                            this.bloodlust.started_at = state.bloodlust.started_at;
                            this.bloodlust.expected_end = state.bloodlust.expected_end;
                            if (this.bloodlust.expected_end) {
                                const endTime = new Date(this.bloodlust.expected_end);
                                const now = new Date();
                                this.bloodlust.seconds_remaining = Math.max(0, Math.floor((endTime - now) / 1000));
                            }
                        }

                        // Restore shield protection state
                        if (state.shield_active) {
                            this.shieldProtectionActive = state.shield_active.is_active || false;
                        }

                    } catch (e) {
                        console.log('No persisted state available (first run?):', e.message);
                    }
                },

                // =============================================
                // Block Timeline Methods
                // =============================================

                async refreshBlocks() {
                    try {
                        const res = await fetch('/api/timeline/blocks');
                        const data = await res.json();
                        this.blocks = {
                            blocks: data.blocks || [],
                            current_event: data.current_event || null,
                            time_remaining: data.time_remaining || null,
                            vs_day: data.vs_day || null,
                            vs_info: data.vs_info || null,
                            is_special_day: data.is_special_day || false,
                            server_reset_in: data.server_reset_in || null,
                            day_boundaries: data.day_boundaries || [],
                            lastRefresh: Date.now()
                        };
                    } catch (e) { console.error('Blocks fetch failed:', e); }
                },

                async refreshEvents() {
                    try {
                        const res = await fetch('/api/timeline');
                        const data = await res.json();
                        this.events = {
                            past: (data.past_events || []).reverse(),  // Most recent first
                            future: data.future_events || [],
                            lastRefresh: Date.now()
                        };
                    } catch (e) { console.error('Events fetch failed:', e); }
                },

                // =============================================
                // DM Sessions Methods
                // =============================================

                async refreshDmSessions() {
                    this.dmLoading = true;
                    try {
                        const res = await fetch('/api/dm-sessions');
                        const data = await res.json();
                        this.dmSessions = data.sessions || [];
                    } catch (e) {
                        console.error('DM sessions fetch failed:', e);
                        this.showToast('Failed to load DM sessions', 'error');
                    } finally {
                        this.dmLoading = false;
                    }
                },

                async selectDmSession(otherId) {
                    this.selectedDmSession = otherId;
                    this.dmMessagesLoading = true;
                    try {
                        const res = await fetch(`/api/dm-sessions/${otherId}?limit=100`);
                        const data = await res.json();
                        this.dmMessages = data.messages || [];
                    } catch (e) {
                        console.error('DM messages fetch failed:', e);
                        this.showToast('Failed to load messages', 'error');
                    } finally {
                        this.dmMessagesLoading = false;
                    }
                },

                formatDmTime(timestamp) {
                    if (!timestamp) return '';
                    const date = new Date(timestamp * 1000);
                    const now = new Date();
                    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
                    if (diffDays === 0) {
                        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                    } else if (diffDays === 1) {
                        return 'Yesterday';
                    } else if (diffDays < 7) {
                        return date.toLocaleDateString('en-US', { weekday: 'short' });
                    } else {
                        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    }
                },

                formatDmMessageTime(timestamp) {
                    if (!timestamp) return '';
                    const date = new Date(timestamp * 1000);
                    return date.toLocaleString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                },

                // Player Profile methods
                async refreshPlayerProfile() {
                    this.profileLoading = true;
                    try {
                        const res = await fetch('/api/player-profile');
                        const data = await res.json();
                        if (data.success && data.profile) {
                            this.playerProfile = data.profile;
                            this.profileLastUpdated = new Date().toLocaleTimeString();
                        } else {
                            this.showToast(data.error || 'Failed to load profile', 'error');
                        }
                    } catch (e) {
                        console.error('Profile fetch failed:', e);
                        this.showToast('Failed to load profile', 'error');
                    } finally {
                        this.profileLoading = false;
                    }
                },

                autoCheckScore() {
                    // Auto-check score every hour if we haven't checked in the last 55 minutes
                    const lastChecked = this.armsRaceScore.last_checked;
                    const fiftyFiveMinutes = 55 * 60 * 1000;
                    if (!lastChecked || Date.now() - new Date(lastChecked).getTime() > fiftyFiveMinutes) {
                        console.log('Auto-checking Arms Race score (hourly)');
                        this.checkArmsRaceScore();
                    }
                },

                checkEventChange() {
                    // Check if Arms Race event changed - if so, reset score and check
                    const currentEvent = this.blocks.current_event;
                    if (currentEvent && currentEvent !== this.lastScoreCheckEvent) {
                        console.log(`Arms Race event changed: ${this.lastScoreCheckEvent} -> ${currentEvent}`);
                        this.lastScoreCheckEvent = currentEvent;
                        // Reset score for new event
                        this.armsRaceScore = { current_points: null, chest3_target: null, points_to_chest3: null, last_checked: null, error: null };
                        // Auto-check score for new event after 30 seconds
                        setTimeout(() => this.checkArmsRaceScore(), 30000);
                    }
                },

                formatEventTime(isoDate) {
                    if (!isoDate) return '';
                    const date = new Date(isoDate);
                    const now = new Date();
                    const diffMins = Math.round((date - now) / 60000);
                    const timeStr = date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });

                    if (Math.abs(diffMins) < 1) return 'now';
                    if (diffMins < 0) {
                        if (diffMins > -60) return `${-diffMins}m ago`;
                        if (diffMins > -1440) return timeStr;
                        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    }
                    if (diffMins < 60) return `in ${diffMins}m`;
                    if (diffMins < 1440) return timeStr;
                    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                },

                async checkArmsRaceScore() {
                    this.armsRaceScoreLoading = true;
                    this.armsRaceScore.error = null;
                    try {
                        const res = await fetch('/api/arms-race/check-score', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            // Calculate speedup minutes if not provided by API
                            let speedupMins = data.speedup_minutes_needed;
                            if (!speedupMins && data.points_to_chest3 > 0) {
                                speedupMins = Math.floor(data.points_to_chest3 / 10);
                            }
                            this.armsRaceScore = {
                                current_points: data.current_points,
                                chest3_target: data.chest3_target,
                                points_to_chest3: data.points_to_chest3,
                                speedup_minutes_needed: speedupMins,
                                last_checked: new Date().toISOString(),
                                error: null
                            };
                            this.showToast(`Score: ${data.current_points?.toLocaleString() || 0} points`, 'success');
                        } else {
                            this.armsRaceScore.error = data.error || 'Failed to check score';
                            this.showToast(this.armsRaceScore.error, 'error');
                        }
                    } catch (e) {
                        this.armsRaceScore.error = e.message;
                        this.showToast(`Error: ${e.message}`, 'error');
                    } finally {
                        this.armsRaceScoreLoading = false;
                    }
                },

                async refreshShields() {
                    if (this.shieldRefreshing) return;
                    this.shieldRefreshing = true;
                    try {
                        const res = await fetch('/api/shields/refresh', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            this.shieldInventory = {
                                '8hr': data['8hr'],
                                '12hr': data['12hr'],
                                '24hr': data['24hr'],
                                timestamp: new Date().toISOString()
                            };
                            this.showToast(`Shields: ${data['8hr'] ?? '-'}/${data['12hr'] ?? '-'}/${data['24hr'] ?? '-'}`, 'success');
                        } else {
                            this.showToast(data.error || 'Failed to refresh shields', 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    } finally {
                        this.shieldRefreshing = false;
                    }
                },

                async takeScreenshot() {
                    if (this.screenshotLoading) return;
                    this.screenshotLoading = true;
                    try {
                        const res = await fetch('/api/screenshot');
                        const data = await res.json();
                        if (data.success) {
                            this.lastScreenshot = data;
                            this.showToast(`Screenshot saved: ${data.filename}`, 'success');
                        } else {
                            this.showToast(data.detail || 'Screenshot failed', 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    } finally {
                        this.screenshotLoading = false;
                    }
                },

                async useShield(duration) {
                    this.showToast(`Activating ${duration} shield...`, 'info');
                    try {
                        const res = await fetch('/api/shields/use', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ shield_type: duration })
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`${duration} shield activated!`, 'success');
                            // Update local inventory count
                            if (this.shieldInventory[duration] !== null && this.shieldInventory[duration] > 0) {
                                this.shieldInventory[duration]--;
                            }
                            // Clear under attack state since we now have protection
                            this.underAttack = false;
                        } else {
                            this.showToast(`Failed: ${data.error || 'Unknown error'}`, 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                parseTimeInput(input) {
                    // Parse time input like "9m 13s", "1h 30m", "90s", "5m", "10:30" (time of day)
                    if (!input || !input.trim()) return null;
                    input = input.trim().toLowerCase();

                    // Check for time of day format (HH:MM)
                    const timeMatch = input.match(/^(\d{1,2}):(\d{2})$/);
                    if (timeMatch) {
                        const hours = parseInt(timeMatch[1]);
                        const minutes = parseInt(timeMatch[2]);
                        const now = new Date();
                        const target = new Date();
                        target.setHours(hours, minutes, 0, 0);
                        if (target <= now) {
                            target.setDate(target.getDate() + 1); // Tomorrow if time already passed
                        }
                        return Math.floor((target - now) / 1000);
                    }

                    // Parse duration format (e.g., "1h 30m 15s", "5m", "90s")
                    let totalSeconds = 0;
                    const hourMatch = input.match(/(\d+)\s*h/);
                    const minMatch = input.match(/(\d+)\s*m(?!s)/);
                    const secMatch = input.match(/(\d+)\s*s/);

                    if (hourMatch) totalSeconds += parseInt(hourMatch[1]) * 3600;
                    if (minMatch) totalSeconds += parseInt(minMatch[1]) * 60;
                    if (secMatch) totalSeconds += parseInt(secMatch[1]);

                    // If no units matched, try parsing as just seconds
                    if (!hourMatch && !minMatch && !secMatch) {
                        const num = parseInt(input);
                        if (!isNaN(num)) totalSeconds = num;
                    }

                    return totalSeconds > 0 ? totalSeconds : null;
                },

                async scheduleShield() {
                    const delaySeconds = this.parseTimeInput(this.scheduleDelayInput);
                    if (!delaySeconds) {
                        this.showToast('Invalid time format. Try "9m 13s" or "10:30"', 'error');
                        return;
                    }

                    try {
                        const res = await fetch('/api/shields/schedule', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                shield_type: this.scheduleShieldType,
                                delay_seconds: delaySeconds
                            })
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`${this.scheduleShieldType} shield scheduled in ${this.formatCountdown(delaySeconds)}`, 'success');
                            this.showShieldScheduleModal = false;
                            this.scheduleDelayInput = '';
                            this.refreshScheduledShield();
                        } else {
                            this.showToast(data.error || 'Failed to schedule', 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async cancelScheduledShield() {
                    try {
                        const res = await fetch('/api/shields/cancel', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`Cancelled scheduled ${data.cancelled} shield`, 'info');
                            this.scheduledShield = null;
                        } else {
                            this.showToast(data.error || 'Nothing to cancel', 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async refreshScheduledShield() {
                    try {
                        const res = await fetch('/api/shields/scheduled');
                        const data = await res.json();
                        if (data.scheduled) {
                            const activateAt = new Date(data.activate_at);
                            const now = new Date();
                            const secondsRemaining = Math.max(0, Math.floor((activateAt - now) / 1000));
                            this.scheduledShield = {
                                shield_type: data.shield_type,
                                activate_at: data.activate_at,
                                seconds_remaining: secondsRemaining
                            };
                        } else {
                            this.scheduledShield = null;
                        }
                    } catch (e) {
                        // Ignore errors
                    }
                },

                async runFlow(name) {
                    try {
                        const res = await fetch(`/api/flows/${name}/run`, { method: 'POST' });
                        const data = await res.json();
                        this.showToast(data.success ? `Started ${this.formatFlowName(name)}` : `Failed: ${data.detail}`, data.success ? 'success' : 'error');
                        await this.refreshFlows();
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async runZombieOnce() {
                    // Run zombie using current selectedZombieMode and targetLevel
                    try {
                        const mode = this.selectedZombieMode;
                        const level = this.targetLevel;
                        let body;

                        if (mode === 'elite') {
                            body = { cmd: 'run_elite_zombie', args: { target_level: level } };
                        } else {
                            // gold, food, iron_mine -> zombie_attack
                            body = { cmd: 'run_zombie_attack', args: { zombie_type: mode, target_level: level } };
                        }

                        this.showToast(`Running ${this.getZombieModeDisplay(mode)} at level ${level}...`, 'info');
                        const res = await fetch('/api/ws/command', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`Started ${this.getZombieModeDisplay(mode)} (Lv ${level})`, 'success');
                        } else {
                            this.showToast(`Failed: ${data.error || data.detail}`, 'error');
                        }
                        await this.refreshFlows();
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async togglePause() {
                    try {
                        await fetch(this.status.paused ? '/api/resume' : '/api/pause', { method: 'POST' });
                        await this.refreshStatus();
                        this.showToast(this.status.paused ? 'Paused' : 'Resumed', 'info');
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async returnToBase() {
                    try {
                        this.showToast('Returning to base...', 'info');
                        const res = await fetch('/api/return-to-base', { method: 'POST' });
                        const data = await res.json();
                        this.showToast(data.success ? 'Returned to base' : 'Failed', data.success ? 'success' : 'error');
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async loadTitles() {
                    try {
                        const res = await fetch('/api/titles');
                        const data = await res.json();
                        this.titles = data.titles || [];
                    } catch (e) { console.error('Titles load failed:', e); }
                },

                async applyTitle() {
                    if (!this.selectedTitle) return;
                    try {
                        this.showToast(`Applying ${this.selectedTitle}...`, 'info');
                        const res = await fetch(`/api/titles/${this.selectedTitle}/apply`, { method: 'POST' });
                        const data = await res.json();
                        this.showToast(data.success ? `Applied ${this.selectedTitle}` : `Failed: ${data.detail}`, data.success ? 'success' : 'error');
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async markQuickProductionDone(verifyOcr) {
                    if (this.qpMarking) return;
                    this.qpMarking = true;
                    this.qpStatusText = verifyOcr ? 'Navigating to Class Skill panel...' : 'Marking done...';
                    try {
                        const res = await fetch('/api/quick-production/mark-done', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({verify_ocr: !!verifyOcr}),
                        });
                        const data = await res.json();
                        if (!data.success) {
                            this.qpStatusText = '';
                            this.showToast(`Failed: ${data.error || 'unknown error'}`, 'error');
                            return;
                        }
                        const hrs = (data.remaining_seconds / 3600).toFixed(1);
                        const nextDate = new Date(data.next_run_iso);
                        const niceTime = nextDate.toLocaleString();
                        const srcTag = data.source === 'ocr' ? 'via OCR' : '(default 24h)';
                        this.qpStatusText = `Next: ${niceTime} ${srcTag}`;
                        let toast = `Quick Production: next run ${niceTime} (in ${hrs}h) ${srcTag}`;
                        if (data.reason) toast += ` — ${data.reason}`;
                        this.showToast(toast, 'success');
                    } catch (e) {
                        this.qpStatusText = '';
                        this.showToast(`Error: ${e.message}`, 'error');
                    } finally {
                        this.qpMarking = false;
                    }
                },

                async loadZombieModes() {
                    // Load available zombie modes from config (dynamic stamina values)
                    try {
                        const res = await fetch('/api/zombie-modes');
                        const data = await res.json();
                        this.zombieModes = data.modes || {};
                    } catch (e) {
                        console.error('Zombie modes load failed:', e);
                        // Fallback to defaults if API fails
                        this.zombieModes = {
                            'elite': { stamina: 20, points: 2000 },
                            'gold': { stamina: 10, points: 1000 },
                            'food': { stamina: 10, points: 1000 },
                            'iron_mine': { stamina: 10, points: 1000 }
                        };
                    }
                },

                async loadZombieMode() {
                    try {
                        const res = await fetch('/api/zombie-mode');
                        const data = await res.json();
                        this.zombieMode = { mode: data.mode || 'elite', expires: data.expires, hours_remaining: data.hours_remaining };
                        this.selectedZombieMode = this.zombieMode.mode;
                        if (data.hours_remaining != null) {
                            this.zombieModeHours = Math.max(0.5, Math.round(data.hours_remaining * 10) / 10);
                        }
                    } catch (e) { console.error('Zombie mode load failed:', e); }
                },

                async setZombieMode() {
                    try {
                        const hours = this.zombieModeHours || 24;
                        const res = await fetch(`/api/zombie-mode/${this.selectedZombieMode}?hours=${encodeURIComponent(hours)}`, { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            if (this.selectedZombieMode === 'elite') {
                                const durationVal = this.overrideDurations?.['ELITE_ZOMBIE_TARGET_LEVEL'];
                                const duration = durationVal ? parseInt(durationVal) : null;
                                await fetch('/api/config/ELITE_ZOMBIE_TARGET_LEVEL/override', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ value: this.targetLevel, duration_minutes: duration })
                                });
                            }
                            this.showToast(`Zombie mode: ${this.getZombieModeDisplay(this.selectedZombieMode)}`, 'success');
                            await this.loadZombieMode();
                        } else {
                            this.showToast(`Failed: ${data.detail}`, 'error');
                        }
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async applyZombieSettings() {
                    // Combined: sets zombie mode + applies stamina/level overrides
                    try {
                        const hours = this.zombieModeHours || 24;
                        const res = await fetch(`/api/zombie-mode/${this.selectedZombieMode}?hours=${encodeURIComponent(hours)}`, { method: 'POST' });
                        const data = await res.json();
                        if (!data.success) {
                            this.showToast(`Failed: ${data.detail}`, 'error');
                            return;
                        }

                        if (this.selectedZombieMode === 'elite') {
                            const levelDuration = this.overrideDurations?.['ELITE_ZOMBIE_TARGET_LEVEL'];
                            const thresholdDuration = this.overrideDurations?.['ELITE_ZOMBIE_STAMINA_THRESHOLD'];

                            await fetch('/api/config/ELITE_ZOMBIE_TARGET_LEVEL/override', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: this.targetLevel, duration_minutes: levelDuration ? parseInt(levelDuration) : null })
                            });

                            await fetch('/api/config/ELITE_ZOMBIE_STAMINA_THRESHOLD/override', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: this.staminaThreshold, duration_minutes: thresholdDuration ? parseInt(thresholdDuration) : null })
                            });
                        }

                        this.showToast(`Applied: ${this.getZombieModeDisplay(this.selectedZombieMode)} mode`, 'success');
                        await Promise.all([this.loadZombieMode(), this.loadConfig()]);
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async runCurrentZombie() {
                    // Run the currently active zombie mode flow
                    const mode = this.zombieMode.mode || 'elite';
                    const flowMap = {
                        'elite': 'elite_zombie',
                        'gold': 'zombie_attack_gold',
                        'food': 'zombie_attack_food',
                        'iron_mine': 'zombie_attack_iron_mine'
                    };
                    const flowName = flowMap[mode] || 'elite_zombie';
                    await this.runFlow(flowName);
                },

                getZombieModeDisplay(mode) {
                    const displays = {
                        'elite': 'Elite Zombie',
                        'overlord': 'Zombie Overlord',
                        'gold': 'Gold Mine',
                        'food': 'Food Farm',
                        'iron_mine': 'Iron Mine'
                    };
                    return displays[mode] || mode;
                },

                // Reinforce Mode Methods
                async loadReinforceMode() {
                    try {
                        const res = await fetch('/api/reinforce-mode');
                        const data = await res.json();
                        this.reinforceMode = {
                            active: data.active || false,
                            interval: data.interval || 10,
                            expires: data.expires,
                            hours_remaining: data.hours_remaining
                        };
                        this.reinforceInterval = data.interval || 10;
                    } catch (e) { console.error('Reinforce mode load failed:', e); }
                },

                async startReinforce() {
                    try {
                        const res = await fetch('/api/reinforce-mode/start', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ interval: this.reinforceInterval })
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`Reinforce loop started (${this.reinforceInterval}s interval)`, 'success');
                            await this.loadReinforceMode();
                        } else {
                            this.showToast(`Failed: ${data.detail}`, 'error');
                        }
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                async stopReinforce() {
                    try {
                        const res = await fetch('/api/reinforce-mode/stop', { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast('Reinforce loop stopped', 'success');
                            await this.loadReinforceMode();
                        } else {
                            this.showToast(`Failed: ${data.detail}`, 'error');
                        }
                    } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); }
                },

                // =============================================
                // Burst Mode Methods
                // =============================================

                async startBurstMode() {
                    // Use selectedZombieMode and convert to flow name
                    const mode = this.selectedZombieMode;
                    const cfg = this.zombieModes[mode] || { stamina: 20, flow: 'elite_zombie' };
                    const flow = cfg.flow || ((mode === 'elite' || mode === 'overlord') ? 'elite_zombie' : `zombie_attack_${mode}`);
                    const staminaCost = cfg.stamina || 20;

                    this.burstMode.running = true;
                    this.burstMode.completed = 0;
                    this.showToast(`Starting burst: ${this.formatFlowName(flow)}`, 'info');

                    // Run immediately first
                    await this.runBurstIteration(flow, staminaCost);

                    // Schedule subsequent runs
                    if (this.burstMode.running) {
                        this.burstMode.nextRunIn = this.burstMode.delay;
                        this.scheduleBurstNext(flow, staminaCost);
                    }
                },

                async runBurstIteration(flow, staminaCost) {
                    // Check if we've hit the count limit
                    if (this.burstMode.completed >= this.burstMode.count) {
                        this.showToast(`Burst complete: ${this.burstMode.completed} runs`, 'success');
                        this.stopBurstMode();
                        return false;
                    }

                    // Run the flow
                    try {
                        const res = await fetch(`/api/flows/${flow}/run`, { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                            this.burstMode.completed++;
                            await this.refreshFlows();
                        } else {
                            this.showToast(`Burst error: ${data.detail}`, 'error');
                            this.stopBurstMode();
                            return false;
                        }
                    } catch (e) {
                        this.showToast(`Burst error: ${e.message}`, 'error');
                        this.stopBurstMode();
                        return false;
                    }

                    return true;
                },

                scheduleBurstNext(flow, staminaCost) {
                    // Countdown timer
                    this.burstMode.countdownId = setInterval(() => {
                        this.burstMode.nextRunIn--;
                        if (this.burstMode.nextRunIn <= 0) {
                            clearInterval(this.burstMode.countdownId);
                        }
                    }, 1000);

                    // Schedule next run
                    this.burstMode.intervalId = setTimeout(async () => {
                        clearInterval(this.burstMode.countdownId);

                        if (!this.burstMode.running) return;

                        // Refresh status to get current stamina
                        await this.refreshStatus();

                        const shouldContinue = await this.runBurstIteration(flow, staminaCost);
                        if (shouldContinue && this.burstMode.running) {
                            // Check if more runs needed
                            if (this.burstMode.completed < this.burstMode.count) {
                                this.burstMode.nextRunIn = this.burstMode.delay;
                                this.scheduleBurstNext(flow, staminaCost);
                            } else {
                                this.showToast(`Burst complete: ${this.burstMode.completed} runs`, 'success');
                                this.stopBurstMode();
                            }
                        }
                    }, this.burstMode.delay * 1000);
                },

                stopBurstMode() {
                    this.burstMode.running = false;
                    if (this.burstMode.intervalId) {
                        clearTimeout(this.burstMode.intervalId);
                        this.burstMode.intervalId = null;
                    }
                    if (this.burstMode.countdownId) {
                        clearInterval(this.burstMode.countdownId);
                        this.burstMode.countdownId = null;
                    }
                    this.burstMode.nextRunIn = 0;
                },

                showToast(message, type = 'info') {
                    this.toast = { show: true, message, type };
                    setTimeout(() => { this.toast.show = false; }, 3000);
                },

                formatFlowName(name) {
                    return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                },

                formatSeconds(secs) {
                    if (!secs) return '0:00';
                    const m = Math.floor(secs / 60);
                    const s = Math.floor(secs % 60);
                    return `${m}:${s.toString().padStart(2, '0')}`;
                },

                formatCountdown(secs) {
                    if (!secs) return '0:00:00';
                    const h = Math.floor(secs / 3600);
                    const m = Math.floor((secs % 3600) / 60);
                    const s = Math.floor(secs % 60);
                    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                },

                formatSecondsToHM(secs) {
                    if (!secs || secs <= 0) return 'NOW';
                    const h = Math.floor(secs / 3600);
                    const m = Math.floor((secs % 3600) / 60);
                    if (h > 0) return `${h}h ${m}m`;
                    return `${m}m`;
                },

                formatSecondsToTime(secs) {
                    if (!secs || secs <= 0) return '--';
                    const d = Math.floor(secs / 86400);
                    const h = Math.floor((secs % 86400) / 3600);
                    const m = Math.floor((secs % 3600) / 60);
                    const s = Math.floor(secs % 60);
                    if (d > 0) return `${d}d ${h}h ${m}m`;
                    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
                },

                formatSpeedupTime(minutes) {
                    if (!minutes || minutes <= 0) return '--';
                    const d = Math.floor(minutes / 1440);
                    const h = Math.floor((minutes % 1440) / 60);
                    const m = minutes % 60;
                    if (d > 0) return `${d}d ${h}h ${m}m`;
                    if (h > 0) return `${h}h ${m}m`;
                    return `${m}m`;
                },

                formatClaimTimer() {
                    // Calculate remaining time from stored timer, adjusted for elapsed time
                    if (!this.staminaClaimTimer.seconds_remaining) return '--';
                    let remaining = this.staminaClaimTimer.seconds_remaining;

                    // Subtract elapsed time since we checked
                    if (this.staminaClaimTimer.checked_at) {
                        const elapsed = Math.floor((new Date() - new Date(this.staminaClaimTimer.checked_at)) / 1000);
                        remaining = Math.max(0, remaining - elapsed);
                    }

                    if (remaining <= 0) return 'Ready!';
                    const h = Math.floor(remaining / 3600);
                    const m = Math.floor((remaining % 3600) / 60);
                    if (h > 0) return `${h}h ${m}m`;
                    return `${m}m`;
                },

                formatLastRun(isoDate) {
                    if (!isoDate) return '';
                    const diffMins = Math.floor((new Date() - new Date(isoDate)) / 60000);
                    if (diffMins < 1) return 'Just now';
                    if (diffMins < 60) return `${diffMins}m ago`;
                    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
                    return new Date(isoDate).toLocaleDateString();
                },

                formatTimeAgo(isoDate) {
                    if (!isoDate) return '';
                    const diffMins = Math.floor((new Date() - new Date(isoDate)) / 60000);
                    if (diffMins < 1) return 'just now';
                    if (diffMins < 60) return `${diffMins} minute${diffMins === 1 ? '' : 's'} ago`;
                    const hours = Math.floor(diffMins / 60);
                    const mins = diffMins % 60;
                    if (hours < 24) {
                        if (mins === 0) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
                        return `${hours}h ${mins}m ago`;
                    }
                    return new Date(isoDate).toLocaleString();
                },

                formatTime(isoDate) {
                    if (!isoDate) return '';
                    return new Date(isoDate).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                },

                // =============================================
                // Config Override Methods
                // =============================================

                async loadConfig() {
                    try {
                        const res = await fetch('/api/config');
                        const data = await res.json();
                        this.configs = data.configs || {};

                        // Update local values from configs
                        if (this.configs.ELITE_ZOMBIE_STAMINA_THRESHOLD) {
                            this.staminaThreshold = this.configs.ELITE_ZOMBIE_STAMINA_THRESHOLD.value;
                        }
                        if (this.configs.ELITE_ZOMBIE_TARGET_LEVEL) {
                            this.targetLevel = this.configs.ELITE_ZOMBIE_TARGET_LEVEL.value;
                        }

                        // Build active overrides list
                        this.activeOverrides = {};
                        for (const [key, cfg] of Object.entries(this.configs)) {
                            if (cfg.overridden) {
                                this.activeOverrides[key] = cfg;
                            }
                        }
                        await this.loadRallyMonsters();
                    } catch (e) {
                        console.error('Config load failed:', e);
                    }
                },

                async loadRallyMonsters() {
                    try {
                        const res = await fetch('/api/rally/monsters');
                        const data = await res.json();
                        this.rallyMonsters = data.monsters || [];
                    } catch (e) {
                        console.error('Rally monsters load failed:', e);
                    }
                },

                async markOverlordDone() {
                    try {
                        const res = await fetch('/api/ws/command', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ cmd: 'mark_overlord_done', args: {} })
                        });
                        const data = await res.json();
                        if (data.success === false || data.error) {
                            this.showToast(`Failed: ${data.error || 'unknown error'}`, 'error');
                            return;
                        }
                        this.status.overlord_first_kill_done = true;
                        this.showToast('Overlord gate marked done for this reset - all overlords joinable', 'success');
                    } catch (e) {
                        this.showToast(`Failed to mark overlord done: ${e}`, 'error');
                    }
                },

                async setRallyMonsterIgnoreOverride(monster, value, durationMinutes) {
                    const key = monster?.ignore_override_key;
                    if (!key) return;

                    try {
                        const res = await fetch(`/api/config/${key}/override`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ value, duration_minutes: durationMinutes })
                        });
                        const data = await res.json();
                        if (data.success) {
                            const label = value ? 'Ignore limit' : 'Respect limit';
                            this.showToast(`${monster.name}: ${label}`, 'success');
                            await Promise.all([this.loadConfig(), this.loadRallyMonsters()]);
                        } else {
                            this.showToast(`Failed: ${data.error || 'Unknown error'}`, 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async toggleConfigOverride(key) {
                    const cfg = this.configs[key];
                    if (!cfg) return;

                    const newValue = !cfg.value;
                    const durationVal = this.overrideDurations?.[key];
                    const duration = durationVal ? parseInt(durationVal) : null;

                    try {
                        const res = await fetch(`/api/config/${key}/override`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ value: newValue, duration_minutes: duration })
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`${this.formatConfigName(key)}: ${this.formatBoolValueLabel(key, newValue)}`, 'success');
                            await this.loadConfig();
                        } else {
                            this.showToast(`Failed: ${data.error || 'Unknown error'}`, 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async setBoolOverride(key, value, durationMinutes) {
                    try {
                        const res = await fetch(`/api/config/${key}/override`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ value, duration_minutes: durationMinutes })
                        });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`${this.formatConfigName(key)}: ${this.formatBoolValueLabel(key, value)}`, 'success');
                            await this.loadConfig();
                        } else {
                            this.showToast(`Failed: ${data.error || 'Unknown error'}`, 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async applyStaminaOverrides() {
                    const thresholdDurationVal = this.overrideDurations?.['ELITE_ZOMBIE_STAMINA_THRESHOLD'];
                    const targetDurationVal = this.overrideDurations?.['ELITE_ZOMBIE_TARGET_LEVEL'];
                    const thresholdDuration = thresholdDurationVal ? parseInt(thresholdDurationVal) : null;
                    const targetDuration = targetDurationVal ? parseInt(targetDurationVal) : null;

                    try {
                        // Apply threshold override
                        if (this.staminaThreshold !== 118) {
                            await fetch('/api/config/ELITE_ZOMBIE_STAMINA_THRESHOLD/override', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: this.staminaThreshold, duration_minutes: thresholdDuration })
                            });
                        }

                        // Apply target level override
                        if (this.targetLevel !== 30) {
                            await fetch('/api/config/ELITE_ZOMBIE_TARGET_LEVEL/override', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: this.targetLevel, duration_minutes: targetDuration })
                            });
                        }

                        this.showToast('Stamina overrides applied', 'success');
                        await this.loadConfig();
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                async clearOverride(key) {
                    try {
                        const res = await fetch(`/api/config/${key}/override`, { method: 'DELETE' });
                        const data = await res.json();
                        if (data.success) {
                            this.showToast(`Cleared ${this.formatConfigName(key)}`, 'info');
                            await this.loadConfig();
                        } else {
                            this.showToast(`Failed: ${data.error || 'Unknown error'}`, 'error');
                        }
                    } catch (e) {
                        this.showToast(`Error: ${e.message}`, 'error');
                    }
                },

                formatOverrideTime(seconds) {
                    if (!seconds) return 'Permanent';
                    if (seconds < 60) return `${seconds}s`;
                    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
                    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
                    return `${Math.floor(seconds / 86400)}d`;
                },

                formatConfigName(key) {
                    const customNames = {
                        BARRACKS_CLAIM_ENABLED: 'Barracks Auto-Claim',
                        HOSPITAL_SOLDIER_CLAIM_ENABLED: 'Hospital Soldier Auto-Claim',
                        HOSPITAL_HEAL_ENABLED: 'Hospital Auto-Heal',
                    };
                    if (customNames[key]) return customNames[key];
                    let name = key.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
                    name = name.replace(/\s+Enabled$/i, '');
                    return name;
                },

                rallyIgnoreValueLabel(value) {
                    return value ? 'Ignore limit' : 'Respect limit';
                },

                monsterDailyLimitSummary(monster) {
                    const mode = monster?.ignore_daily_limit?.overridden
                        ? `Override: ${this.rallyIgnoreValueLabel(monster.ignore_daily_limit?.value)}`
                        : `Default: ${this.rallyIgnoreValueLabel(monster?.ignore_daily_limit?.default)}`;
                    if (!monster?.track_daily_limit) {
                        return `No local exhaustion tracking | ${mode}`;
                    }
                    return mode;
                },

                getEffectiveIgnoreLimit(monster) {
                    // Returns the EFFECTIVE ignore limit value for this monster
                    // Priority: per-monster override > global default
                    if (monster?.ignore_daily_limit?.overridden) {
                        // Per-monster override is SET - use it
                        return monster.ignore_daily_limit.value;
                    }
                    // No override - use global default
                    return this.configs?.RALLY_IGNORE_DAILY_LIMIT?.value ?? false;
                },

                isClaimToggleKey(key) {
                    return ['BARRACKS_CLAIM_ENABLED', 'HOSPITAL_SOLDIER_CLAIM_ENABLED'].includes(key);
                },

                toggleOverlayLabel(key) {
                    return this.isClaimToggleKey(key) ? 'DISABLE TIMERS' : 'OFF TIMERS';
                },

                toggleOffLabel(key) {
                    return this.isClaimToggleKey(key) ? 'DISABLE' : 'OFF';
                },

                toggleOnLabel(key) {
                    return this.isClaimToggleKey(key) ? 'ENABLE' : 'ON';
                },

                formatBoolValueLabel(key, value) {
                    if (key === 'RALLY_IGNORE_DAILY_LIMIT') return this.rallyIgnoreValueLabel(value);
                    if (this.isClaimToggleKey(key)) return value ? 'ENABLED' : 'DISABLED';
                    return value ? 'ON' : 'OFF';
                },

                formatConfigStatus(key, cfg) {
                    if (cfg.overridden) return `OVERRIDE ${this.formatOverrideTime(cfg.expires_in)}`;
                    return `Default: ${this.formatBoolValueLabel(key, cfg.default)}`;
                },

                claimToggleHint(key, value) {
                    if (key === 'BARRACKS_CLAIM_ENABLED') {
                        return value ? 'Enabled: daemon taps READY barracks to claim soldiers' : 'Disabled: daemon will not claim READY barracks';
                    }
                    if (key === 'HOSPITAL_SOLDIER_CLAIM_ENABLED') {
                        return value ? 'Enabled: daemon taps Claim in hospital' : 'Disabled: daemon leaves healed soldiers in hospital';
                    }
                    return '';
                },

                // =============================================
                // Daily Check-in Methods
                // =============================================

                getNextResetTime() {
                    // Server resets at 02:00 UTC
                    const now = new Date();
                    const resetHour = 2;
                    let reset = new Date(Date.UTC(
                        now.getUTCFullYear(),
                        now.getUTCMonth(),
                        now.getUTCDate(),
                        resetHour, 0, 0
                    ));
                    // If we're past today's reset, next reset is tomorrow
                    if (now >= reset) {
                        reset.setUTCDate(reset.getUTCDate() + 1);
                    }
                    return reset;
                },

                formatResetCountdown() {
                    const reset = this.getNextResetTime();
                    const diff = reset - new Date();
                    const hours = Math.floor(diff / 3600000);
                    const mins = Math.floor((diff % 3600000) / 60000);
                    return `${hours}h ${mins}m`;
                },
            };
        }