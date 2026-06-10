"""Log all mitmproxy flows to a JSON file with rolling limit."""
import json
import os
from mitmproxy import http

OUTPUT_FILE = "C:/Users/mail/xclash/data/mitm_flows.json"
MAX_FLOWS = 5000  # Keep last 5000 requests (rolling log)
flows = []

def response(flow: http.HTTPFlow) -> None:
    """Log every response."""
    entry = {
        "url": flow.request.pretty_url,
        "method": flow.request.method,
        "host": flow.request.host,
        "path": flow.request.path,
        "status": flow.response.status_code if flow.response else None,
        "error": str(flow.error) if flow.error else None,
    }

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

    # Rolling limit - keep only last MAX_FLOWS
    if len(flows) > MAX_FLOWS:
        flows.pop(0)

    # Write to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)

def error(flow: http.HTTPFlow) -> None:
    """Log errors too."""
    entry = {
        "url": flow.request.pretty_url,
        "method": flow.request.method,
        "host": flow.request.host,
        "path": flow.request.path,
        "status": None,
        "error": str(flow.error) if flow.error else "unknown error",
    }
    flows.append(entry)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(flows, f, indent=2, ensure_ascii=False)
