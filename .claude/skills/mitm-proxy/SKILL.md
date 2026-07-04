# MITM Proxy + Frida SSL Bypass Skill

**Purpose**: Intercept HTTPS traffic from BlueStacks apps to see hidden URLs.

**Status**: ✅ Fully configured - Root enabled, CA cert installed, Frida ready

---

## EASIEST METHOD: Check Logcat

The game logs URLs to logcat! No MITM/Frida needed for most cases:

```bash
# Click the button in game, then immediately run:
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 logcat -d | grep -iE "openWebView|loadUrl|url.*http"
```

**Example output:**
```
I [Q1_JS_BRIDGE]: openWebView 的 url = https://club-en.q1.com/?type=1&platform=1&...
```

---

## TL;DR - Full Intercept (Game Starts Successfully with Proxy!)

**Key flags**:
- `--no-http2`: Game servers return malformed HTTP/2 headers → forces HTTP/1.1
- `--ignore-hosts`: Bypass Google/Facebook auth → game can login

```bash
# 1. Start mitmproxy with selective bypass (run in separate terminal)
mitmdump -p 8888 --no-http2 --ignore-hosts '.*google.*|.*googleapis.*|.*gstatic.*|.*facebook.*|.*fbcdn.*|.*firebase.*|.*cloudflare.*|.*bluestacks.*' -s "C:/Users/mail/xclash/scripts/one_off/mitm_logger.py"

# 2. Set BlueStacks proxy
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy 10.0.2.2:8888"

# 3. Start frida-server as root
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c 'killall frida-server 2>/dev/null; /data/local/tmp/frida-server &'"

# 4a. SPAWN MODE (recommended): Start game fresh with SSL bypass
frida -U -f com.xman.na.gp -l "C:/Users/mail/xclash/scripts/one_off/ssl_bypass.js"

# 4b. OR ATTACH MODE: If game already running
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "ps -A | grep xman"
frida -U -p <PID> -l "C:/Users/mail/xclash/scripts/one_off/ssl_bypass.js"
```

Then click whatever you want to capture. View with:
```bash
python -c "import json; [print(e['url']) for e in json.load(open('C:/Users/mail/xclash/data/mitm_flows.json', encoding='utf-8'))[-20:] if 'localhost' not in e.get('host','')]"
```

**Note**: Log is rolling (keeps last 5000 requests) - won't eat disk space.

---

## Stop Intercept (IMPORTANT - or network breaks!)

```bash
# Remove proxy
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy :0"

# Kill processes
taskkill /F /IM mitmdump.exe
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c 'killall frida-server'"
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ BlueStacks  │────▶│ MITM Proxy   │────▶│  Internet    │
│ (Game App)  │     │ (port 8888)  │     │              │
└─────────────┘     └──────────────┘     └──────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌──────────────┐
│   Frida     │     │ mitm_flows   │
│ SSL Bypass  │     │    .json     │
└─────────────┘     └──────────────┘
```

**Why both?**
- MITM Proxy: Intercepts traffic, logs URLs
- Frida: Makes game trust MITM's fake certificate (bypasses SSL pinning)

Without Frida, game rejects MITM's cert → HTTPS fails → no traffic captured.

---

## Detailed Steps

### Step 1: Start MITM Proxy

```bash
# Kill any existing
taskkill /F /IM mitmdump.exe 2>/dev/null

# Start with selective bypass (REQUIRED for game to login!)
mitmdump -p 8888 --no-http2 --ignore-hosts '.*google.*|.*googleapis.*|.*gstatic.*|.*facebook.*|.*fbcdn.*|.*firebase.*|.*cloudflare.*|.*bluestacks.*' -s "C:/Users/mail/xclash/scripts/one_off/mitm_logger.py"

# Verify running
netstat -an | findstr 8888
# Should show: TCP 0.0.0.0:8888 LISTENING
```

**Key flags**:
- `--no-http2`: Game servers (q1.com) return malformed HTTP/2 headers
- `--ignore-hosts`: Bypass Google/Facebook so game can authenticate

### Step 2: Configure BlueStacks Proxy

```bash
# Set proxy (10.0.2.2 = host machine from Android's perspective)
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy 10.0.2.2:8888"

# Verify
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings get global http_proxy"
# Should show: 10.0.2.2:8888
```

### Step 3: Start Frida Server (as root)

```bash
# Start frida-server as root
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c 'killall frida-server 2>/dev/null; /data/local/tmp/frida-server &'"

# Verify running
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "ps -A | grep frida"
# Should show: root ... frida-server
```

### Step 4: Attach Frida SSL Bypass to Game

```bash
# Get game PID
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "ps -A | grep xman"
# Output: u0_a64 <PID> ... com.xman.na.gp

# Attach with SSL bypass script
frida -U -p <PID> -l "C:/Users/mail/xclash/scripts/one_off/ssl_bypass.js"

# Should output:
# [*] SSL Bypass script loaded
# [*] TrustManagerImpl bypass installed
# [*] SSLContext bypass installed
# ... etc
```

