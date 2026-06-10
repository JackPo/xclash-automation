import argparse
import base64
import json
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_INPUT = r"C:\\Users\\mail\\xclash\\data\\mitm_flows.json"
DEFAULT_OUTPUT = r"C:\\Users\\mail\\xclash\\data\\chat_messages.jsonl"

PRINTABLE_RE = re.compile(r"[\x20-\x7E]{4,}")


def _extract_from_json(obj: Any) -> List[Dict[str, Any]]:
    """Try to pull chat-like fields from a JSON object."""
    msgs = []
    if isinstance(obj, dict):
        # Common keys
        text = None
        for key in ("content", "message", "msg", "chat", "q", "text"):
            if key in obj and isinstance(obj[key], str):
                text = obj[key]
                break
        if text:
            msgs.append({
                "content": text,
                "sender": obj.get("senderName") or obj.get("sender") or obj.get("from") or obj.get("roleName"),
                "channel": obj.get("channel") or obj.get("chatType") or obj.get("chat_channel"),
                "worldid": obj.get("worldid") or obj.get("worldId"),
                "chat_id": obj.get("chatID") or obj.get("szChatID") or obj.get("msgId"),
                "raw": obj,
            })
        # Recurse into values
        for v in obj.values():
            msgs.extend(_extract_from_json(v))
    elif isinstance(obj, list):
        for item in obj:
            msgs.extend(_extract_from_json(item))
    return msgs


def _extract_printable(raw: bytes) -> List[str]:
    try:
        s = raw.decode("utf-8", errors="replace")
    except Exception:
        return []
    return [m.group(0) for m in PRINTABLE_RE.finditer(s)]


def parse_ws_entries(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in entries:
        if e.get("type") != "websocket":
            continue
        ts = e.get("timestamp")
        direction = e.get("direction")
        host = e.get("host")
        url = e.get("url")

        if e.get("is_text") and e.get("content"):
            content = e.get("content")
            # Try JSON
            try:
                obj = json.loads(content)
                msgs = _extract_from_json(obj)
                for m in msgs:
                    out.append({
                        **m,
                        "timestamp": ts,
                        "direction": direction,
                        "host": host,
                        "url": url,
                    })
                if not msgs:
                    out.append({
                        "content": content,
                        "timestamp": ts,
                        "direction": direction,
                        "host": host,
                        "url": url,
                    })
            except Exception:
                out.append({
                    "content": content,
                    "timestamp": ts,
                    "direction": direction,
                    "host": host,
                    "url": url,
                })
            continue

        # Binary payloads
        b64 = e.get("content_b64")
        if b64:
            try:
                raw = base64.b64decode(b64)
            except Exception:
                raw = b""
            # Heuristic: extract printable substrings
            printable = _extract_printable(raw)
            for text in printable:
                out.append({
                    "content": text,
                    "timestamp": ts,
                    "direction": direction,
                    "host": host,
                    "url": url,
                    "note": "binary_utf8_substring",
                })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    msgs = parse_ws_entries(data)

    with open(args.output, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"parsed {len(msgs)} potential chat messages -> {args.output}")


if __name__ == "__main__":
    main()
