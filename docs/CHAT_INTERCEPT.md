# Chat Message Interception

## Status: ✅ WORKING (tested 2026-02-06)

## Goal
Intercept game chat messages via MITM proxy to:
1. See treasure dig coordinates before character arrives
2. Summarize chat hourly and post to web interface
3. Potentially automate responses

## Architecture

```
BlueStacks Game → MITM Proxy (8888) → Internet
       ↓               ↓
   Frida SSL      mitm_flows.json
    Bypass         (captures)
```

Chat messages go through `translate.q1.com/api/livedata/translate`

## Setup Commands (SPAWN MODE - Recommended)

```bash
# 1. Force stop game first
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "am force-stop com.xman.na.gp"

# 2. Start MITM proxy (in separate terminal)
mitmdump -p 8888 --no-http2 --ignore-hosts ".*google.*|.*googleapis.*|.*gstatic.*|.*facebook.*|.*fbcdn.*|.*firebase.*|.*cloudflare.*|.*bluestacks.*" -s "C:/Users/mail/xclash/scripts/one_off/mitm_logger.py"

# 3. Set BlueStacks proxy
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy 10.0.2.2:8888"

# 4. Start Frida server (as root)
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "su -c 'killall frida-server 2>/dev/null; /data/local/tmp/frida-server &'"

# 5. SPAWN game with SSL bypass (starts game automatically)
frida -U -f com.xman.na.gp -l "C:/Users/mail/xclash/scripts/one_off/ssl_bypass.js"
```

## Stop Interception (IMPORTANT!)

```bash
# Remove proxy (or network breaks!)
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" -s emulator-5554 shell "settings put global http_proxy :0"

# Kill processes
python -c "import os; os.system('taskkill /F /IM mitmdump.exe')"
python -c "import os; os.system('taskkill /F /IM frida.exe')"
```

## Chat Message Format

Chat messages go through translation API at `translate.q1.com`:

```json
{
  "url": "https://translate.q1.com/api/livedata/translate",
  "request_body": {
    "q": "The actual message text",
    "source": "en",
    "textType": "chat",
    "userId": "500285023",
    "actorId": "5179912",
    "msgId": "unique-message-id"
  },
  "response_preview": {
    "code": 1,
    "message": "翻译成功",
    "data": "Translated message text"
  }
}
```

## Key Fields
- `q` - Original message text
- `userId` / `actorId` - Sender identifiers
- `msgId` - Unique message ID
- `textType` - "chat" for chat messages

## Viewing Captured Messages

```bash
python -c "
import json
d = json.load(open('C:/Users/mail/xclash/data/mitm_flows.json', encoding='utf-8'))
for e in d:
    if 'translate' in e.get('url', '').lower():
        req = e.get('request_body', '')
        if req:
            import json as j
            try:
                body = j.loads(req)
                print(f\"Message: {body.get('q')}\")
            except: pass
"
```

## Future Work
1. Create daemon integration to read chat in real-time
2. Detect treasure dig coordinates from chat links
3. Hourly chat summary to web dashboard
4. Auto-respond to specific messages
