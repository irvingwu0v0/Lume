"""Shared helpers for talking to OpenAI-compatible chat completion APIs.

Both the single-shot streaming worker (`SseWorker`) and the two-pass
batch/split worker use the helpers here, so SSE parsing and request
construction live in exactly one place.
"""

import json


def extract_json(text):
    """Robustly extract a JSON object from AI-generated text.

    Tries, in order: direct parse, the last complete ```json fence,
    string-aware balanced-brace scanning, and auto-closing a truncated
    object. Returns ``(dict, None)`` on success or ``(None, reason)``.
    """
    if not text or not text.strip():
        return None, "empty content"
    t = text.strip()

    # 1) Direct parse
    try:
        result = json.loads(t)
        if isinstance(result, dict):
            return result, None
    except Exception:
        pass

    # 2) Search for JSON fences — prefer the LAST complete code block
    fences = ["```json\n", "```json", "```JSON\n", "```JSON", "```"]
    best = None
    for fence in fences:
        pos = 0
        while True:
            fence_start = t.find(fence, pos)
            if fence_start == -1:
                break
            inner_start = fence_start + len(fence)
            inner = t[inner_start:]
            fence_end = inner.find("```")
            if fence_end == -1:
                fence_end = len(inner)
            inner = inner[:fence_end].strip()
            if inner:
                try:
                    result = json.loads(inner)
                    if isinstance(result, dict):
                        best = result
                except Exception:
                    pass
            pos = inner_start + fence_end + 3

    if best is not None:
        return best, None

    # 3) String-aware balanced brace extraction
    start_pos = t.find("{")
    if start_pos == -1:
        return None, "no JSON object found"

    stack = []
    in_string = False
    escape_next = False
    i = start_pos
    while i < len(t):
        ch = t[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            escape_next = True
            i += 1
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue
        if ch == '{':
            stack.append('{')
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
                if not stack:
                    candidate = t[start_pos:i + 1]
                    try:
                        return json.loads(candidate), None
                    except Exception:
                        pass
        elif ch == '[':
            stack.append('[')
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()
        i += 1

    # 4) Auto-close truncated JSON
    if stack and len(stack) <= 50:
        suffix = ""
        if in_string:
            suffix += '"'
        for opener in reversed(stack):
            suffix += '}' if opener == '{' else ']'
        candidate = t[start_pos:] + suffix
        try:
            return json.loads(candidate), None
        except Exception:
            pass

    return None, "could not extract valid JSON"


def build_chat_request(model, messages, thinking_enabled=False, temperature=None):
    """Build ``(url, payload, headers)`` for an OpenAI-compatible chat call."""
    base_url = model["base_url"].rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model["model_name"],
        "messages": messages,
        "stream": True,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model['api_key']}",
    }
    return url, payload, headers


def iter_sse_deltas(chunks, should_abort=lambda: False):
    """Yield ``(reasoning, content)`` deltas from an SSE byte iterator.

    Buffers partial lines so a JSON event split across chunks is decoded
    correctly. Stops at ``[DONE]`` or when ``should_abort()`` becomes true.
    """
    buf = ""
    for chunk in chunks:
        if should_abort():
            return
        if not chunk:
            continue
        buf += chunk.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                return
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            yield delta.get("reasoning_content", ""), delta.get("content", "")


def image_content(images_b64, note):
    """Build an OpenAI vision content array from base64 JPEG strings."""
    content = [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        for b64 in images_b64
    ]
    content.append({"type": "text", "text": note})
    return content
