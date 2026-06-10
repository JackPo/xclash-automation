"""Log all mitmproxy flows including WebSocket traffic to a JSON file."""
import base64
import json
import os
from mitmproxy import http, websocket

OUTPUT_FILE = "C:/Users/mail/xclash/data/mitm_flows.json"
MAX_FLOWS = 5000  # Keep last 5000 requests (rolling log)
MAX_BINARY_BYTES = 20000  # Cap binary payloads to avoid huge logs
flows = []

def response(flow: http.HTTPFlow) -> None:
    """Log every HTTP response."""
    entry = {
        "type": "http",
        "url": flow.request.pretty_url,
        "method": flow.request.method,
        "host": flow.request.host,
        "path": flow.request.path,
        "status": flow.response.status_code if flow.response else None,
        "error": str(flow.error) if flow.error else None,
    }

    # Check for WebSocket upgrade
    if flow.response and flow.response.headers.get("Upgrade", "").lower() == "websocket":
        entry["websocket_upgrade"] = True

    # Try to get response content for interesting requests
    if flow.response and flow.response.content:
        try:
            content = flow.response.content.decode('utf-8', errors='replace')[:2000]
            entry["response_preview"] = content
        except Exception:
            pass

    # Try to get request body
    if flow.request.content:
        try:
            req_body = flow.request.content.decode('utf-8', errors='replace')[:2000]
            entry["request_body"] = req_body
        except Exception:
            pass

    flows.append(entry)
    _write_flows()

def websocket_message(flow: http.HTTPFlow) -> None:
    """Log WebSocket messages."""
    assert flow.websocket is not None

    for message in flow.websocket.messages:
        if not hasattr(message, '_logged'):
            entry = {
                "type": "websocket",
                "url": flow.request.pretty_url,
                "host": flow.request.host,
                "direction": "client->server" if message.from_client else "server->client",
                "is_text": message.is_text,
                "timestamp": message.timestamp,
                "byte_len": len(message.content) if message.content else 0,
            }

            # Try to decode the content
            try:
                if message.is_text:
                    content = message.text[:5000] if len(message.text) > 5000 else message.text
                    entry["content"] = content
                else:
                    raw = message.content or b""
                    if len(raw) > MAX_BINARY_BYTES:
                        raw = raw[:MAX_BINARY_BYTES]
                    entry["content_b64"] = base64.b64encode(raw).decode('ascii')
                    # Also include a small hex preview and utf-8 fallback
                    try:
                        entry["content_utf8"] = raw.decode('utf-8', errors='replace')[:2000]
                    except Exception:
                        pass
                    entry["content_hex"] = raw[:500].hex()
            except Exception as e:
                entry["content_error"] = str(e)

            flows.append(entry)
            message._logged = True

    _write_flows()

def error(flow: http.HTTPFlow) -> None:
    """Log errors too."""
    entry = {
        "type": "http_error",
        "url": flow.request.pretty_url,
        "method": flow.request.method,
        "host": flow.request.host,
        "path": flow.request.path,
        "status": None,
        "error": str(flow.error) if flow.error else "unknown error",
    }
    flows.append(entry)
    _write_flows()

def _write_flows():
    """Write flows to file with rolling limit."""
    global flows
    # Rolling limit - keep only last MAX_FLOWS
    if len(flows) > MAX_FLOWS:
        flows = flows[-MAX_FLOWS:]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(flows, f, indent=2, ensure_ascii=False, default=str)
