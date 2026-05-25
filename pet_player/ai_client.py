"""
OpenAI-compatible chat client used by XiaoYi.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from pet_player.ai_config import AiApiConfig


DEFAULT_SYSTEM_PROMPT = (
    "你是小艺，一个温柔、简洁、带一点活泼感的桌面宠物助手。"
    "你正在通过桌面宠物聊天窗口和用户对话。"
    "回答要自然、直接，默认使用中文；不知道就坦诚说明。"
)


def request_chat_completion(
    config: AiApiConfig,
    messages: list[dict[str, str]],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> tuple[bool, str]:
    """Send one non-streaming chat request and return (ok, text)."""
    errors = config.validate()
    if errors:
        return False, "\n".join(errors)

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)
    payload = {
        "model": config.model.strip(),
        "messages": api_messages,
        "temperature": 0.7,
        "max_tokens": 1024,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {config.api_key.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update({k: v for k, v in config.extra_headers.items() if k and v})

    request = urllib.request.Request(
        config.chat_completions_url(),
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        return False, f"HTTP {exc.code}: {detail or exc.reason}"
    except urllib.error.URLError as exc:
        return False, f"网络错误: {exc.reason}"
    except TimeoutError:
        return False, "请求超时"
    except OSError as exc:
        return False, f"请求失败: {exc}"

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, f"接口返回的不是 JSON: {raw[:300]}"

    choices = data.get("choices") or []
    if not choices:
        return False, f"接口已响应，但没有返回 choices: {raw[:500]}"

    message = choices[0].get("message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        return False, f"接口返回为空: {raw[:500]}"
    return True, content
