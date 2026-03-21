"""
CECLAW Router - Configuration Loader
優先順序: 預設值 → ceclaw.yaml → 環境變數 → CLI 參數
"""
import os
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


DEFAULT_CONFIG_PATH = Path.home() / ".ceclaw" / "ceclaw.yaml"
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 8000
DEFAULT_STRATEGY = "local-first"
DEFAULT_TIMEOUT_LOCAL_MS = 30000

CLOUD_BASE_URLS = {
    "groq":      "https://api.groq.com/openai/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "openai":    "https://api.openai.com/v1",
    "nvidia":    "https://integrate.api.nvidia.com/v1",
}


class ModelDef(BaseModel):
    id: str
    alias: Optional[str] = None
    context_window: int = 32768


class LocalBackend(BaseModel):
    name: str
    type: str                          # llama.cpp | vllm | ollama | sglang
    base_url: str
    models: list[ModelDef] = Field(default_factory=list)


class CloudProvider(BaseModel):
    provider: str                      # groq | anthropic | openai | nvidia
    env_key: str
    base_url: Optional[str] = None
    models: list[str] = Field(default_factory=list)

    def resolved_base_url(self) -> str:
        return self.base_url or CLOUD_BASE_URLS.get(self.provider, "")

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.env_key)


class CloudFallback(BaseModel):
    enabled: bool = True
    priority: list[CloudProvider] = Field(default_factory=list)


class LocalInference(BaseModel):
    backends: list[LocalBackend] = Field(default_factory=list)


class InferenceConfig(BaseModel):
    strategy: str = DEFAULT_STRATEGY
    timeout_local_ms: int = DEFAULT_TIMEOUT_LOCAL_MS
    local: LocalInference = Field(default_factory=LocalInference)
    cloud_fallback: CloudFallback = Field(default_factory=CloudFallback)


class RouterConfig(BaseModel):
    listen_host: str = DEFAULT_LISTEN_HOST
    listen_port: int = DEFAULT_LISTEN_PORT
    tls: bool = False
    reload_on_sighup: bool = True


class CECLAWConfig(BaseModel):
    version: int = 1
    router: RouterConfig = Field(default_factory=RouterConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)


def load_config(config_path: Optional[str] = None) -> CECLAWConfig:
    """
    載入設定，優先順序：
    1. 預設值
    2. ceclaw.yaml
    3. 環境變數覆蓋
    """
    path = Path(config_path) if config_path else Path(
        os.environ.get("CECLAW_CONFIG", str(DEFAULT_CONFIG_PATH))
    )

    raw: dict = {}
    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

    config = CECLAWConfig.model_validate(raw)

    if host := os.environ.get("CECLAW_LISTEN_HOST"):
        config.router.listen_host = host
    if port := os.environ.get("CECLAW_LISTEN_PORT"):
        config.router.listen_port = int(port)
    if strategy := os.environ.get("CECLAW_STRATEGY"):
        config.inference.strategy = strategy
    if timeout := os.environ.get("CECLAW_TIMEOUT_LOCAL_MS"):
        config.inference.timeout_local_ms = int(timeout)

    return config
