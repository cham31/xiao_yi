"""
大模型 API 配置与连通性测试。

配置文件保存在用户目录，不进入仓库，避免泄露 API Key。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass
class AiApiConfig:
    provider: str = "deepseek"
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    extra_headers: dict[str, str] = field(default_factory=dict)

    def normalized_base_url(self) -> str:
        return self.base_url.strip().rstrip("/")

    def chat_completions_url(self) -> str:
        return f"{self.normalized_base_url()}/chat/completions"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.provider.strip():
            errors.append("提供商不能为空")
        if not self.normalized_base_url():
            errors.append("Base URL 不能为空")
        if not self.api_key.strip():
            errors.append("API Key 不能为空")
        if not self.model.strip():
            errors.append("模型名称不能为空")
        if self.timeout_seconds < 5:
            errors.append("超时时间不能小于 5 秒")
        return errors


def config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "XiaoYi" / "ai_config.json"
    return Path.home() / ".xiaoyi" / "ai_config.json"


def load_ai_config() -> AiApiConfig:
    path = config_path()
    if not path.is_file():
        env_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        return AiApiConfig(api_key=env_key)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AiApiConfig()

    cfg = AiApiConfig()
    for key in asdict(cfg):
        if key in data:
            setattr(cfg, key, data[key])
    if not isinstance(cfg.extra_headers, dict):
        cfg.extra_headers = {}
    return cfg


def save_ai_config(config: AiApiConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def masked_key(api_key: str) -> str:
    key = api_key.strip()
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:6]}...{key[-4:]}"


def test_ai_config(config: AiApiConfig) -> tuple[bool, str]:
    errors = config.validate()
    if errors:
        return False, "\n".join(errors)

    payload = {
        "model": config.model.strip(),
        "messages": [
            {"role": "system", "content": "You are a concise API connectivity tester."},
            {"role": "user", "content": "Reply with OK."},
        ],
        "max_tokens": 8,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
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

    usage = data.get("usage") or {}
    usage_text = ""
    if usage:
        usage_text = f"\nusage: {usage}"
    return True, f"连接成功，模型 {config.model} 可用。{usage_text}"