### Step 5: Clear Log and Capture

```bash
# Clear old captures
echo "[]" > "C:/Users/mail/xclash/data/mitm_flows.json"

# Now click whatever you want to capture in the game
# Then check the log:
python -c "
import json
d = json.load(open('C:/Users/mail/xclash/data/mitm_flows.json', encoding='utf-8'))
for e in d[-30:]:
    if 'localhost' not in e.get('host', ''):
        print(f\"{e.get('status')}: {e.get('url', '')[:120]}\")
"
```

---

## One-Time Setup (Already Done)

### BlueStacks Root Access ✅

Config: `C:\ProgramData\BlueStacks_nxt\bluestacks.conf`
```
bst.feature.rooting="1"
bst.instance.Pie64.enable_root_access="1"
```
**File is READ-ONLY** to prevent BlueStacks from overwriting.

To verify root works:
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c id"
# Should show: uid=0(root)
```

To remove read-only (if needed):
```bash
attrib -R "C:/ProgramData/BlueStacks_nxt/bluestacks.conf"
```

### MITM CA Certificate ✅

Installed in BlueStacks. Certificate files: `C:\Users\mail\.mitmproxy\`

To reinstall if needed:
1. Set temporary PIN: Settings → Security → Screen lock → PIN (1234)
2. Chrome → `http://mitm.it` → Android → Download
3. Settings → Security → Install from storage → Select cert
4. Remove PIN: `adb shell locksettings clear --old 1234`

### Frida Server ✅

Binary: `C:\Users\mail\xclash\data\frida-server` (110MB, x86_64)
Location on device: `/data/local/tmp/frida-server`

To reinstall if needed:
```bash
# Copy to BlueStacks shared folder
cp "C:/Users/mail/xclash/data/frida-server" "C:/ProgramData/BlueStacks_nxt/Engine/UserData/SharedFolder/"

# From BlueStacks, copy to /data/local/tmp
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "cp /mnt/windows/BstSharedFolder/frida-server /data/local/tmp/ && chmod 755 /data/local/tmp/frida-server"
```

### SSL Bypass Script ✅

Location: `C:\Users\mail\xclash\scripts\one_off\ssl_bypass.js`

Hooks (all installed):
- TrustManagerImpl.verifyChain
- **ConscryptFileDescriptorSocket.verifyCertificateChain** (critical!)
- ConscryptEngineSocket.verifyCertificateChain
- X509TrustManager (custom impl)
- SSLContext.init
- OkHttp3 CertificatePinner
- OkHttp3 CertificatePinner.Builder
- **Q1 SDK OkHttp3 CertificatePinner** (com.q1.common.lib.okhttp3)
- HttpsURLConnection
- HostnameVerifier

---

## Files Reference

| File | Purpose |
|------|---------|
| `scripts/one_off/mitm_logger.py` | MITM addon - logs HTTP flows to JSON |
| `scripts/one_off/mitm_ws_logger.py` | MITM addon - logs HTTP + WebSocket |
| `scripts/one_off/ssl_bypass.js` | Frida script - bypasses SSL pinning |
| `data/mitm_flows.json` | Captured traffic log |
| `data/frida-server` | Frida server binary (x86_64) |

## Key Values

| Setting | Value |
|---------|-------|
| MITM Proxy port | `8888` |
| BlueStacks host alias | `10.0.2.2` |
| Frida server path | `/data/local/tmp/frida-server` |
| Game package | `com.xman.na.gp` |
| BlueStacks shared folder (Windows) | `C:\ProgramData\BlueStacks_nxt\Engine\UserData\SharedFolder\` |
| BlueStacks shared folder (Android) | `/mnt/windows/BstSharedFolder/` |
| BlueStacks config | `C:\ProgramData\BlueStacks_nxt\bluestacks.conf` |

---

## Troubleshooting

### "No network" in BlueStacks
Proxy set but MITM not running:
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy :0"
```

### Frida can't attach / permission denied
frida-server not running as root:
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c '/data/local/tmp/frida-server &'"
```

### HTTPS traffic not captured (TLS errors in proxy log)
Frida SSL bypass not attached:
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "ps -A | grep xman"
frida -U -p <PID> -l "C:/Users/mail/xclash/scripts/one_off/ssl_bypass.js"
```

### Root not working after BlueStacks restart
Config was overwritten. Re-enable:
```bash
# Close BlueStacks first!
attrib -R "C:/ProgramData/BlueStacks_nxt/bluestacks.conf"
# Edit file: set rooting="1" and enable_root_access="1"
attrib +R "C:/ProgramData/BlueStacks_nxt/bluestacks.conf"
```

### frida-ps hangs
Normal - just use direct PID attachment instead of listing processes.
