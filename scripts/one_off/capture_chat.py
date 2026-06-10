"""
Capture game chat traffic to find the tavern quest link format.
Run this, then configure BlueStacks to use proxy 127.0.0.1:8080
"""
import os
import json
import re
from datetime import datetime
from mitmproxy import http, ctx

# Output file for captured data
OUTPUT_FILE = "C:/Users/mail/xclash/data/chat_capture.json"
captured = []

def response(flow: http.HTTPFlow) -> None:
    """Capture responses that might contain chat data."""

    # Log all requests for debugging
    url = flow.request.pretty_url

    # Look for chat-related endpoints
    keywords = ['chat', 'message', 'msg', 'send', 'tavern', 'quest', 'share', 'link']

    is_interesting = any(kw in url.lower() for kw in keywords)

    # Also capture if response contains these patterns
    content = ""
    if flow.response and flow.response.content:
        try:
            content = flow.response.content.decode('utf-8', errors='replace')
            if any(kw in content.lower() for kw in ['tavern', 'quest', '<link', 'BChubb', 'ToT']):
                is_interesting = True
        except Exception:
            pass

    if is_interesting or 'xman' in url.lower() or 'q1.com' in url.lower():
        entry = {
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "method": flow.request.method,
            "request_headers": dict(flow.request.headers),
            "response_status": flow.response.status_code if flow.response else None,
            "response_headers": dict(flow.response.headers) if flow.response else None,
            "response_content_preview": content[:2000] if content else None,
        }

        # Try to decode request body
        if flow.request.content:
            try:
                req_body = flow.request.content.decode('utf-8', errors='replace')
                entry["request_body"] = req_body[:2000]
            except Exception:
                entry["request_body"] = str(flow.request.content[:500])

        captured.append(entry)

        # Save to file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(captured, f, indent=2, ensure_ascii=False)

        ctx.log.info(f"Captured: {url[:100]}")

def done():
    """Called when mitmproxy shuts down."""
    print(f"\nCaptured {len(captured)} requests")
    print(f"Saved to: {OUTPUT_FILE}")
